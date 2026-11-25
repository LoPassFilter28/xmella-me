// On-demand Markdown content negotiation for xmella.me/us-dr/*
// Triggered ONLY when requests carry `Accept: text/markdown` (human
// browsers hitting Accept: text/html go directly to Vercel's static CDN).
import {
  AGENT_LINK_HEADER,
  SITE_ORIGIN,
  fetchStaticAsset,
  renderArticleMarkdown,
  renderGenericPageMarkdown,
  renderHomeMarkdown,
  renderNotFoundMarkdown,
} from './_usdr-md.mjs';

function normalizePath(raw) {
  if (typeof raw !== 'string') return null;
  const clean = raw.split('?')[0].split('#')[0].trim();
  if (!clean.startsWith('/us-dr')) return null;
  if (clean.includes('..') || clean.includes('\\') || /[\x00-\x1f]/.test(clean)) return null;
  return clean === '/us-dr' ? '/us-dr/' : clean;
}

function pickLang(url) {
  const q = (url.searchParams.get('lang') || '').toLowerCase();
  if (q === 'en' || q === 'es' || q === 'both') return q;
  return 'both';
}

function mdResponse(body, status = 200, cache = true) {
  const headers = {
    'Content-Type': 'text/markdown; charset=utf-8',
    Vary: 'Accept',
    'X-Content-Type-Options': 'nosniff',
    Link: AGENT_LINK_HEADER,
    'Cache-Control': cache
      ? 'public, max-age=0, s-maxage=3600, stale-while-revalidate=86400'
      : 'public, max-age=0, s-maxage=300',
  };
  return new Response(body, { status, headers });
}

export async function GET(request) {
  const url = new URL(request.url);
  const reqPath = normalizePath(url.searchParams.get('path') || '/us-dr/');
  if (!reqPath) {
    return mdResponse(renderNotFoundMarkdown(url.pathname), 404, false);
  }

  const lang = pickLang(url);
  const summaryOnly = url.searchParams.get('summary') === '1' || url.searchParams.get('summary') === 'true';

  if (url.searchParams.get('notfound') === '1') {
    return mdResponse(renderNotFoundMarkdown(reqPath), 404, false);
  }

  try {
    // Rich Markdown overview for /us-dr/ homepage
    if (reqPath === '/us-dr/' || reqPath === '/us-dr/index.html') {
      const tdRes = await fetchStaticAsset(request.url, '/us-dr/assets/timeline-data.json');
      const td = tdRes.ok ? await tdRes.json().catch(() => null) : null;
      return mdResponse(renderHomeMarkdown(td, lang), 200, true);
    }

    const fetchPath = reqPath.endsWith('/') ? `${reqPath}index.html` : reqPath;
    const upstream = await fetchStaticAsset(request.url, fetchPath);
    if (upstream.status === 404) {
      return mdResponse(renderNotFoundMarkdown(reqPath), 404, false);
    }
    if (!upstream.ok) {
      console.error('us-dr markdown upstream error', { reqPath, status: upstream.status });
      return mdResponse(`# Error\n\nUnable to retrieve \`${reqPath}\` (HTTP ${upstream.status}).\n`, 502, false);
    }

    const html = await upstream.text();
    const canonicalUrl = `${SITE_ORIGIN}${reqPath}`;
    const isArticle = /^\/us-dr\/(?:articles|misc)\/[^/]+\.html$/i.test(reqPath);
    const md = isArticle
      ? renderArticleMarkdown(html, canonicalUrl, { lang, summaryOnly })
      : renderGenericPageMarkdown(html, canonicalUrl, { lang });

    return mdResponse(md, 200, true);
  } catch (err) {
    console.error('us-dr markdown handler failed', { reqPath, error: err instanceof Error ? err.message : String(err) });
    return mdResponse(`# Service Error\n\nFailed to render Markdown for \`${reqPath}\`.\n`, 500, false);
  }
}

export async function HEAD(request) {
  const res = await GET(request);
  return new Response(null, { status: res.status, headers: res.headers });
}
