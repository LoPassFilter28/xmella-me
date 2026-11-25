// Shared HTML-to-Markdown, metadata extraction, and archive search helpers
// for xmella.me/us-dr Vercel Functions (Node.js 26, zero external deps).

export const SITE_ORIGIN = 'https://xmella.me';
export const USDR_BASE = `${SITE_ORIGIN}/us-dr/`;
export const CHAT_FN = 'https://xxdgxigwpnezsdvbiawi.supabase.co/functions/v1/chatrd';
export const CHAT_KEY =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh4ZGd4aWd3cG5lenNkdmJpYXdpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE2OTM0MDYsImV4cCI6MjEwNzI2OTQwNn0.3fuj9vjXspT31fQhgcejf4Thmk9yHPc7RSBZ0v97Gw4';

export const SEARCH_VARIANTS = [['jimenes', 'jimenez']];

export const TOPICS = [
  { slug: 'columbus', en: 'Columbus', es: 'Colón' },
  { slug: 'finance-debt', en: 'Debt & Finance', es: 'Deuda y finanzas' },
  { slug: 'diplomacy-treaties', en: 'Diplomacy & Treaties', es: 'Diplomacia y tratados' },
  { slug: 'elections-politics', en: 'Elections & Politics', es: 'Elecciones y política' },
  { slug: 'haiti-relations', en: 'Haiti', es: 'Haití' },
  { slug: 'culture-society', en: 'Life & Culture', es: 'Vida y cultura' },
  { slug: 'naval-military', en: 'Naval & Military', es: 'Asuntos navales y militares' },
  { slug: 'revolution-unrest', en: 'Revolution & Unrest', es: 'Revolución y disturbios' },
  { slug: 'samana-bay', en: 'Samaná Bay', es: 'Bahía de Samaná' },
  { slug: 'natural-disaster', en: 'Storms & Disasters', es: 'Tormentas y desastres' },
  { slug: 'trade-sugar', en: 'Sugar & Trade', es: 'Azúcar y comercio' },
  { slug: 'us-intervention', en: 'U.S. Intervention', es: 'Intervención estadounidense' },
];

export const AGENT_LINK_HEADER = [
  '</us-dr/llms.txt>; rel="describedby"; type="text/markdown"',
  '</us-dr/sitemap.xml>; rel="sitemap"; type="application/xml"',
  '</us-dr/mcp>; rel="service-desc"; type="application/json"',
  '</us-dr/opensearch.xml>; rel="search"; type="application/opensearchdescription+xml"',
].join(', ');

export function normalize(str) {
  return String(str || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

export function expandVariants(str) {
  let out = str;
  for (const [a, b] of SEARCH_VARIANTS) {
    if (out.includes(a) && !out.includes(b)) out += ` ${b}`;
    else if (out.includes(b) && !out.includes(a)) out += ` ${a}`;
  }
  return out;
}

const NAMED_ENTITIES = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: ' ',
  middot: '·',
  mdash: '—',
  ndash: '–',
  hellip: '…',
  laquo: '«',
  raquo: '»',
  ldquo: '“',
  rdquo: '”',
  lsquo: '‘',
  rsquo: '’',
  times: '×',
  copy: '©',
  rarr: '→',
  larr: '←',
};

export function decodeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z]+);/g, (full, ent) => {
    if (ent[0] === '#') {
      const code = ent[1] === 'x' || ent[1] === 'X' ? parseInt(ent.slice(2), 16) : parseInt(ent.slice(1), 10);
      return Number.isFinite(code) ? String.fromCodePoint(code) : full;
    }
    return Object.hasOwn(NAMED_ENTITIES, ent) ? NAMED_ENTITIES[ent] : full;
  });
}

function escapeYaml(val) {
  return JSON.stringify(String(val ?? ''));
}

