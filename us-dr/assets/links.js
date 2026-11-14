/* Article cross-printing links (2026-11-14): on article pages whose
   record has DIRECT tier-1 sibling printings (the same dispatch carried
   by another newspaper, detected and audited in
   review/KNOWLEDGE-EXPANSION-2026-11-14/links/REPORT.md), render one
   quiet line under the citation: "This dispatch also ran in ..." with
   one link per sibling, at most four, earliest first.
   Data: assets/links.json (per record: [paper, ISO date, sibling id]).
   The line uses the site's paired l-en/l-es spans, so it follows the
   page's body[data-lang] state through the shipped stylesheet, live on
   toggle, with no script-side language handling. If the data cannot be
   loaded, or the record has no siblings, the page is left exactly as
   shipped: no element is inserted and nothing else runs. */
(function () {
  try {
    var fact = document.querySelector('article.page .plt-factline');
    if (!fact || document.querySelector('.plt-alsoran')) return;
    var m = /\/articles\/([^\/]+)\.html$/.exec(location.pathname);
    if (!m) return;
    var rid = m[1];
    var s = document.querySelector('script[src*="chatrd.js"]');
    if (!s) return;
    var base = s.src.replace(/chatrd\.js(?:\?.*)?$/, '');
    if (!base) return;
    var root = base.replace(/assets\/$/, '');
    fetch(base + 'links.json?v=1')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        var sibs = data[rid];
        if (!sibs || !sibs.length) return;
        fact.parentNode.insertBefore(build(root, sibs), fact.nextSibling);
      })
      .catch(function () {});
  } catch (_) {}

  var MONTHS = {
    en: ['January', 'February', 'March', 'April', 'May', 'June', 'July',
         'August', 'September', 'October', 'November', 'December'],
    es: ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
  };
  var LEAD = {
    en: 'This dispatch also ran in ',
    es: 'Este despacho también se publicó en '
  };

  function fmtDate(iso, lang) {
    var p = iso.split('-');
    var y = p[0], mo = parseInt(p[1], 10), d = parseInt(p[2], 10);
    if (lang === 'en') return MONTHS.en[mo - 1] + ' ' + d + ', ' + y;
    return d + ' de ' + MONTHS.es[mo - 1] + ' de ' + y;
  }

  function span(root, sibs, lang) {
    var el = document.createElement('span');
    el.className = 'l-' + lang;
    el.appendChild(document.createTextNode(LEAD[lang]));
    sibs.forEach(function (sib, i) {
      if (i > 0) el.appendChild(document.createTextNode(' · '));
      var a = document.createElement('a');
      a.href = root + 'articles/' + sib[2] + '.html';
      a.textContent = sib[0] + ', ' + fmtDate(sib[1], lang);
      el.appendChild(a);
    });
    return el;
  }

  function build(root, sibs) {
    var p = document.createElement('p');
    p.className = 'plt-alsoran';
    p.appendChild(span(root, sibs, 'en'));
    p.appendChild(span(root, sibs, 'es'));
    return p;
  }
})();
