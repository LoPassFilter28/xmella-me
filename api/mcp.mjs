// Read-only Streamable HTTP MCP server for xmella.me/us-dr (routed at /us-dr/mcp).
// Pure Node.js 26 Web Standards, zero external dependencies, Vercel Hobby friendly.
import {
  AGENT_LINK_HEADER,
  CHAT_FN,
  CHAT_KEY,
  SEARCH_VARIANTS,
  SITE_ORIGIN,
  TOPICS,
  USDR_BASE,
  expandVariants,
  fetchStaticAsset,
  normalize,
  renderArticleMarkdown,
  searchRecords,
} from './_usdr-md.mjs';

const SERVER_INFO = { name: 'xmella-us-dr', version: '1.0.0' };
const PROTOCOL_VERSION = '2025-06-18';
const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Accept, Mcp-Session-Id, MCP-Protocol-Version',
  'X-Content-Type-Options': 'nosniff',
};

// Warm-instance cache (reused across concurrent Fluid Compute requests, refreshed hourly).
const CACHE_TTL_MS = 60 * 60 * 1000;
const cache = {
  search: { data: null, at: 0, inflight: null },
  people: { data: null, at: 0, inflight: null },
  timeline: { data: null, at: 0, inflight: null },
  links: { data: null, at: 0, inflight: null },
  llms: { data: null, at: 0, inflight: null },
};

async function cachedLoad(slot, loader) {
  const now = Date.now();
  if (slot.data && now - slot.at < CACHE_TTL_MS) return slot.data;
  if (!slot.inflight) {
    slot.inflight = loader()
      .then((val) => {
        slot.data = val;
        slot.at = Date.now();
        slot.inflight = null;
        return val;
      })
      .catch((err) => {
        slot.inflight = null;
        throw err;
      });
  }
  return slot.inflight;
}

const getSearchIndex = (reqUrl) =>
  cachedLoad(cache.search, async () => {
    const res = await fetchStaticAsset(reqUrl, '/us-dr/assets/search-index.json');
    if (!res.ok) throw new Error(`search-index.json HTTP ${res.status}`);
    const data = await res.json();
    for (const r of data) {
      r._searchable = expandVariants(
        normalize([r.h, r.g, r.s, r.x, r.n, (r.d || '').slice(0, 4), r.v || '', r.w || ''].join(' '))
      );
      r._headline = normalize([r.h, r.g].join(' '));
      r._paper = normalize(r.n || '');
    }
    return data;
  });

const getPeopleIndex = (reqUrl) =>
  cachedLoad(cache.people, async () => {
    const res = await fetchStaticAsset(reqUrl, '/us-dr/assets/people-index.json');
    if (!res.ok) throw new Error(`people-index.json HTTP ${res.status}`);
    const data = await res.json();
    for (const p of data) {
      const toks = Array.isArray(p.tokens) ? [...p.tokens] : [];
      for (const [a, b] of SEARCH_VARIANTS) {
        if (toks.includes(a) && !toks.includes(b)) toks.push(b);
        else if (toks.includes(b) && !toks.includes(a)) toks.push(a);
      }
      p._tokens = toks;
      p._haystack = expandVariants(normalize([p.name, p.dates, p.role_en, p.role_es, toks.join(' ')].join(' ')));
    }
    return data;
  });

const getTimeline = (reqUrl) =>
  cachedLoad(cache.timeline, async () => {
    const res = await fetchStaticAsset(reqUrl, '/us-dr/assets/timeline-data.json');
    if (!res.ok) throw new Error(`timeline-data.json HTTP ${res.status}`);
    return res.json();
  });

const getLinks = (reqUrl) =>
  cachedLoad(cache.links, async () => {
    const res = await fetchStaticAsset(reqUrl, '/us-dr/assets/links.json');
    if (!res.ok) return {};
    return res.json();
  });

const getLlmsTxt = (reqUrl) =>
  cachedLoad(cache.llms, async () => {
    const res = await fetchStaticAsset(reqUrl, '/us-dr/llms.txt');
    if (!res.ok) throw new Error(`llms.txt HTTP ${res.status}`);
    return res.text();
  });