export function extractMeta(html) {
  const metas = {};
  const metaRe = /<meta\s+[^>]*?(?:name|property)=["']([^"']+)["'][^>]*?content=["']([^"']*)["'][^>]*>/gi;
  const metaRevRe = /<meta\s+[^>]*?content=["']([^"']*)["'][^>]*?(?:name|property)=["']([^"']+)["'][^>]*>/gi;
  let m;
  while ((m = metaRe.exec(html))) {
    if (!metas[m[1]]) metas[m[1]] = decodeHtml(m[2]);
  }
  while ((m = metaRevRe.exec(html))) {
    if (!metas[m[2]]) metas[m[2]] = decodeHtml(m[1]);
  }
  const titleMatch = /<title>([\s\S]*?)<\/title>/i.exec(html);
  const titleEnMatch = /data-title-en=["']([^"']*)["']/i.exec(html);
  const titleEsMatch = /data-title-es=["']([^"']*)["']/i.exec(html);
  const canonicalMatch = /<link\s+[^>]*rel=["']canonical["'][^>]*href=["']([^"']+)["']/i.exec(html);

  return {
    title: titleMatch ? decodeHtml(titleMatch[1]).trim() : '',
    titleEn: titleEnMatch ? decodeHtml(titleEnMatch[1]).trim() : '',
    titleEs: titleEsMatch ? decodeHtml(titleEsMatch[1]).trim() : '',
    canonical: canonicalMatch ? decodeHtml(canonicalMatch[1]).trim() : '',
    description: metas.description || '',
    dcTitle: metas['DC.title'] || '',
    publisher: metas['DC.publisher'] || metas.citation_journal_title || '',
    date: metas['DC.date'] || '',
    sourceUrl: metas['DC.source'] || '',
    identifier: metas['DC.identifier'] || '',
    page: metas.citation_firstpage || '',
    citationTitle: metas.citation_title || '',
  };
}

// Removes balanced HTML elements carrying a specific class (e.g. "l-en" or "l-es").
export function stripElementsByClass(html, className) {
  const openRe = new RegExp(
    `<(span|p|div|li|h[1-6]|figcaption|small|b|strong|em)\\b[^>]*\\bclass=["'][^"']*\\b${className}\\b[^"']*["'][^>]*>`,
    'gi'
  );
  let result = html;
  let safety = 0;
  while (safety++ < 20000) {
    openRe.lastIndex = 0;
    const match = openRe.exec(result);
    if (!match) break;
    const tag = match[1].toLowerCase();
    const startIdx = match.index;
    const afterOpen = startIdx + match[0].length;
    const tagScan = new RegExp(`<(\\/)?${tag}\\b[^>]*>`, 'gi');
    tagScan.lastIndex = afterOpen;
    let depth = 1;
    let endIdx = result.length;
    let t;
    while ((t = tagScan.exec(result))) {
      if (t[1]) depth--;
      else if (!t[0].endsWith('/>')) depth++;
      if (depth === 0) {
        endIdx = t.index + t[0].length;
        break;
      }
    }
    result = result.slice(0, startIdx) + result.slice(endIdx);
  }
  return result;
}

export function extractTagBlock(html, openRegex, tagName) {
  const m = openRegex.exec(html);
  if (!m) return '';
  const start = m.index + m[0].length;
  const tagScan = new RegExp(`<(\\/)?${tagName}\\b[^>]*>`, 'gi');
  tagScan.lastIndex = start;
  let depth = 1;
  let t;
  while ((t = tagScan.exec(html))) {
    if (t[1]) depth--;
    else if (!t[0].endsWith('/>')) depth++;
    if (depth === 0) return html.slice(start, t.index);
  }
  return html.slice(start);
}

function resolveHref(href, baseUrl) {
  if (!href) return '';
  const clean = decodeHtml(href).trim();
  if (/^(?:https?:|mailto:|#)/i.test(clean)) return clean;
  try {
    return new URL(clean, baseUrl).href;
  } catch {
    return clean;
  }
}

export function fragmentToMarkdown(fragment, { baseUrl = USDR_BASE, lang = 'both' } = {}) {
  let s = String(fragment || '');
  s = s.replace(/<script\b[\s\S]*?<\/script>/gi, '');
  s = s.replace(/<style\b[\s\S]*?<\/style>/gi, '');
  s = s.replace(/<svg\b[\s\S]*?<\/svg>/gi, '');
  s = s.replace(/<section\b[^>]*id=["']search-panel["'][\s\S]*?<\/section>/gi, '');
  s = stripElementsByClass(s, 'dz-ghost');
  s = stripElementsByClass(s, 'sbar');
  s = stripElementsByClass(s, 'hp');
  s = stripElementsByClass(s, 'plt-endmark');

  if (lang === 'en') s = stripElementsByClass(s, 'l-es');
  else if (lang === 'es') s = stripElementsByClass(s, 'l-en');

  // Preserve anchor links as Markdown links
  s = s.replace(/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi, (_, href, inner) => {
    const label = decodeHtml(inner.replace(/<[^>]+>/g, ' '))
      .replace(/\s+/g, ' ')
      .trim();
    if (!label) return '';
    return `[${label}](${resolveHref(href, baseUrl)})`;
  });

  // Headings
  for (let level = 1; level <= 6; level++) {
    const re = new RegExp(`<h${level}\\b[^>]*>([\\s\\S]*?)<\\/h${level}>`, 'gi');
    s = s.replace(re, (_, inner) => {
      const txt = decodeHtml(inner.replace(/<[^>]+>/g, ' '))
        .replace(/\s+/g, ' ')
        .trim();
      return txt ? `\n\n${'#'.repeat(level)} ${txt}\n\n` : '\n\n';
    });
  }

  // Details/summary (e.g., papers.html state cards)
  s = s.replace(/<summary\b[^>]*>([\s\S]*?)<\/summary>/gi, (_, inner) => {
    const txt = decodeHtml(inner.replace(/<[^>]+>/g, ' '))
      .replace(/\s+/g, ' ')
      .trim();
    return txt ? `\n\n## ${txt}\n\n` : '\n\n';
  });

  // Blockquotes
  s = s.replace(/<blockquote\b[^>]*>([\s\S]*?)<\/blockquote>/gi, (_, inner) => {
    const txt = decodeHtml(inner.replace(/<[^>]+>/g, ' '))
      .replace(/\s+/g, ' ')
      .trim();
    return txt ? `\n\n> ${txt}\n\n` : '\n\n';
  });

  // List items
  s = s.replace(/<li\b[^>]*>([\s\S]*?)<\/li>/gi, (_, inner) => {
    const txt = decodeHtml(inner.replace(/<[^>]+>/g, ' '))
      .replace(/\s+/g, ' ')
      .trim();
    return txt ? `\n- ${txt}` : '';
  });

  // Inline emphasis
  s = s.replace(/<(?:b|strong)\b[^>]*>([\s\S]*?)<\/(?:b|strong)>/gi, (_, inner) => {
    const txt = inner.replace(/<[^>]+>/g, '').trim();
    return txt ? `**${txt}**` : '';
  });
  s = s.replace(/<(?:i|em)\b[^>]*>([\s\S]*?)<\/(?:i|em)>/gi, (_, inner) => {
    const txt = inner.replace(/<[^>]+>/g, '').trim();
    return txt ? `*${txt}*` : '';
  });

  // Structural breaks
  s = s.replace(/<br\s*\/?>/gi, '\n');
  s = s.replace(/<\/(?:p|div|section|article|figure|figcaption|ul|ol|details|header)>/gi, '\n\n');
  s = s.replace(/<[^>]+>/g, '');
  s = decodeHtml(s);

  return s
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n[ \t]+/g, '\n')
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

export function renderArticleMarkdown(html, canonicalUrl, { lang = 'both', summaryOnly = false } = {}) {
  const meta = extractMeta(html);
  const main = extractTagBlock(html, /<main\b[^>]*>/i, 'main') || html;
  const h1Block = extractTagBlock(main, /<h1\b[^>]*>/i, 'h1');
  const titleEn = fragmentToMarkdown(h1Block, { baseUrl: canonicalUrl, lang: 'en' }) || meta.citationTitle || meta.titleEn;
  const titleEs = fragmentToMarkdown(h1Block, { baseUrl: canonicalUrl, lang: 'es' }) || meta.titleEs;

  const seriesBlock = extractTagBlock(main, /<a\b[^>]*class=["'][^"']*\bplt-series\b[^"']*["'][^>]*>/i, 'a');
  const seriesHrefMatch = /<a\b[^>]*class=["'][^"']*\bplt-series\b[^"']*["'][^>]*href=["']([^"']+)["']/i.exec(main);
  const deckBlock = extractTagBlock(main, /<section\b[^>]*class=["'][^"']*\bplt-deck\b[^"']*["'][^>]*>/i, 'section');
  const summaryBlock = extractTagBlock(main, /<section\b[^>]*class=["'][^"']*\bplt-summary\b[^"']*["'][^>]*>/i, 'section');
  const bodyBlock = extractTagBlock(main, /<div\b[^>]*class=["'][^"']*\bplt-body\b[^"']*["'][^>]*>/i, 'div');
  const noteBlock = extractTagBlock(main, /<p\b[^>]*class=["'][^"']*\bplt-note\b[^"']*["'][^>]*>/i, 'p');

  const id = meta.identifier && !meta.identifier.startsWith('http')
    ? meta.identifier
    : (/\/(?:articles|misc)\/([^/?#]+)\.html/.exec(canonicalUrl)?.[1] || '');

  const fmLines = [
    '---',
    `id: ${escapeYaml(id)}`,
    `title_en: ${escapeYaml(titleEn)}`,
    `title_es: ${escapeYaml(titleEs)}`,
    `newspaper: ${escapeYaml(meta.publisher)}`,
    `date: ${escapeYaml(meta.date)}`,
    meta.page ? `page: ${escapeYaml(meta.page)}` : null,
    `source_url: ${escapeYaml(meta.sourceUrl)}`,
    `canonical_url: ${escapeYaml(canonicalUrl)}`,
    `lang: ${escapeYaml(lang)}`,
    `single_lang_hint: ${escapeYaml(`Append ?lang=en or ?lang=es for single-language output.`)}`,
    '---',
  ].filter(Boolean);

  const out = [fmLines.join('\n')];
  const primaryTitle = lang === 'es' ? titleEs || titleEn : titleEn || titleEs;
  out.push(`# ${primaryTitle}`);

  const metaParts = [meta.publisher, meta.date, meta.page ? `Page ${meta.page}` : ''].filter(Boolean);
  if (metaParts.length) out.push(`**Citation:** ${metaParts.join(' · ')}`);
  if (meta.sourceUrl) out.push(`**Original primary source:** ${meta.sourceUrl}`);
  if (seriesBlock) {
    const sTxt = fragmentToMarkdown(seriesBlock, { baseUrl: canonicalUrl, lang: lang === 'both' ? 'en' : lang });
    const sUrl = seriesHrefMatch ? resolveHref(seriesHrefMatch[1], canonicalUrl) : '';
    if (sTxt) out.push(sUrl ? `**Era:** [${sTxt}](${sUrl})` : `**Era:** ${sTxt}`);
  }

  const langs = lang === 'both' ? ['en', 'es'] : [lang];
  for (const l of langs) {
    const tag = l === 'en' ? 'English' : 'Español';
    const deckMd = deckBlock ? fragmentToMarkdown(deckBlock, { baseUrl: canonicalUrl, lang: l }) : '';
    const sumMd = summaryBlock ? fragmentToMarkdown(summaryBlock, { baseUrl: canonicalUrl, lang: l }) : '';
    const bodyMd = !summaryOnly && bodyBlock ? fragmentToMarkdown(bodyBlock, { baseUrl: canonicalUrl, lang: l }) : '';
    const noteMd = noteBlock ? fragmentToMarkdown(noteBlock, { baseUrl: canonicalUrl, lang: l }) : '';

    if (deckMd) out.push(`## ${l === 'en' ? 'Subheads' : 'Subtítulos'}${lang === 'both' ? ` (${tag})` : ''}\n\n${deckMd}`);
    if (sumMd) out.push(`## ${l === 'en' ? 'Summary' : 'Resumen'}${lang === 'both' ? ` (${tag})` : ''}\n\n${sumMd}`);
    if (bodyMd) out.push(`## ${l === 'en' ? 'Full Text' : 'Texto completo'}${lang === 'both' ? ` (${tag})` : ''}\n\n${bodyMd}`);
    if (noteMd) out.push(`> **${l === 'en' ? 'Editorial note' : 'Nota editorial'}:** ${noteMd}`);
  }

  return out.join('\n\n') + '\n';
}

export function renderGenericPageMarkdown(html, canonicalUrl, { lang = 'both' } = {}) {
  const meta = extractMeta(html);
  const main = extractTagBlock(html, /<main\b[^>]*>/i, 'main') || html;
  const fm = [
    '---',
    `title_en: ${escapeYaml(meta.titleEn || meta.title)}`,
    `title_es: ${escapeYaml(meta.titleEs || meta.title)}`,
    `canonical_url: ${escapeYaml(canonicalUrl)}`,
    `lang: ${escapeYaml(lang)}`,
    `llms_txt: ${escapeYaml(USDR_BASE + 'llms.txt')}`,
    `mcp_endpoint: ${escapeYaml(USDR_BASE + 'mcp')}`,
    '---',
  ].join('\n');

  if (lang === 'both') {
    const enMd = fragmentToMarkdown(main, { baseUrl: canonicalUrl, lang: 'en' });
    const esMd = fragmentToMarkdown(main, { baseUrl: canonicalUrl, lang: 'es' });
    if (enMd === esMd) return `${fm}\n\n${enMd}\n`;
    return `${fm}\n\n<!-- Pass ?lang=en or ?lang=es to reduce tokens by ~50% -->\n\n## English\n\n${enMd}\n\n---\n\n## Español\n\n${esMd}\n`;
  }
  const body = fragmentToMarkdown(main, { baseUrl: canonicalUrl, lang });
  return `${fm}\n\n${body}\n`;
}

export function renderHomeMarkdown(timelineData, lang = 'both') {
  const chapters = Array.isArray(timelineData?.chapters) ? timelineData.chapters : [];
  const total = timelineData?.recordCount || 7954;
  const fullText = timelineData?.fullText || 588;
  const lines = [
    '---',
    `title_en: "DR in the American Press (1820-1984)"`,
    `title_es: "RD en la Prensa Norteamericana (1820-1984)"`,
    `canonical_url: "${USDR_BASE}"`,
    `records: ${total}`,
    `full_text_transcriptions: ${fullText}`,
    `languages: ["es", "en"]`,
    `llms_txt: "${USDR_BASE}llms.txt"`,
    `sitemap: "${USDR_BASE}sitemap.xml"`,
    `mcp_endpoint: "${USDR_BASE}mcp"`,
    '---',
    '',
    '# DR in the American Press / RD en la Prensa Norteamericana',
    '',
  ];

  if (lang !== 'es') {
    lines.push(
      `A bilingual (English/Spanish) historical archive of United States newspaper coverage of the Dominican Republic from 1820 to 1984 (${total} records across 1,023 newspapers, including ${fullText} full transcriptions). Most records link directly to original digitized newspaper pages at the Library of Congress (Chronicling America).`
    );
    lines.push('');
  }
  if (lang !== 'en') {
    lines.push(
      `Una colección bilingüe (inglés/español) de la cobertura histórica de la República Dominicana en periódicos de Estados Unidos de 1820 a 1984 (${total} registros de 1,023 periódicos, incluidas ${fullText} transcripciones completas). La mayoría enlaza directamente a la página original en la Biblioteca del Congreso (Chronicling America).`
    );
    lines.push('');
  }

  lines.push('## Agent-Native Access (Most Token-Efficient)');
  lines.push(`- **Remote MCP server (Streamable HTTP JSON-RPC):** \`${USDR_BASE}mcp\` — tools: \`search_articles\`, \`get_article\`, \`list_sections\`, \`lookup_person\`, \`ask_chatrd\`.`);
  lines.push(`- **Markdown content negotiation:** Send \`Accept: text/markdown\` to any \`/us-dr/\` URL (append \`?lang=en\` or \`?lang=es\` for single-language Markdown, or \`&summary=1\` on articles).`);
  lines.push(`- **Archive guide & citation rules:** [${USDR_BASE}llms.txt](${USDR_BASE}llms.txt)`);
  lines.push(`- **Search URL:** \`${USDR_BASE}?q=<query>\` (or structured JSON indexes: [timeline-data.json](${USDR_BASE}assets/timeline-data.json), [people-index.json](${USDR_BASE}assets/people-index.json), [links.json](${USDR_BASE}assets/links.json), [search-index.json](${USDR_BASE}assets/search-index.json)).`);
  lines.push('');

  lines.push('## Sections');
  lines.push(`- [Eras / Eras](${USDR_BASE}eras.html)`);
  lines.push(`- [Newspapers / Periódicos](${USDR_BASE}papers.html)`);
  lines.push(`- [Topics / Temas](${USDR_BASE}topics.html)`);
  lines.push(`- [Profiles / Perfiles](${USDR_BASE}profiles.html)`);
  lines.push(`- [Glossary / Glosario](${USDR_BASE}glossary.html)`);
  lines.push(`- [Guide / Guía](${USDR_BASE}howto.html)`);
  lines.push('');

  if (chapters.length) {
    lines.push('## Historical Eras (1804–1984)');
    for (const c of chapters) {
      const label = lang === 'es' ? c.es : lang === 'en' ? c.en : `${c.en} / ${c.es}`;
      const blurb = lang === 'es' ? c.blurbEs : c.blurbEn;
      lines.push(`- **${c.years}** — [${label}](${USDR_BASE}era/${c.slug}.html) (${c.count} articles, ${c.fullText} full text): ${blurb}`);
    }
    lines.push('');
  }

  lines.push('## Topics');
  for (const t of TOPICS) {
    const label = lang === 'es' ? t.es : lang === 'en' ? t.en : `${t.en} / ${t.es}`;
    lines.push(`- [${label}](${USDR_BASE}topic/${t.slug}-1.html) (\`${t.slug}\`)`);
  }

  return lines.join('\n') + '\n';
}

export function renderNotFoundMarkdown(reqPath) {
  return [
    '---',
    'status: 404',
    `requested_path: ${escapeYaml(reqPath)}`,
    `llms_txt: "${USDR_BASE}llms.txt"`,
    `sitemap: "${USDR_BASE}sitemap.xml"`,
    `mcp_endpoint: "${USDR_BASE}mcp"`,
    '---',
    '',
    '# 404 — Page Not Found in DR in the American Press (`xmella.me/us-dr`)',
    '',
    `The requested path \`${reqPath}\` does not exist in this archive.`,
    '',
    '## Where to navigate next',
    `- **Archive home & overview:** [${USDR_BASE}](${USDR_BASE})`,
    `- **Agent instructions & citation guide:** [${USDR_BASE}llms.txt](${USDR_BASE}llms.txt)`,
    `- **Complete sitemap (all 7,955+ articles):** [${USDR_BASE}sitemap.xml](${USDR_BASE}sitemap.xml)`,
    `- **Remote MCP endpoint (search & retrieve articles directly):** \`${USDR_BASE}mcp\``,
    `- **Browse by era:** [${USDR_BASE}eras.html](${USDR_BASE}eras.html)`,
    `- **Search the archive:** \`${USDR_BASE}?q=<keyword>\``,
    '',
  ].join('\n');
}

export async function fetchStaticAsset(requestUrl, pathname) {
  let reqOrigin = SITE_ORIGIN;
  try {
    const u = new URL(requestUrl);
    if (u.hostname === 'xmella.me' || u.hostname === 'www.xmella.me') {
      reqOrigin = u.origin;
    }
  } catch {}

  const headers = { Accept: 'text/html,application/json,*/*', 'x-usdr-raw-html': '1' };
  const primary = await fetch(reqOrigin + pathname, { headers, redirect: 'follow' });
  if (primary.status !== 401 && primary.status !== 403) return primary;
  if (reqOrigin !== SITE_ORIGIN) {
    return fetch(SITE_ORIGIN + pathname, { headers, redirect: 'follow' });
  }
  return primary;
}

export function searchRecords(records, people, params = {}) {
  const rawQuery = typeof params.query === 'string' ? params.query.trim() : '';
  const lang = params.lang === 'en' ? 'en' : 'es';
  const limit = Math.max(1, Math.min(25, Number.isInteger(params.limit) ? params.limit : 10));
  const offset = Math.max(0, Number.isInteger(params.offset) ? params.offset : 0);
  const yearFrom = Number.isInteger(params.yearFrom) ? params.yearFrom : null;
  const yearTo = Number.isInteger(params.yearTo) ? params.yearTo : null;
  const era = typeof params.era === 'string' && params.era.trim() ? normalize(params.era.trim()) : null;
  const topic = typeof params.topic === 'string' && params.topic.trim() ? normalize(params.topic.trim()) : null;
  const newspaper = typeof params.newspaper === 'string' && params.newspaper.trim() ? normalize(params.newspaper.trim()) : null;
  const fullTextOnly = params.fullTextOnly === true;

  const qNorm = normalize(rawQuery);
  const terms = qNorm.split(/\s+/).filter(Boolean);
  const exactYear = /^\d{4}$/.test(rawQuery) ? rawQuery : null;

  const matched = [];
  for (const r of records) {
    if (terms.length && !terms.every((t) => r._searchable.includes(t))) continue;
    const y = parseInt((r.d || '').slice(0, 4), 10);
    if (yearFrom !== null && (!y || y < yearFrom)) continue;
    if (yearTo !== null && (!y || y > yearTo)) continue;
    if (era && normalize(r.u || '') !== era) continue;
    if (topic && !(Array.isArray(r.t) && r.t.some((s) => normalize(s) === topic))) continue;
    if (newspaper && !r._paper.includes(newspaper)) continue;
    if (fullTextOnly && !r.f) continue;

    const tier =
      exactYear && (r.d || '').slice(0, 4) === exactYear
        ? -1
        : terms.length && terms.every((t) => r._paper.includes(t))
          ? 0
          : terms.length && terms.every((t) => r._headline.includes(t))
            ? 1
            : 2;
    matched.push({ r, tier });
  }

  matched.sort(
    (a, b) =>
      a.tier - b.tier ||
      (a.tier === 0 && b.tier === 0 && a.r.n !== b.r.n ? a.r.n.localeCompare(b.r.n) : 0) ||
      String(b.r.d || '').localeCompare(String(a.r.d || ''))
  );

  const peopleDoors =
    terms.length && terms.some((t) => t.length >= 4)
      ? people
          .filter((p) => terms.every((t) => p._tokens.includes(t)))
          .slice(0, 4)
          .map((p) => ({
            slug: p.slug,
            name: p.name,
            dates: p.dates || '',
            role: (lang === 'es' ? p.role_es : p.role_en) || '',
            profileUrl: `${USDR_BASE}profile/${encodeURIComponent(p.slug)}.html`,
          }))
      : [];

  const results = matched.slice(offset, offset + limit).map(({ r }) => {
    const rel = r.m ? `misc/${encodeURIComponent(r.i)}.html` : `articles/${encodeURIComponent(r.i)}.html`;
    const url = USDR_BASE + rel;
    return {
      id: r.i,
      headline: lang === 'es' && r.g ? r.g : r.h,
      originalHeadline: r.h,
      date: r.d,
      newspaper: r.n,
      eraSlug: r.u || '',
      hasFullText: Boolean(r.f),
      summary: lang === 'es' && r.x ? r.x : r.s,
      url,
      markdownUrl: `${url}?lang=${lang}`,
    };
  });

  return {
    total: matched.length,
    returned: results.length,
    offset,
    lang,
    peopleDoors,
    results,
  };
}
