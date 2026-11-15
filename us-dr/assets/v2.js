/* V2 motion layer — one system, tiered.
   Tier A/B: progress hairline, one-shot group reveals, rail progress.
   Tier C (prefers-reduced-motion or save-data): this script adds no
   states at all; the page is complete and still. No-JS is the same.
   Deterministic: identical on every load. Transform/opacity only. */
(function () {
  var mq = window.matchMedia;
  var reduced = mq && mq("(prefers-reduced-motion: reduce)").matches;
  var saveData = !!(navigator.connection && navigator.connection.saveData);
  if (reduced || saveData) return;

  /* page progress hairline */
  var bar = document.createElement("div");
  bar.className = "v2-prog";
  bar.setAttribute("aria-hidden", "true");
  bar.innerHTML = "<i></i>";
  document.body.appendChild(bar);
  var fill = bar.firstChild;
  var ticking = false;
  function upd() {
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    var p = max > 0 ? (h.scrollTop || document.body.scrollTop) / max : 0;
    fill.style.transform = "scaleX(" + p + ")";
    ticking = false;
  }
  window.addEventListener("scroll", function () {
    if (!ticking) { ticking = true; requestAnimationFrame(upd); }
  }, { passive: true });
  upd();

  /* one-shot group reveals: section heads, subheads, plates, hero, cast.
     Moments cards are not individually animated; the river is the motion.
     Sections convergence (2026-11-14): the same reveals extend to the
     Glossary, Newspapers, Guide and Topics sections — their own heads
     and groups (.g-sec, .g-quote, .state-h, .topic-group-h, .entry,
     .v2-pageh) and the profile pages' body heads. Every added selector
     matches nothing on era pages, so era behavior is unchanged.
     Newspapers state wall (2026-11-14): the directory's state cards
     (.scard) reveal the same way; the class exists only on papers.html. */
  var targets = document.querySelectorAll(
    ".sec-head, .era-subhead, figure.plate, .v2-hero, .v2-cast, " +
    ".g-sec, .g-quote, .state-h, .topic-group-h, .entry, .v2-pageh, .scard, " +
    ".page.profile .body h2");
  targets.forEach(function (el) { el.classList.add("v2r"); });
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (x) {
        if (x.isIntersecting) { x.target.classList.add("in"); io.unobserve(x.target); }
      });
    }, { threshold: 0.12 });
    targets.forEach(function (el) { io.observe(el); });
  } else {
    targets.forEach(function (el) { el.classList.add("in"); });
  }

  /* Moments rail progress hairlines */
  document.querySelectorAll(".v2-rail").forEach(function (rail) {
    var prog = rail.nextElementSibling;
    if (!prog || !prog.classList.contains("v2-railprog")) return;
    var f = prog.firstChild, rt = false;
    function ru() {
      var m = rail.scrollWidth - rail.clientWidth;
      var p = m > 0 ? rail.scrollLeft / m : 0;
      f.style.transform = "scaleX(" + Math.max(p, 0.05) + ")";
      rt = false;
    }
    rail.addEventListener("scroll", function () {
      if (!rt) { rt = true; requestAnimationFrame(ru); }
    }, { passive: true });
    ru();
  });
})();