const TOOLS = [
  {
    name: 'search_articles',
    description:
      'Search all 7,955 bilingual articles in DR in the American Press (1820-1984) by keyword, year range, era slug, topic slug, newspaper, or full-text availability. Returns compact ranked records with IDs for get_article.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Keyword, person name, newspaper title, or 4-digit year.' },
        yearFrom: { type: 'integer', minimum: 1820, maximum: 1984, description: 'Earliest publication year.' },
        yearTo: { type: 'integer', minimum: 1820, maximum: 1984, description: 'Latest publication year.' },
        era: { type: 'string', description: 'Era slug from list_sections (e.g., trujillo-era).' },
        topic: { type: 'string', description: 'Topic slug from list_sections (e.g., samana-bay).' },
        newspaper: { type: 'string', description: 'Newspaper title substring filter.' },
        fullTextOnly: { type: 'boolean', default: false, description: 'Only return articles with full transcription.' },
        lang: { type: 'string', enum: ['en', 'es'], default: 'en', description: 'Language for returned headlines and summaries.' },
        limit: { type: 'integer', minimum: 1, maximum: 25, default: 10, description: 'Max results per page.' },
        offset: { type: 'integer', minimum: 0, default: 0, description: 'Pagination offset.' },
      },
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  {
    name: 'get_article',
    description:
      'Retrieve a single archive article as compact Markdown with Library of Congress provenance URL, summary, optional full transcription, and audited sibling printings.',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'Article record ID (e.g., cr00396-5).' },
        lang: { type: 'string', enum: ['en', 'es', 'both'], default: 'en', description: 'Language selection (single language cuts tokens ~50%).' },
        includeFullText: { type: 'boolean', default: true, description: 'Include full transcription body when available.' },
      },
      required: ['id'],
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  {
    name: 'list_sections',
    description: 'List all 10 historical eras (with year ranges, counts, blurbs, and top pick IDs), 12 topics, and top-level directory URLs.',
    inputSchema: {
      type: 'object',
      properties: {
        lang: { type: 'string', enum: ['en', 'es'], default: 'en', description: 'Preferred language for labels.' },
      },
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  {
    name: 'lookup_person',
    description: 'Search the archive directory of profiled historical figures by name or role keyword.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Person name, surname, or role keyword.' },
        lang: { type: 'string', enum: ['en', 'es'], default: 'en', description: 'Language for biographical role.' },
        limit: { type: 'integer', minimum: 1, maximum: 20, default: 8, description: 'Max profiles to return.' },
      },
      required: ['query'],
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  {
    name: 'ask_chatrd',
    description: 'Ask the archive-grounded ChatRD research assistant a natural-language question answered strictly from the collection articles with source citations.',
    inputSchema: {
      type: 'object',
      properties: {
        question: { type: 'string', description: 'Historical research question about the Dominican Republic in U.S. newspapers.' },
        lang: { type: 'string', enum: ['en', 'es'], default: 'en', description: 'Preferred answer language.' },
      },
      required: ['question'],
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: true },
  },
];

const RESOURCES = [
  {
    uri: 'usdr://llms.txt',
    name: 'Archive Agent Guide (llms.txt)',
    description: 'Overview, when-to-use guidance, URL patterns, and citation rules for xmella.me/us-dr.',
    mimeType: 'text/markdown',
  },
  {
    uri: 'usdr://eras',
    name: 'Historical Eras & Yearly Coverage',
    description: 'Structured JSON of all 10 eras (1804-1984), article counts, blurbs, and per-year totals.',
    mimeType: 'application/json',
  },
  {
    uri: 'usdr://people',
    name: 'Profiled Historical Figures',
    description: 'Structured JSON index of all profiled figures in DR in the American Press.',
    mimeType: 'application/json',
  },
];

function toolSuccess(payload, textOverride) {
  return {
    content: [{ type: 'text', text: textOverride ?? JSON.stringify(payload) }],
    structuredContent: payload,
  };
}

function toolError(message) {
  return {
    content: [{ type: 'text', text: JSON.stringify({ error: message }) }],
    isError: true,
  };
}

