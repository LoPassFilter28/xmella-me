/* ChatRD widget for "DR in the American Press / RD en la Prensa
   Norteamericana". Drop-in: one stylesheet link + this script tag.
   Adapted from the ChatFYI widget (407 FYI, deployment-12 pattern):
   corner button, panel, message flow, suggestion chips rendered from
   the function's cited records, visitor id in localStorage, thinking
   state, soft-opening notice. Differences: the widget builds its own
   DOM (ChatFYI's markup lived in the page), its strings are bilingual
   and follow the site's language state (body[data-lang], Spanish by
   default), and its chips link to archive article pages, resolved
   against the branch root derived from this script's own URL.
   Talks to the ChatRD Supabase edge function; answers come only from
   the archive's records. */
(() => {
  if (window.__chatrdLoaded) return;
  window.__chatrdLoaded = true;

  // Ship-day values, replaced at deploy time (same placeholder pattern
  // as ChatFYI's __CHAT_KEY__).
  const FN = 'https://xxdgxigwpnezsdvbiawi.supabase.co/functions/v1/chatrd';   // e.g. https://<project>.supabase.co/functions/v1/chatrd
  const KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh4ZGd4aWd3cG5lenNkdmJpYXdpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE2OTM0MDYsImV4cCI6MjEwNzI2OTQwNn0.3fuj9vjXspT31fQhgcejf4Thmk9yHPc7RSBZ0v97Gw4';

  // Branch root: this script is served from <root>assets/chatrd.js, so
  // article paths ("articles/<id>.html") resolve from the script URL,
  // whatever depth the host page sits at.
  const scriptSrc = (document.currentScript && document.currentScript.src) || '';
  const ROOT = scriptSrc.replace(/assets\/chatrd\.js(\?.*)?$/, '') || './';

  const STR = {
    es: {
      title: 'ChatRD',
      sub: 'Respuestas solo de los artículos de este archivo.',
      greet: 'Pregunta por un año, un tema o un periódico.',
      placeholder: 'Pregunta por un año, un tema, un periódico...',
      send: 'Enviar',
      thinking: 'Buscando en el archivo...',
      error: 'Algo falló de mi lado. La cronología de esta página puede ayudarte, o inténtalo de nuevo en un momento.',
      ratelimit_retry_min: 'ChatRD llegó a su límite de uso. La espera indicada es de unos {N} minutos; vuelve a intentarlo pasado ese tiempo.',
      ratelimit_retry_hr: 'ChatRD llegó a su límite de uso. La espera indicada es de unas {H} horas; vuelve a intentarlo pasado ese tiempo.',
      ratelimit_day: 'ChatRD llegó a su límite diario de uso. El límite se renueva en unas {H} horas.',
      ratelimit_minute: 'ChatRD llegó a su límite de uso por minuto. La espera es de unos 2 minutos.',
      ratelimit_fallback: 'ChatRD llegó a su límite de uso y no puede responder ahora. Vuelve a intentarlo en unos 15 minutos.',
      close: 'Cerrar el chat',
      open: 'Abrir ChatRD',
    },
    en: {
      title: 'ChatRD',
      sub: 'Answers only from this archive\'s articles.',
      greet: 'Ask about a year, a topic, or a newspaper.',
      placeholder: 'Ask about a year, a topic, a newspaper...',
      send: 'Send',
      thinking: 'Searching the archive...',
      error: 'Something went wrong on my end. The timeline on this page can still help, or try me again in a moment.',
      ratelimit_retry_min: 'ChatRD has reached its usage limit. The indicated wait is about {N} minutes; please try again after that.',
      ratelimit_retry_hr: 'ChatRD has reached its usage limit. The indicated wait is about {H} hours; please try again after that.',
      ratelimit_day: 'ChatRD has reached its daily usage limit. The limit resets in about {H} hours.',
      ratelimit_minute: 'ChatRD has reached its per-minute usage limit. The wait is about 2 minutes.',
      ratelimit_fallback: 'ChatRD has reached its usage limit and can\'t respond right now. Please try again in about 15 minutes.',
      close: 'Close chat',
      open: 'Open ChatRD',
    },
  };
  const MONTHS = {
    en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
    es: ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'],
  };

  function siteLang() {
    const l = (document.body && document.body.dataset.lang) ||
      (() => { try { return localStorage.getItem('xm-lang'); } catch (e) { return null; } })();
    return l === 'en' ? 'en' : 'es';
  }
  let lang = siteLang();
  const S = () => STR[lang];

  // ------------------------------------------------------------- DOM
  const btn = document.createElement('button');
  btn.className = 'crd-chat-btn';
  btn.setAttribute('aria-haspopup', 'dialog');
  btn.setAttribute('aria-expanded', 'false');
  btn.innerHTML = '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg><span class="crd-chat-btn-label">ChatRD</span>';

  const panel = document.createElement('section');
  panel.className = 'crd-chat-panel';
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', 'ChatRD');
  panel.innerHTML =
    '<div class="crd-chat-head"><div>' +
    '<h2 class="crd-chat-title"></h2><p class="crd-chat-sub"></p></div>' +
    '<button class="crd-chat-close" type="button">&times;</button></div>' +
    '<div class="crd-chat-msgs"></div>' +
    '<form class="crd-chat-form"><input class="crd-chat-input" type="text" autocomplete="off" maxlength="500">' +
    '<button class="crd-chat-send" type="submit"></button></form>';

  document.body.appendChild(btn);
  document.body.appendChild(panel);

  const msgs = panel.querySelector('.crd-chat-msgs');
  const form = panel.querySelector('.crd-chat-form');
  const input = panel.querySelector('.crd-chat-input');
  const send = panel.querySelector('.crd-chat-send');
  const closeBtn = panel.querySelector('.crd-chat-close');

  function applyStrings() {
    panel.querySelector('.crd-chat-title').textContent = S().title;
    panel.querySelector('.crd-chat-sub').textContent = S().sub;
    input.placeholder = S().placeholder;
    input.setAttribute('aria-label', S().placeholder);
    send.textContent = S().send;
    closeBtn.setAttribute('aria-label', S().close);
    btn.setAttribute('aria-label', S().open);
  }
  applyStrings();

  // Follow the site's language toggle live (the site sets
  // body[data-lang] and stores xm-lang; theme needs no JS: the CSS
  // tokens switch with body[data-theme] on their own).
  if (window.MutationObserver && document.body) {
    new MutationObserver(() => {
      const l = siteLang();
      if (l !== lang) { lang = l; applyStrings(); }
    }).observe(document.body, { attributes: true, attributeFilter: ['data-lang'] });
  }

  // ---------------------------------------------------------- state
  let opened = false, busy = false, noticeShown = false;
  const history = [];
  let visitor = '';
  try {
    visitor = localStorage.getItem('chatrd-visitor') || '';
    if (!visitor) {
      visitor = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(36).slice(2));
      localStorage.setItem('chatrd-visitor', visitor);
    }
  } catch (e) { visitor = 'anon'; }
  const track = (name) => { try { if (window.captureEvent) captureEvent(name, {}); else if (window.posthog) posthog.capture(name); } catch (e) {} };
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (s) => s.split(/\n\s*\n/).map((para) => '<p>' + esc(para)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/^\s*[-*]\s+/gm, '• ')
    .replace(/\n/g, '<br>') + '</p>').join('');
  function fmtDate(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
    if (!m) return iso || '';
    const y = +m[1], mo = +m[2], d = +m[3];
    return lang === 'es' ? `${d} de ${MONTHS.es[mo - 1]} de ${y}` : `${MONTHS.en[mo - 1]} ${d}, ${y}`;
  }
  function addMsg(cls, text) {
    const d = document.createElement('div');
    d.className = 'crd-chat-msg ' + cls;
    d.innerHTML = fmt(text);
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
    return d;
  }
  function addChips(articles) {
    if (!articles || !articles.length) return;
    const row = document.createElement('div');
    row.className = 'crd-chat-chips';
    for (const a of articles) {
      const link = document.createElement('a');
      link.className = 'crd-chat-chip';
      link.href = ROOT + a.path;
      link.innerHTML = esc(a.newspaper) + ' <small>' + esc(fmtDate(a.date)) + '</small>';
      row.appendChild(link);
    }
    msgs.appendChild(row);
    msgs.scrollTop = msgs.scrollHeight;
  }
  function toggle(open) {
    panel.classList.toggle('open', open);
    btn.setAttribute('aria-expanded', String(open));
    if (open) {
      if (!opened) {
        opened = true;
        addMsg('bot', S().greet);
        track('chatrd_open');
      }
      setTimeout(() => input.focus(), 60);
    }
  }
  btn.addEventListener('click', () => toggle(!panel.classList.contains('open')));
  closeBtn.addEventListener('click', () => toggle(false));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && panel.classList.contains('open')) toggle(false); });
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q || busy) return;
    busy = true; send.disabled = true; input.value = '';
    addMsg('user', q);
    history.push({ role: 'user', text: q });
    const thinking = addMsg('bot thinking', S().thinking);
    // One POST attempt, with its own 30 s timeout. Any failure to
    // obtain a usable answer (network error, abort/timeout, bad
    // status or body) throws to the caller.
    async function postChat() {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 30000);
      try {
        const r = await fetch(FN, {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + KEY, 'apikey': KEY, 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q, history: history.slice(0, -1).slice(-6), visitor, page: location.pathname }),
          signal: ctrl.signal,
        });
        const data = await r.json();
        // The function's structured rate limit (HTTP 429, error code
        // rate_limited) is a result, not a failure: it returns as a
        // sentinel so the caller renders the prepared note and does
        // NOT spend the one retry on it — retrying is the reader's
        // own next move, never an automatic loop. The sentinel carries
        // the variant and the concrete wait the function computed from
        // the provider's own error (Revision 2, 2026-11-03); a 429
        // without those fields (an older function build) renders the
        // fallback note.
        if (r.status === 429 || (data && data.error === 'rate_limited')) {
          return {
            rate_limited: true,
            variant: (data && data.variant) || 'fallback',
            display_value: data && data.display_value,
            display_unit: data && data.display_unit,
          };
        }
        if (!r.ok || !data.answer) throw new Error('bad response');
        return data;
      } finally {
        clearTimeout(timer);
      }
    }
    try {
      let data;
      try {
        data = await postChat();
      } catch (firstErr) {
        // Exactly one retry after a short delay: the edge function's
        // cold start made first attempts fail in live testing
        // (2026-11-03) while an immediate re-ask succeeded. A second
        // failure falls through to the error message below.
        await new Promise((res) => setTimeout(res, 1200));
        data = await postChat();
      }
      thinking.remove();
      if (data.rate_limited) {
        // Calm system note in the page's current language — not a
        // fake assistant answer, not a raw error. It carries the
        // concrete wait the function computed from the provider's own
        // error response (Revision 2): the provider's indicated delay,
        // the hours to the daily reset, or the approved fixed waits
        // for the per-minute and unparseable cases. Nothing is added
        // to the conversation history, and the input stays enabled so
        // the reader can ask again when they choose.
        const s = S();
        let noteText;
        if (data.variant === 'retry' && data.display_unit === 'hours') {
          noteText = s.ratelimit_retry_hr.replace('{H}', data.display_value);
        } else if (data.variant === 'retry') {
          noteText = s.ratelimit_retry_min.replace('{N}', data.display_value);
        } else if (data.variant === 'day') {
          noteText = s.ratelimit_day.replace('{H}', data.display_value);
        } else if (data.variant === 'minute') {
          noteText = s.ratelimit_minute;
        } else {
          noteText = s.ratelimit_fallback;
        }
        const n = document.createElement('div');
        n.className = 'crd-chat-note';
        n.textContent = noteText;
        msgs.appendChild(n);
        msgs.scrollTop = msgs.scrollHeight;
        track('chatrd_rate_limited');
      } else {
        if (data.notice && !noticeShown) {
          noticeShown = true;
          const n = document.createElement('div');
          n.className = 'crd-chat-note';
          n.textContent = data.notice;
          msgs.appendChild(n);
        }
        addMsg('bot', data.answer);
        addChips(data.articles);
        history.push({ role: 'assistant', text: data.answer });
        track('chatrd_question');
      }
    } catch (err) {
      thinking.remove();
      addMsg('bot', S().error);
    }
    busy = false; send.disabled = false; input.focus();
  });
})();
