/* Agent navigation, accessibility-tree hardening, and WebMCP tools
   for "DR in the American Press / RD en la Prensa Norteamericana"
   (xmella.me/us-dr). Loaded defensively on every /us-dr/ page by
   assets/chatrd.js. Zero visual, layout, CSS, or copy changes for
   human readers. */
(() => {
  'use strict';
  if (window.__usdrAgentToolsLoaded) return;
  window.__usdrAgentToolsLoaded = true;

  const ORIGIN = location.origin === 'null' ? 'https://xmella.me' : location.origin;
  const selfScript = document.currentScript || document.querySelector('script[src*="agent-tools.js"]') || document.querySelector('script[src*="chatrd.js"]');
  const scriptSrc = (selfScript && selfScript.src) || (ORIGIN + '/us-dr/assets/agent-tools.js');
  const ASSETS_URL = scriptSrc.replace(/[^/]+(?:\?.*)?$/, '');
  const ROOT_URL = ASSETS_URL.replace(/assets\/$/, '');
  const CHAT_FN = 'https://xxdgxigwpnezsdvbiawi.supabase.co/functions/v1/chatrd';
  const CHAT_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh4ZGd4aWd3cG5lenNkdmJpYXdpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE2OTM0MDYsImV4cCI6MjEwNzI2OTQwNn0.3fuj9vjXspT31fQhgcejf4Thmk9yHPc7RSBZ0v97Gw4';

  const SEARCH_VARIANTS = [['jimenes', 'jimenez']];
  const TOPICS = [
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

  const activeLang = () => (document.body && document.body.dataset.lang === 'en' ? 'en' : 'es');
  const normalize = (s) => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const expandVariants = (s) => {
    let out = s;
    for (const [a, b] of SEARCH_VARIANTS) {
      if (out.includes(a) && !out.includes(b)) out += ' ' + b;
      else if (out.includes(b) && !out.includes(a)) out += ' ' + a;
    }
    return out;
  };
  const recRelPath = (r) => (r.m ? `misc/${encodeURIComponent(r.i)}.html` : `articles/${encodeURIComponent(r.i)}.html`);

  // ---------------------------------------------------------------------------
  // 1. Accessibility-tree & semantic HTML hardening (0 visual changes)
  // ---------------------------------------------------------------------------
  function applySemantics() {
    const lang = activeLang();

    // Tag bilingual spans with explicit lang attributes for DOM/a11y agents.
    document.querySelectorAll('.l-en:not([lang])').forEach((el) => el.setAttribute('lang', 'en'));
    document.querySelectorAll('.l-es:not([lang])').forEach((el) => el.setAttribute('lang', 'es'));

    // Ensure non-submit buttons carry explicit type="button".
    ['#btn-es', '#btn-en', '#btn-theme', '#close-search', '#search-more'].forEach((sel) => {
      const btn = document.querySelector(sel);
      if (btn && !btn.getAttribute('type')) btn.setAttribute('type', 'button');
    });

    // Give primary <nav> a distinguishable accessible name and mark current section.
    const nav = document.querySelector('nav.main');
    if (nav) {
      if (!nav.hasAttribute('data-en-aria-label')) nav.setAttribute('data-en-aria-label', 'Primary');
      if (!nav.hasAttribute('data-es-aria-label')) nav.setAttribute('data-es-aria-label', 'Principal');
      nav.setAttribute('aria-label', lang === 'en' ? 'Primary' : 'Principal');
    }

    const path = location.pathname;
    const isHome = /\/us-dr\/(?:index\.html)?$/.test(path);
    const homeLink = document.querySelector('.topbar .tb-home');
    if (homeLink) {
      if (isHome) homeLink.setAttribute('aria-current', 'page');
      else homeLink.removeAttribute('aria-current');
    }
    const guideLink = document.querySelector('.topbar .guide-corner');
    if (guideLink) {
      if (/\/us-dr\/howto\.html$/.test(path)) guideLink.setAttribute('aria-current', 'page');
      else guideLink.removeAttribute('aria-current');
    }
    if (nav) {
      const sectionMatchers = [
        ['eras.html', /\/us-dr\/(?:eras\.html|(?:era|chapter)\/)/],
        ['papers.html', /\/us-dr\/(?:papers\.html|paper\/)/],
        ['topics.html', /\/us-dr\/(?:topics\.html|topic\/)/],
        ['profiles.html', /\/us-dr\/(?:profiles\.html|profile\/)/],
        ['glossary.html', /\/us-dr\/glossary\.html$/],
      ];
      nav.querySelectorAll('a[href]').forEach((a) => {
        const href = a.getAttribute('href') || '';
        const match = sectionMatchers.find(([file]) => href.endsWith(file));
        if (match && match[1].test(path)) a.setAttribute('aria-current', 'page');
        else a.removeAttribute('aria-current');
      });
    }

    // Disambiguate repeated "Read the full era" links on eras.html (WCAG 2.5.3 Label in Name).
    document.querySelectorAll('.dz-chapter').forEach((ch) => {
      const door = ch.querySelector('a.dz-door');
      if (!door || door.querySelector('.sr-only')) return;
      const kicker = (ch.querySelector('.dz-kicker')?.textContent || '').trim();
      const nameEn = (ch.querySelector('.dz-name .l-en')?.textContent || '').trim();
      const nameEs = (ch.querySelector('.dz-name .l-es')?.textContent || '').trim();
      if (nameEn && nameEs) {
        const enLabel = `Read the full era: ${nameEn}${kicker ? ` (${kicker})` : ''}`;
        const esLabel = `Leer la era completa: ${nameEs}${kicker ? ` (${kicker})` : ''}`;
        door.setAttribute('data-en-aria-label', enLabel);
        door.setAttribute('data-es-aria-label', esLabel);
        door.setAttribute('aria-label', lang === 'en' ? enLabel : esLabel);
      }
    });

    // Disambiguate repeated "Read the full profile" links on profiles.html (WCAG 2.5.3).
    document.querySelectorAll('.entry').forEach((entry) => {
      const door = entry.querySelector('.profile-door a');
      const name = (entry.querySelector('.entry-h')?.textContent || '').trim();
      if (door && name) {
        const enLabel = `Read the full profile: ${name}`;
        const esLabel = `Leer el perfil completo: ${name}`;
        door.setAttribute('data-en-aria-label', enLabel);
        door.setAttribute('data-es-aria-label', esLabel);
        door.setAttribute('aria-label', lang === 'en' ? enLabel : esLabel);
      }
    });

    // Annotate topbar search form with WebMCP declarative attributes on all pages.
    const searchForm = document.querySelector('.topbar form.search-wrap');
    if (searchForm) {
      if (!searchForm.hasAttribute('toolname')) searchForm.setAttribute('toolname', 'search_archive_form');
      if (!searchForm.hasAttribute('tooldescription')) {
        searchForm.setAttribute('tooldescription', 'Search the Dominican Republic in the American Press historical newspaper archive by keyword, person, newspaper, or year.');
      }
      if (!searchForm.hasAttribute('toolautosubmit')) searchForm.setAttribute('toolautosubmit', '');
      const qInput = searchForm.querySelector('input[type="search"], input[name="q"]');
      if (qInput) {
        if (!qInput.hasAttribute('toolparamdescription')) {
          qInput.setAttribute('toolparamdescription', 'Search query: keyword, person name, newspaper title, or 4-digit year (e.g., Samana, Trujillo, 1871).');
        }
        qInput.setAttribute('aria-controls', 'search-panel');
      }
    }

    // Annotate newsletter form declaratively WITHOUT toolautosubmit (external email action).
    const nlForm = document.getElementById('nl-form');
    if (nlForm) {
      if (!nlForm.hasAttribute('toolname')) nlForm.setAttribute('toolname', 'subscribe_newsletter');
      if (!nlForm.hasAttribute('tooldescription')) {
        nlForm.setAttribute('tooldescription', 'Prepare a newsletter signup for archive updates. Requires user confirmation before sending.');
      }
      nlForm.removeAttribute('toolautosubmit');
      const hp = nlForm.querySelector('.hp');
      if (hp) {
        hp.removeAttribute('aria-hidden');
        hp.inert = true;
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applySemantics, { once: true });
  } else {
    applySemantics();
  }

  if (window.MutationObserver && document.body) {
    new MutationObserver(() => {
      const lang = activeLang();
      const nav = document.querySelector('nav.main');
      if (nav) nav.setAttribute('aria-label', lang === 'en' ? 'Primary' : 'Principal');
    }).observe(document.body, { attributes: true, attributeFilter: ['data-lang'] });
  }

  // ---------------------------------------------------------------------------
  // 2. Cached data loaders (lazy, signal-aware, shared by tools & form respondWith)
  // ---------------------------------------------------------------------------
  let searchRecords = null;
  let searchPromise = null;
  let peopleRecords = null;
  let peoplePromise = null;
  let timelineData = null;
  let timelinePromise = null;
  let linksMap = null;
  let linksPromise = null;

  function fetchJsonWithAbort(url, signal) {
    if (signal && signal.aborted) {
      return Promise.reject(signal.reason || new DOMException('Aborted', 'AbortError'));
    }
    return fetch(url, { signal }).then(async (r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status} fetching ${url}`);
      return r.json();
    });
  }

  function awaitWithSignal(promise, signal) {
    if (!signal) return promise;
    return new Promise((resolve, reject) => {
      if (signal.aborted) {
        reject(signal.reason || new DOMException('Aborted', 'AbortError'));
        return;
      }
      const onAbort = () => reject(signal.reason || new DOMException('Aborted', 'AbortError'));
      signal.addEventListener('abort', onAbort, { once: true });
      promise.then(
        (res) => { signal.removeEventListener('abort', onAbort); resolve(res); },
        (err) => { signal.removeEventListener('abort', onAbort); reject(err); }
      );
    });
  }

  async function loadSearchIndex(signal) {
    if (searchRecords) return searchRecords;
    if (!searchPromise) {
      searchPromise = fetch(ASSETS_URL + 'search-index.json')
        .then(async (r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status} loading search index`);
          const data = await r.json();
          for (const rec of data) {
            rec._searchable = expandVariants(
              normalize([rec.h, rec.g, rec.s, rec.x, rec.n, (rec.d || '').slice(0, 4), rec.v || '', rec.w || ''].join(' '))
            );
            rec._headline = normalize([rec.h, rec.g].join(' '));
            rec._paper = normalize(rec.n || '');
          }
          searchRecords = data;
          return data;
        })
        .catch((err) => {
          searchPromise = null;
          throw err;
        });
    }
    return awaitWithSignal(searchPromise, signal);
  }

  async function loadPeopleIndex(signal) {
    if (peopleRecords) return peopleRecords;
    if (!peoplePromise) {
      peoplePromise = fetchJsonWithAbort(ASSETS_URL + 'people-index.json')
        .then((data) => {
          for (const p of data) {
            const toks = Array.isArray(p.tokens) ? [...p.tokens] : [];
            for (const [a, b] of SEARCH_VARIANTS) {
              if (toks.includes(a) && !toks.includes(b)) toks.push(b);
              else if (toks.includes(b) && !toks.includes(a)) toks.push(a);
            }
            p._tokens = toks;
            p._haystack = expandVariants(normalize([p.name, p.dates, p.role_en, p.role_es, toks.join(' ')].join(' ')));
          }
          peopleRecords = data;
          return data;
        })
        .catch((err) => {
          peoplePromise = null;
          throw err;
        });
    }
    return awaitWithSignal(peoplePromise, signal);
  }

  async function loadTimeline(signal) {
    if (timelineData) return timelineData;
    if (!timelinePromise) {
      timelinePromise = fetchJsonWithAbort(ASSETS_URL + 'timeline-data.json')
        .then((data) => { timelineData = data; return data; })
        .catch((err) => { timelinePromise = null; throw err; });
    }
    return awaitWithSignal(timelinePromise, signal);
  }

  async function loadLinks(signal) {
    if (linksMap) return linksMap;
    if (!linksPromise) {
      linksPromise = fetchJsonWithAbort(ASSETS_URL + 'links.json?v=1')
        .then((data) => { linksMap = data || {}; return linksMap; })
        .catch(() => ({}));
    }
    return awaitWithSignal(linksPromise, signal);
  }

  async function executeArchiveSearch(params, signal) {
    const rawQuery = typeof params.query === 'string' ? params.query.trim() : '';
    const lang = params.lang === 'en' || params.lang === 'es' ? params.lang : activeLang();
    const limit = Math.max(1, Math.min(25, Number.isInteger(params.limit) ? params.limit : 10));
    const offset = Math.max(0, Number.isInteger(params.offset) ? params.offset : 0);
    const yearFrom = Number.isInteger(params.yearFrom) ? params.yearFrom : null;
    const yearTo = Number.isInteger(params.yearTo) ? params.yearTo : null;
    const era = typeof params.era === 'string' && params.era.trim() ? normalize(params.era.trim()) : null;
    const topic = typeof params.topic === 'string' && params.topic.trim() ? normalize(params.topic.trim()) : null;
    const newspaper = typeof params.newspaper === 'string' && params.newspaper.trim() ? normalize(params.newspaper.trim()) : null;
    const fullTextOnly = params.fullTextOnly === true;

    if (!rawQuery && !yearFrom && !yearTo && !era && !topic && !newspaper && !fullTextOnly) {
      return { error: 'Provide a search query or at least one filter (yearFrom, yearTo, era, topic, newspaper, or fullTextOnly).' };
    }

    const [records, people] = await Promise.all([
      loadSearchIndex(signal),
      loadPeopleIndex(signal).catch(() => []),
    ]);
    if (signal && signal.aborted) throw (signal.reason || new DOMException('Aborted', 'AbortError'));

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

      const tier = exactYear && (r.d || '').slice(0, 4) === exactYear
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

    const peopleDoors = terms.length && terms.some((t) => t.length >= 4)
      ? people
          .filter((p) => terms.every((t) => p._tokens.includes(t)))
          .slice(0, 4)
          .map((p) => ({
            slug: p.slug,
            name: p.name,
            dates: p.dates || '',
            role: (lang === 'es' ? p.role_es : p.role_en) || '',
            profileUrl: ROOT_URL + 'profile/' + encodeURIComponent(p.slug) + '.html',
          }))
      : [];

    const slice = matched.slice(offset, offset + limit).map(({ r }) => {
      const rel = recRelPath(r);
      const url = ROOT_URL + rel;
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
      returned: slice.length,
      offset,
      lang,
      peopleDoors,
      results: slice,
    };
  }

  // Expose helper for declarative search form respondWith() in app.js / search.js
  window.__usdrAgentSearch = (query, signal) => executeArchiveSearch({ query, lang: activeLang(), limit: 10 }, signal);

  // ---------------------------------------------------------------------------
  // 3. WebMCP Imperative API (document.modelContext.registerTool)
  // ---------------------------------------------------------------------------
  if (!('modelContext' in document) || !document.modelContext || typeof document.modelContext.registerTool !== 'function') {
    return;
  }

  const controller = new AbortController();
  const regOpts = { signal: controller.signal };
  window.addEventListener('pagehide', () => controller.abort(), { once: true });

  const ERROR_SCHEMA = {
    type: 'object',
    properties: { error: { type: 'string' } },
    required: ['error'],
  };

  function safeRegister(def) {
    try {
      Promise.resolve(document.modelContext.registerTool(def, regOpts)).catch(() => {});
    } catch (_) {}
  }

  // Tool 1: search_archive
  safeRegister({
    name: 'search_archive',
    description: 'Searches the Dominican Republic in the American Press newspaper archive (1820-1984). Use to find historical articles and profiled figures before reading individual articles.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Keyword, person name, newspaper title, or 4-digit year.' },
        yearFrom: { type: 'integer', minimum: 1820, maximum: 1984, description: 'Earliest publication year to include.' },
        yearTo: { type: 'integer', minimum: 1820, maximum: 1984, description: 'Latest publication year to include.' },
        era: { type: 'string', description: 'Era slug from list_sections (e.g., trujillo-era, the-american-annexation-fight).' },
        topic: { type: 'string', description: 'Topic slug from list_sections (e.g., samana-bay, diplomacy-treaties).' },
        newspaper: { type: 'string', description: 'Filter to newspapers matching this name substring.' },
        fullTextOnly: { type: 'boolean', default: false, description: 'Restrict results to articles with a full transcription.' },
        lang: { type: 'string', enum: ['es', 'en'], description: 'Preferred language for headlines and summaries.' },
        limit: { type: 'integer', minimum: 1, maximum: 25, default: 10, description: 'Maximum records to return per page.' },
        offset: { type: 'integer', minimum: 0, default: 0, description: 'Zero-based pagination offset.' },
      },
    },
    outputSchema: {
      anyOf: [
        {
          type: 'object',
          properties: {
            total: { type: 'integer' },
            returned: { type: 'integer' },
            offset: { type: 'integer' },
            lang: { type: 'string', enum: ['es', 'en'] },
            peopleDoors: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  slug: { type: 'string' },
                  name: { type: 'string' },
                  dates: { type: 'string' },
                  role: { type: 'string' },
                  profileUrl: { type: 'string' },
                },
                required: ['slug', 'name', 'profileUrl'],
              },
            },
            results: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  id: { type: 'string', description: 'Pass to get_article.' },
                  headline: { type: 'string' },
                  originalHeadline: { type: 'string' },
                  date: { type: 'string' },
                  newspaper: { type: 'string' },
                  eraSlug: { type: 'string' },
                  hasFullText: { type: 'boolean' },
                  summary: { type: 'string' },
                  url: { type: 'string' },
                  markdownUrl: { type: 'string' },
                },
                required: ['id', 'headline', 'date', 'newspaper', 'url'],
              },
            },
          },
          required: ['total', 'returned', 'offset', 'lang', 'results'],
        },
        ERROR_SCHEMA,
      ],
    },
    async execute(input = {}, { signal }) {
      try {
        return await executeArchiveSearch(input || {}, signal);
      } catch (err) {
        if (signal && signal.aborted) throw err;
        return { error: err instanceof Error ? err.message : String(err) };
      }
    },
    annotations: { readOnlyHint: true },
  });

  // Tool 2: get_article
  safeRegister({
    name: 'get_article',
    description: 'Retrieves the full metadata, Library of Congress provenance link, summary, transcription, and sibling printings for a specific archive article.',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'Record ID returned by search_archive or list_sections (e.g., cr00396-5).' },
        lang: { type: 'string', enum: ['es', 'en', 'both'], description: 'Language selection for the returned article text.' },
        includeFullText: { type: 'boolean', default: true, description: 'Whether to include the complete transcription body.' },
      },
      required: ['id'],
    },
    outputSchema: {
      anyOf: [
        {
          type: 'object',
          properties: {
            id: { type: 'string' },
            url: { type: 'string' },
            headline: { type: 'string' },
            newspaper: { type: 'string' },
            date: { type: 'string' },
            locSourceUrl: { type: 'string' },
            markdown: { type: 'string' },
            alsoRanIn: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  id: { type: 'string' },
                  newspaper: { type: 'string' },
                  date: { type: 'string' },
                  url: { type: 'string' },
                },
                required: ['id', 'newspaper', 'date', 'url'],
              },
            },
          },
          required: ['id', 'url', 'markdown'],
        },
        ERROR_SCHEMA,
      ],
    },
    async execute({ id, lang, includeFullText = true } = {}, { signal }) {
      if (typeof id !== 'string' || !/^[a-zA-Z0-9_-]{2,64}$/.test(id.trim())) {
        return { error: 'Pass a valid archive article id (for example cr00396-5).' };
      }
      const cleanId = id.trim();
      const chosenLang = lang === 'en' || lang === 'es' || lang === 'both' ? lang : activeLang();
      const articleUrl = `${ROOT_URL}articles/${encodeURIComponent(cleanId)}.html`;
      const miscUrl = `${ROOT_URL}misc/${encodeURIComponent(cleanId)}.html`;

      try {
        const query = `?lang=${chosenLang}${includeFullText === false ? '&summary=1' : ''}`;
        let targetUrl = articleUrl;
        let res = await fetch(articleUrl + query, { headers: { Accept: 'text/markdown' }, signal });
        if (res.status === 404) {
          targetUrl = miscUrl;
          res = await fetch(miscUrl + query, { headers: { Accept: 'text/markdown' }, signal });
        }
        if (!res.ok) {
          return { error: `Article "${cleanId}" was not found (HTTP ${res.status}).` };
        }
        const ct = res.headers.get('content-type') || '';
        const text = await res.text();
        let headline = '';
        let newspaper = '';
        let date = '';
        let locSourceUrl = '';
        let markdown = text;

        if (ct.includes('text/markdown')) {
          const fmMatch = /^---\n([\s\S]*?)\n---/.exec(text);
          if (fmMatch) {
            const fm = fmMatch[1];
            const pick = (k) => {
              const m = new RegExp(`^${k}:\\s*"?([^"\\n]+)"?`, 'm').exec(fm);
              return m ? m[1].trim() : '';
            };
            headline = (chosenLang === 'es' ? pick('title_es') : pick('title_en')) || pick('title');
            newspaper = pick('newspaper');
            date = pick('date');
            locSourceUrl = pick('source_url');
          }
        } else {
          const doc = new DOMParser().parseFromString(text, 'text/html');
          headline = (doc.querySelector(`.plt-h1 .l-${chosenLang === 'en' ? 'en' : 'es'}`)?.textContent || doc.querySelector('h1')?.textContent || '').trim();
          newspaper = doc.querySelector('meta[name="DC.publisher"]')?.getAttribute('content') || '';
          date = doc.querySelector('meta[name="DC.date"]')?.getAttribute('content') || '';
          locSourceUrl = doc.querySelector('meta[name="DC.source"]')?.getAttribute('content') || '';
          const summary = (doc.querySelector(`.plt-summary .l-${chosenLang === 'en' ? 'en' : 'es'}`)?.textContent || doc.querySelector('.plt-summary')?.textContent || '').trim();
          const bodyNodes = includeFullText === false ? [] : [...doc.querySelectorAll(`.plt-body p .l-${chosenLang === 'en' ? 'en' : 'es'}`)];
          const bodyText = bodyNodes.map((n) => n.textContent.trim()).filter(Boolean).join('\n\n');
          markdown = `# ${headline}\n\n${newspaper} · ${date}\nSource: ${locSourceUrl}\n\n## Summary\n\n${summary}${bodyText ? `\n\n## Full Text\n\n${bodyText}` : ''}`;
        }

        const links = await loadLinks(signal);
        const sibs = Array.isArray(links[cleanId])
          ? links[cleanId].map((s) => ({
              newspaper: s[0],
              date: s[1],
              id: s[2],
              url: `${ROOT_URL}articles/${encodeURIComponent(s[2])}.html`,
            }))
          : [];

        return {
          id: cleanId,
          url: targetUrl,
          headline,
          newspaper,
          date,
          locSourceUrl,
          markdown,
          alsoRanIn: sibs,
        };
      } catch (err) {
        if (signal && signal.aborted) throw err;
        return { error: err instanceof Error ? err.message : String(err) };
      }
    },
    annotations: { readOnlyHint: true },
  });

  // Tool 3: list_sections
  safeRegister({
    name: 'list_sections',
    description: 'Lists all historical eras, curated topics, and top-level directory pages in the archive. Use to orient navigation or discover valid era and topic slugs.',
    inputSchema: {
      type: 'object',
      properties: {
        lang: { type: 'string', enum: ['es', 'en'], description: 'Preferred language for era and topic labels.' },
      },
    },
    outputSchema: {
      anyOf: [
        {
          type: 'object',
          properties: {
            recordCount: { type: 'integer' },
            fullTextCount: { type: 'integer' },
            eras: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  slug: { type: 'string' },
                  years: { type: 'string' },
                  name: { type: 'string' },
                  blurb: { type: 'string' },
                  count: { type: 'integer' },
                  fullText: { type: 'integer' },
                  picks: { type: 'array', items: { type: 'string' } },
                  url: { type: 'string' },
                },
                required: ['slug', 'years', 'name', 'count', 'url'],
              },
            },
            topics: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  slug: { type: 'string' },
                  name: { type: 'string' },
                  url: { type: 'string' },
                },
                required: ['slug', 'name', 'url'],
              },
            },
            directories: {
              type: 'object',
              properties: {
                home: { type: 'string' },
                eras: { type: 'string' },
                papers: { type: 'string' },
                topics: { type: 'string' },
                profiles: { type: 'string' },
                glossary: { type: 'string' },
                guide: { type: 'string' },
                llmsTxt: { type: 'string' },
                mcp: { type: 'string' },
              },
            },
          },
          required: ['recordCount', 'eras', 'topics', 'directories'],
        },
        ERROR_SCHEMA,
      ],
    },
    async execute({ lang } = {}, { signal }) {
      const l = lang === 'en' || lang === 'es' ? lang : activeLang();
      try {
        const td = await loadTimeline(signal);
        return {
          recordCount: td.recordCount || 0,
          fullTextCount: td.fullText || 0,
          eras: (td.chapters || []).map((c) => ({
            slug: c.slug,
            years: c.years,
            name: l === 'en' ? c.en : c.es,
            blurb: l === 'en' ? c.blurbEn : c.blurbEs,
            count: c.count,
            fullText: c.fullText,
            picks: c.picks || [],
            url: `${ROOT_URL}era/${encodeURIComponent(c.slug)}.html`,
          })),
          topics: TOPICS.map((tp) => ({
            slug: tp.slug,
            name: l === 'en' ? tp.en : tp.es,
            url: `${ROOT_URL}topic/${encodeURIComponent(tp.slug)}-1.html`,
          })),
          directories: {
            home: ROOT_URL,
            eras: ROOT_URL + 'eras.html',
            papers: ROOT_URL + 'papers.html',
            topics: ROOT_URL + 'topics.html',
            profiles: ROOT_URL + 'profiles.html',
            glossary: ROOT_URL + 'glossary.html',
            guide: ROOT_URL + 'howto.html',
            llmsTxt: ROOT_URL + 'llms.txt',
            mcp: ROOT_URL + 'mcp',
          },
        };
      } catch (err) {
        if (signal && signal.aborted) throw err;
        return { error: err instanceof Error ? err.message : String(err) };
      }
    },
    annotations: { readOnlyHint: true },
  });

  // Tool 4: lookup_person
  safeRegister({
    name: 'lookup_person',
    description: 'Finds profiled historical figures in the archive by name or role keyword. Use to disambiguate historical people and locate their profile pages.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Person name, surname, or role keyword (e.g., Trujillo, Baez, Sumner, minister).' },
        lang: { type: 'string', enum: ['es', 'en'], description: 'Preferred language for role descriptions.' },
        limit: { type: 'integer', minimum: 1, maximum: 20, default: 8, description: 'Maximum profiles to return.' },
      },
      required: ['query'],
    },
    outputSchema: {
      anyOf: [
        {
          type: 'object',
          properties: {
            total: { type: 'integer' },
            people: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  slug: { type: 'string' },
                  name: { type: 'string' },
                  dates: { type: 'string' },
                  role: { type: 'string' },
                  articleCount: { type: 'integer' },
                  profileUrl: { type: 'string' },
                  directoryUrl: { type: 'string' },
                },
                required: ['slug', 'name', 'profileUrl'],
              },
            },
          },
          required: ['total', 'people'],
        },
        ERROR_SCHEMA,
      ],
    },
    async execute({ query, lang, limit = 8 } = {}, { signal }) {
      if (typeof query !== 'string' || !query.trim()) {
        return { error: 'Pass a non-empty person name or keyword.' };
      }
      const l = lang === 'en' || lang === 'es' ? lang : activeLang();
      const cap = Math.max(1, Math.min(20, Number.isInteger(limit) ? limit : 8));
      try {
        const people = await loadPeopleIndex(signal);
        const terms = normalize(query.trim()).split(/\s+/).filter(Boolean);
        const found = people.filter((p) => terms.every((t) => p._haystack.includes(t)));
        return {
          total: found.length,
          people: found.slice(0, cap).map((p) => ({
            slug: p.slug,
            name: p.name,
            dates: p.dates || '',
            role: (l === 'en' ? p.role_en : p.role_es) || '',
            articleCount: typeof p.n === 'number' ? p.n : 0,
            profileUrl: `${ROOT_URL}profile/${encodeURIComponent(p.slug)}.html`,
            directoryUrl: `${ROOT_URL}profiles.html#p-${encodeURIComponent(p.slug)}`,
          })),
        };
      } catch (err) {
        if (signal && signal.aborted) throw err;
        return { error: err instanceof Error ? err.message : String(err) };
      }
    },
    annotations: { readOnlyHint: true },
  });

  // Tool 5: get_current_page_context
  safeRegister({
    name: 'get_current_page_context',
    description: 'Returns structured metadata about the archive page currently open in this browser tab, including article identifiers and Library of Congress source URL when viewing an article.',
    inputSchema: { type: 'object', properties: {} },
    outputSchema: {
      type: 'object',
      properties: {
        pageType: { type: 'string' },
        lang: { type: 'string', enum: ['es', 'en'] },
        title: { type: 'string' },
        url: { type: 'string' },
        markdownUrl: { type: 'string' },
        articleId: { type: 'string' },
        newspaper: { type: 'string' },
        date: { type: 'string' },
        locSourceUrl: { type: 'string' },
      },
      required: ['pageType', 'lang', 'title', 'url'],
    },
    execute() {
      const p = location.pathname;
      let pageType = 'page';
      if (/\/us-dr\/(?:index\.html)?$/.test(p)) pageType = 'home';
      else if (/\/us-dr\/(?:articles|misc)\//.test(p)) pageType = 'article';
      else if (/\/us-dr\/(?:eras\.html|(?:era|chapter)\/)/.test(p)) pageType = 'era';
      else if (/\/us-dr\/(?:topics\.html|topic\/)/.test(p)) pageType = 'topic';
      else if (/\/us-dr\/(?:papers\.html|paper\/)/.test(p)) pageType = 'paper';
      else if (/\/us-dr\/(?:profiles\.html|profile\/)/.test(p)) pageType = 'profile';
      else if (/\/us-dr\/glossary\.html$/.test(p)) pageType = 'glossary';
      else if (/\/us-dr\/howto\.html$/.test(p)) pageType = 'guide';

      const lang = activeLang();
      const meta = (name) => document.querySelector(`meta[name="${name}"]`)?.getAttribute('content') || '';
      const out = {
        pageType,
        lang,
        title: document.title,
        url: location.href.split('#')[0],
        markdownUrl: `${location.origin}${location.pathname}?lang=${lang}`,
      };
      const dcId = meta('DC.identifier');
      if (dcId && !dcId.startsWith('http')) out.articleId = dcId;
      const pub = meta('DC.publisher');
      if (pub) out.newspaper = pub;
      const dt = meta('DC.date');
      if (dt) out.date = dt;
      const src = meta('DC.source');
      if (src) out.locSourceUrl = src;
      return out;
    },
    annotations: { readOnlyHint: true },
  });

  // Tool 6: ask_chatrd
  safeRegister({
    name: 'ask_chatrd',
    description: 'Asks the archive-grounded ChatRD research assistant a natural-language question answered strictly from the collection articles, returning cited sources.',
    inputSchema: {
      type: 'object',
      properties: {
        question: { type: 'string', description: 'Historical research question about the Dominican Republic in U.S. newspapers.' },
        lang: { type: 'string', enum: ['es', 'en'], description: 'Language for the response.' },
      },
      required: ['question'],
    },
    outputSchema: {
      anyOf: [
        {
          type: 'object',
          properties: {
            answer: { type: 'string' },
            articles: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  newspaper: { type: 'string' },
                  date: { type: 'string' },
                  url: { type: 'string' },
                },
                required: ['newspaper', 'date', 'url'],
              },
            },
          },
          required: ['answer', 'articles'],
        },
        ERROR_SCHEMA,
      ],
    },
    async execute({ question, lang } = {}, { signal }) {
      if (typeof question !== 'string' || !question.trim()) {
        return { error: 'Provide a non-empty research question.' };
      }
      const q = question.trim().slice(0, 500);
      const l = lang === 'en' || lang === 'es' ? lang : activeLang();
      let visitor = 'webmcp-agent';
      try { visitor = localStorage.getItem('chatrd-visitor') || visitor; } catch (_) {}
      try {
        const res = await fetch(CHAT_FN, {
          method: 'POST',
          headers: { Authorization: 'Bearer ' + CHAT_KEY, apikey: CHAT_KEY, 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q, history: [], visitor, page: location.pathname, lang: l }),
          signal,
        });
        const data = await res.json().catch(() => null);
        if (res.status === 429 || (data && data.error === 'rate_limited')) {
          return { error: 'ChatRD rate limit reached. Use search_archive and get_article directly or retry later.' };
        }
        if (!res.ok || !data || !data.answer) {
          return { error: `ChatRD returned HTTP ${res.status}.` };
        }
        return {
          answer: data.answer,
          articles: Array.isArray(data.articles)
            ? data.articles.map((a) => ({
                newspaper: a.newspaper || '',
                date: a.date || '',
                url: a.path ? ROOT_URL + a.path : ROOT_URL,
              }))
            : [],
        };
      } catch (err) {
        if (signal && signal.aborted) throw err;
        return { error: err instanceof Error ? err.message : String(err) };
      }
    },
    annotations: { readOnlyHint: true, untrustedContentHint: false },
  });

  // Tool 7: set_language (simple UI preference action — omit outputSchema per guide)
  safeRegister({
    name: 'set_language',
    description: 'Switches the active reading language of the current archive page.',
    inputSchema: {
      type: 'object',
      properties: {
        lang: { type: 'string', enum: ['es', 'en'], description: 'Target interface and content language.' },
      },
      required: ['lang'],
    },
    execute({ lang } = {}) {
      if (lang !== 'es' && lang !== 'en') {
        return { error: 'Choose "es" or "en".' };
      }
      if (typeof window.applyLang === 'function') window.applyLang(lang);
      else if (typeof window.setLang === 'function') window.setLang(lang);
      else {
        document.body.dataset.lang = lang;
        document.documentElement.lang = lang;
      }
      return { lang: activeLang(), title: document.title };
    },
    annotations: { readOnlyHint: false },
  });
})();