async function runTool(name, args, reqUrl) {
  const a = args && typeof args === 'object' ? args : {};
  if (name === 'search_articles') {
    const hasFilter =
      (typeof a.query === 'string' && a.query.trim()) ||
      Number.isInteger(a.yearFrom) ||
      Number.isInteger(a.yearTo) ||
      (typeof a.era === 'string' && a.era.trim()) ||
      (typeof a.topic === 'string' && a.topic.trim()) ||
      (typeof a.newspaper === 'string' && a.newspaper.trim()) ||
      a.fullTextOnly === true;
    if (!hasFilter) {
      return toolError('Provide a query or at least one filter (yearFrom, yearTo, era, topic, newspaper, fullTextOnly).');
    }
    const [records, people] = await Promise.all([getSearchIndex(reqUrl), getPeopleIndex(reqUrl).catch(() => [])]);
    const out = searchRecords(records, people, { ...a, lang: a.lang === 'es' ? 'es' : 'en' });
    return toolSuccess(out);
  }

  if (name === 'get_article') {
    if (typeof a.id !== 'string' || !/^[a-zA-Z0-9_-]{2,64}$/.test(a.id.trim())) {
      return toolError('Provide a valid article id (for example cr00396-5).');
    }
    const id = a.id.trim();
    const lang = a.lang === 'es' || a.lang === 'both' ? a.lang : 'en';
    const summaryOnly = a.includeFullText === false;
    let relPath = `/us-dr/articles/${encodeURIComponent(id)}.html`;
    let res = await fetchStaticAsset(reqUrl, relPath);
    if (res.status === 404) {
      relPath = `/us-dr/misc/${encodeURIComponent(id)}.html`;
      res = await fetchStaticAsset(reqUrl, relPath);
    }
    if (!res.ok) return toolError(`Article "${id}" not found (HTTP ${res.status}).`);
    const html = await res.text();
    const canonicalUrl = `${SITE_ORIGIN}${relPath}`;
    const markdown = renderArticleMarkdown(html, canonicalUrl, { lang, summaryOnly });
    const links = await getLinks(reqUrl).catch(() => ({}));
    const alsoRanIn = Array.isArray(links[id])
      ? links[id].map((s) => ({
          newspaper: s[0],
          date: s[1],
          id: s[2],
          url: `${USDR_BASE}articles/${encodeURIComponent(s[2])}.html`,
        }))
      : [];
    const payload = { id, url: canonicalUrl, lang, alsoRanIn, markdown };
    const sibSuffix = alsoRanIn.length
      ? `\n\n## Also Ran In\n${alsoRanIn.map((s) => `- ${s.newspaper} (${s.date}) — \`${s.id}\`: ${s.url}`).join('\n')}`
      : '';
    return toolSuccess(payload, markdown + sibSuffix);
  }

  if (name === 'list_sections') {
    const lang = a.lang === 'es' ? 'es' : 'en';
    const td = await getTimeline(reqUrl);
    const payload = {
      recordCount: td.recordCount || 0,
      fullTextCount: td.fullText || 0,
      eras: (td.chapters || []).map((c) => ({
        slug: c.slug,
        years: c.years,
        name: lang === 'es' ? c.es : c.en,
        blurb: lang === 'es' ? c.blurbEs : c.blurbEn,
        count: c.count,
        fullText: c.fullText,
        picks: c.picks || [],
        url: `${USDR_BASE}era/${encodeURIComponent(c.slug)}.html`,
      })),
      topics: TOPICS.map((t) => ({
        slug: t.slug,
        name: lang === 'es' ? t.es : t.en,
        url: `${USDR_BASE}topic/${encodeURIComponent(t.slug)}-1.html`,
      })),
      directories: {
        home: USDR_BASE,
        eras: `${USDR_BASE}eras.html`,
        papers: `${USDR_BASE}papers.html`,
        topics: `${USDR_BASE}topics.html`,
        profiles: `${USDR_BASE}profiles.html`,
        glossary: `${USDR_BASE}glossary.html`,
        guide: `${USDR_BASE}howto.html`,
        llmsTxt: `${USDR_BASE}llms.txt`,
        sitemap: `${USDR_BASE}sitemap.xml`,
      },
    };
    return toolSuccess(payload);
  }

  if (name === 'lookup_person') {
    if (typeof a.query !== 'string' || !a.query.trim()) {
      return toolError('Provide a non-empty query string.');
    }
    const lang = a.lang === 'es' ? 'es' : 'en';
    const limit = Math.max(1, Math.min(20, Number.isInteger(a.limit) ? a.limit : 8));
    const people = await getPeopleIndex(reqUrl);
    const terms = normalize(a.query.trim()).split(/\s+/).filter(Boolean);
    const found = people.filter((p) => terms.every((t) => p._haystack.includes(t)));
    const payload = {
      total: found.length,
      people: found.slice(0, limit).map((p) => ({
        slug: p.slug,
        name: p.name,
        dates: p.dates || '',
        role: (lang === 'es' ? p.role_es : p.role_en) || '',
        articleCount: typeof p.n === 'number' ? p.n : 0,
        profileUrl: `${USDR_BASE}profile/${encodeURIComponent(p.slug)}.html`,
        directoryUrl: `${USDR_BASE}profiles.html#p-${encodeURIComponent(p.slug)}`,
      })),
    };
    return toolSuccess(payload);
  }

  if (name === 'ask_chatrd') {
    if (typeof a.question !== 'string' || !a.question.trim()) {
      return toolError('Provide a non-empty research question.');
    }
    const lang = a.lang === 'es' ? 'es' : 'en';
    const res = await fetch(CHAT_FN, {
      method: 'POST',
      headers: { Authorization: `Bearer ${CHAT_KEY}`, apikey: CHAT_KEY, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: a.question.trim().slice(0, 500),
        history: [],
        visitor: 'mcp-agent',
        page: '/us-dr/mcp',
        lang,
      }),
    });
    const data = await res.json().catch(() => null);
    if (res.status === 429 || (data && data.error === 'rate_limited')) {
      return toolError('ChatRD rate limit reached. Use search_articles + get_article directly or retry later.');
    }
    if (!res.ok || !data || !data.answer) {
      return toolError(`ChatRD returned HTTP ${res.status}.`);
    }
    const payload = {
      answer: data.answer,
      articles: Array.isArray(data.articles)
        ? data.articles.map((x) => ({
            newspaper: x.newspaper || '',
            date: x.date || '',
            url: x.path ? USDR_BASE + x.path : USDR_BASE,
          }))
        : [],
    };
    return toolSuccess(payload);
  }

  return toolError(`Unknown tool: "${name}"`);
}

async function handleRpc(msg, reqUrl) {
  if (!msg || typeof msg !== 'object' || msg.jsonrpc !== '2.0' || typeof msg.method !== 'string') {
    return { jsonrpc: '2.0', id: msg?.id ?? null, error: { code: -32600, message: 'Invalid JSON-RPC 2.0 request' } };
  }

  const { id, method, params } = msg;

  // Notifications have no id and require no JSON-RPC response body.
  if (id === undefined || method === 'notifications/initialized' || method.startsWith('notifications/')) {
    return null;
  }

  try {
    if (method === 'initialize') {
      return {
        jsonrpc: '2.0',
        id,
        result: {
          protocolVersion: PROTOCOL_VERSION,
          capabilities: { tools: { listChanged: false }, resources: { subscribe: false, listChanged: false } },
          serverInfo: SERVER_INFO,
          instructions:
            'Read-only research MCP server for DR in the American Press (xmella.me/us-dr, 1820-1984). Call search_articles or list_sections to find record IDs, then get_article with lang="en" or lang="es" for token-efficient primary-source text and Library of Congress citations.',
        },
      };
    }

    if (method === 'ping') {
      return { jsonrpc: '2.0', id, result: {} };
    }

    if (method === 'tools/list') {
      return { jsonrpc: '2.0', id, result: { tools: TOOLS } };
    }

    if (method === 'tools/call') {
      const result = await runTool(params?.name, params?.arguments, reqUrl);
      return { jsonrpc: '2.0', id, result };
    }

    if (method === 'resources/list') {
      return { jsonrpc: '2.0', id, result: { resources: RESOURCES } };
    }

    if (method === 'resources/read') {
      const uri = params?.uri;
      if (uri === 'usdr://llms.txt') {
        const text = await getLlmsTxt(reqUrl);
        return { jsonrpc: '2.0', id, result: { contents: [{ uri, mimeType: 'text/markdown', text }] } };
      }
      if (uri === 'usdr://eras') {
        const td = await getTimeline(reqUrl);
        return { jsonrpc: '2.0', id, result: { contents: [{ uri, mimeType: 'application/json', text: JSON.stringify(td) }] } };
      }
      if (uri === 'usdr://people') {
        const people = await getPeopleIndex(reqUrl);
        const clean = people.map(({ _tokens, _haystack, ...rest }) => rest);
        return { jsonrpc: '2.0', id, result: { contents: [{ uri, mimeType: 'application/json', text: JSON.stringify(clean) }] } };
      }
      return { jsonrpc: '2.0', id, error: { code: -32002, message: `Resource not found: ${uri}` } };
    }

    return { jsonrpc: '2.0', id, error: { code: -32601, message: `Method not found: ${method}` } };
  } catch (err) {
    console.error('us-dr mcp error', { method, error: err instanceof Error ? err.message : String(err) });
    return {
      jsonrpc: '2.0',
      id,
      error: { code: -32603, message: err instanceof Error ? err.message : 'Internal server error' },
    };
  }
}

export function OPTIONS() {
  return new Response(null, { status: 204, headers: CORS_HEADERS });
}

export function GET(request) {
  const accept = request.headers.get('accept') || '';
  if (accept.includes('text/markdown')) {
    const md = [
      '# DR in the American Press — Remote MCP Endpoint',
      '',
      `- **Endpoint:** \`${USDR_BASE}mcp\` (Streamable HTTP JSON-RPC 2.0, POST)`,
      `- **Auth:** None (public read-only)`,
      `- **Tools:** ${TOOLS.map((t) => `\`${t.name}\``).join(', ')}`,
      `- **Resources:** ${RESOURCES.map((r) => `\`${r.uri}\``).join(', ')}`,
      `- **Guide:** [${USDR_BASE}llms.txt](${USDR_BASE}llms.txt)`,
      '',
    ].join('\n');
    return new Response(md, {
      status: 200,
      headers: { ...CORS_HEADERS, 'Content-Type': 'text/markdown; charset=utf-8', Vary: 'Accept', Link: AGENT_LINK_HEADER },
    });
  }

  return Response.json(
    {
      name: SERVER_INFO.name,
      version: SERVER_INFO.version,
      protocol: 'mcp',
      protocolVersion: PROTOCOL_VERSION,
      transport: 'streamable-http',
      endpoint: `${USDR_BASE}mcp`,
      authentication: 'none',
      readOnly: true,
      tools: TOOLS.map((t) => ({ name: t.name, description: t.description })),
      resources: RESOURCES,
      llmsTxt: `${USDR_BASE}llms.txt`,
    },
    {
      status: 200,
      headers: { ...CORS_HEADERS, Vary: 'Accept', Link: AGENT_LINK_HEADER },
    }
  );
}

export async function POST(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json(
      { jsonrpc: '2.0', id: null, error: { code: -32700, message: 'Parse error: expected valid JSON' } },
      { status: 400, headers: CORS_HEADERS }
    );
  }

  if (Array.isArray(body)) {
    const results = (await Promise.all(body.map((m) => handleRpc(m, request.url)))).filter(Boolean);
    if (!results.length) return new Response(null, { status: 202, headers: CORS_HEADERS });
    return Response.json(results, { status: 200, headers: CORS_HEADERS });
  }

  const reply = await handleRpc(body, request.url);
  if (reply === null) return new Response(null, { status: 202, headers: CORS_HEADERS });
  return Response.json(reply, { status: 200, headers: CORS_HEADERS });
}
