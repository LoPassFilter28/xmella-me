/* Home search machinery (us-dr/index.html).
   Split from the original app.js on 2026-11-10 (Eras Split amendment):
   the timeline scene, rail and evidence moved to the Eras hub and
   live in assets/timeline.js; this file keeps the search wrap, panel
   and index loading. Search no longer waits for timeline-data.json:
   the original renderSearch() guard on that feed is gone, so the home
   search stands on the search/people indexes alone.
   2026-11-10 (HOME-FIX A): the timeline module's leftover string
   entries are removed from STRINGS below — the executable module was
   already gone, but a stale cached copy of the PRE-split app.js
   paired with the post-split home page in production (PostHog,
   Nov 10 14:44 UTC: '$('#previous-year').addEventListener' on null,
   old app.js line 67). index.html now loads this file under a
   versioned URL and redirects ?year= visits to the hub before this
   module runs, so the stale pairing cannot recur. */
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const STRINGS={
 search:['Buscar','Search'],records:['registros','records'],record:['registro','record'],loadMore:['Ver más','Show more'],searchResults:['Resultados de búsqueda','Search results'],originalTitle:['Título original en inglés','Original title in English'],fullAvailable:['Transcripción disponible','Transcription available'],noResults:['No encontramos registros. Prueba otro nombre, periódico o año.','No records found. Try another name, newspaper or year.'],closeSearch:['Cerrar búsqueda','Close search'],loading:['Cargando…','Loading…'],loadError:['No pudimos cargar los registros. Recarga la página.','We could not load the records. Reload the page.'],searchInAll:['Buscar en todos los registros','Search all records'],profileLabel:['Perfil','Profile']
};
let lang=document.body.dataset.lang==='en'?'en':'es',theme=document.body.dataset.theme==='dark'?'dark':'light';
let records=[],searchLimit=15,searchTimer,indexLoaded=false,indexFailed=false,indexLoading=false,indexPromise=null,people=[],peopleRequested=false;
const t=k=>STRINGS[k]?.[lang==='es'?0:1]||k;
const fmt=n=>new Intl.NumberFormat(lang==='es'?'es-DO':'en-US').format(n);
const date=d=>new Intl.DateTimeFormat(lang==='es'?'es-DO':'en-US',{year:'numeric',month:'long',day:'numeric',timeZone:'UTC'}).format(new Date(d+'T12:00:00Z'));
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const countText=n=>`${fmt(n)} ${t(n===1?'record':'records')}`;
const normalize=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
/* F-04 dedupe (flow-fix Batch 1): when a card's summary opens with its headline, print the summary from its second sentence. Abbreviation-aware sentence split; single-sentence summaries keep their text. Mirrors review/FLOW-FIX-BATCHES-2026-11-09/batch1/dedupe.py. */
const ABBREV=new Set(['st','mr','mrs','ms','dr','sr','jr','u.s','u.s.a','no','vol','pp','gen','sen','rep','capt','lt','col','sgt','rev','hon','inc','co','ave','jan','feb','mar','apr','jun','jul','aug','sep','sept','oct','nov','dec','e.g','i.e','vs','al','mt','ft','p.m','a.m']);
const normTxt=s=>String(s??'').replace(/\*/g,'').replace(/\s+/g,' ').trim().toLowerCase();
function splitFirst(s){const re=/[.!?]+(?=\s|$)/g;let m;while((m=re.exec(s))){if(s[m.index]==='.'){let j=m.index;while(j>0&&/[A-Za-z.]/.test(s[j-1]))j--;const w=s.slice(j,m.index).toLowerCase();if(ABBREV.has(w)||w.length===1)continue;}const end=m.index+m[0].length;return [s.slice(0,end).trim(),s.slice(end).trim()];}return [s.trim(),''];}
function dedupeSummary(headline,summary){const s=String(summary??'').trim();const h=normTxt(headline).replace(/\s*…\s*$/,'');if(!s||!h||!normTxt(s).startsWith(h))return s;const [f,rest]=splitFirst(s);return (rest.length>=40&&normTxt(f).startsWith(h))?rest:s;}
/* HOME-FIX E (2026-11-10): a result row carries a short subtext, not
   the whole summary — the record's own opening words, cut at a word
   boundary with an ellipsis (the people-door role cut at 120 is the
   house precedent). The full summary lives on the article page. */
const shortSummary=s=>{s=String(s??'').trim();return s.length>120?s.slice(0,120).replace(/\s+\S*$/,'')+'…':s;};
const recURL=r=>r.m?`misc/${encodeURIComponent(r.i)}.html`:`articles/${encodeURIComponent(r.i)}.html`; /* GRAFT P1: relative article links (was absolute xmella.me URL) */
function applyLanguage(){
 document.documentElement.lang=lang;document.body.dataset.lang=lang;document.title=(lang==='en'?document.documentElement.dataset.titleEn:document.documentElement.dataset.titleEs)||document.title;
 $$('[data-i18n]').forEach(el=>el.innerHTML=t(el.dataset.i18n));$$('[data-placeholder]').forEach(el=>el.placeholder=t(el.dataset.placeholder));
 /* The timeline's own labels live in the hub's timeline.js. */
 [['#search','searchInAll'],['#close-search','closeSearch']].forEach(([sel,key])=>$(sel).setAttribute('aria-label',t(key)));
 $$('img[data-en-alt]').forEach(el=>el.alt=el.dataset[lang+'Alt']);
 renderSearch();
}

function applyTheme(){document.body.dataset.theme=theme;}
function renderSearch(){if(!indexLoaded){$('#search-count').textContent='';$('#search-results').innerHTML=indexFailed?`<p class="empty-message">${t('loadError')}</p>`:indexLoading?`<p class="empty-message">${t('loading')}</p>`:'';$('#search-more').hidden=true;return;}const q=normalize($('#search').value.trim());const terms=q.split(/\s+/).filter(Boolean);const found=records.filter(r=>terms.every(s=>r.searchable.includes(s))).map(r=>({r,tier:(()=>{const yq=/^\d{4}$/.test($('#search').value.trim())?$('#search').value.trim():null;return yq&&r.d.slice(0,4)===yq?-1:(terms.length>0&&terms.every(s=>r.paperSearch.includes(s)))?0:((terms.length>0&&terms.every(s=>r.headlineSearch.includes(s)))?1:2)})()})).sort((a,b)=>a.tier-b.tier||(a.tier===0&&b.tier===0&&a.r.n!==b.r.n?a.r.n.localeCompare(b.r.n):0)||b.r.d.localeCompare(a.r.d));$('#search-count').textContent=countText(found.length);/* F-05 (flow-fix Batch 2): a name that belongs to a profiled person opens a door to that person first — name + dates + role line — so two people who share a name are told apart before the article list begins. */
const doors=(terms.length&&terms.some(s=>s.length>=4))?people.filter(p=>terms.every(s=>p.tokens.includes(s))).slice(0,4):[];
const doorHtml=doors.map(p=>{const role=(lang==='es'?p.role_es:p.role_en)||'';const roleCut=role.length>120?role.slice(0,120).replace(/\s+\S*$/,'')+'…':role;return `<a class="search-result person-door" href="profiles.html#p-${p.slug}"><small>${t('profileLabel')}</small><strong>${esc(p.name)}${p.dates?` · ${esc(p.dates)}`:''}</strong><small>${esc(roleCut)}</small></a>`;}).join('');
$('#search-results').innerHTML=doorHtml+(found.length?(()=>{let lastPaper='';return found.slice(0,searchLimit).map(x=>{const r=x.r;const translated=lang==='es'&&r.x!==r.s;const headline=(lang==='es'&&r.g)?r.g:r.h;const summary=shortSummary(dedupeSummary(translated?(r.g||r.h):r.h,translated?r.x:r.s));const bits=[r.o===1?t('originalTitle'):null,r.f?t('fullAvailable'):null].filter(Boolean).join(' · ');return `<a class="search-result" href="${recURL(r)}"><small>${esc(r.n)} · ${esc(date(r.d))}</small><strong lang="${lang==='es'&&r.g?'es':'en'}">${esc(headline)}</strong><small class="search-summary" lang="${translated?'es':'en'}">${esc(summary)}</small><small>${bits}</small></a>`;}).join('');})():(doors.length?'':`<p class="empty-message">${t('noResults')}</p>`));$('#search-more').hidden=found.length<=searchLimit;}
/* ONE BUILDER PASS (2026-11-07): the section's own preference buttons are gone; the masthead toggle is the site's one toggle design. The search follows the shared body state the masthead flips (and that applyLanguage/applyTheme write back with the same values, so this observer never loops). */new MutationObserver(()=>{const L=document.body.dataset.lang,T=document.body.dataset.theme;if((L==='es'||L==='en')&&L!==lang){lang=L;applyLanguage()}if((T==='light'||T==='dark')&&T!==theme){theme=T;applyTheme()}}).observe(document.body,{attributes:true,attributeFilter:['data-lang','data-theme']});
$('#search').addEventListener('input',()=>{ensureIndex();clearTimeout(searchTimer);searchTimer=setTimeout(()=>{searchLimit=15;$('#search-panel').hidden=false;renderSearch()},120)});$('#search').addEventListener('focus',()=>{ensureIndex();if($('#search').value){$('#search-panel').hidden=false;renderSearch()}});/* GRAFT P5: topic/full filter listeners removed with their controls */$('#search-more').addEventListener('click',()=>{searchLimit+=20;renderSearch()});$('#close-search').addEventListener('click',()=>{$('#search-panel').hidden=true;$('#search').blur()});
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();$('#search').focus()}if(e.key==='Escape'){$('#search-panel').hidden=true;$('#search').blur()}});document.addEventListener('click',e=>{if(!e.target.closest('#search-panel')&&!e.target.closest('.search-wrap'))$('#search-panel').hidden=true});
applyLanguage();applyTheme();if(new URL(location.href).searchParams.get('buscar')){ensureIndex();$('#search')?.focus();}const _q=new URL(location.href).searchParams.get('q');if(_q){const _si=$('#search');if(_si){_si.value=_q;ensureIndex();$('#search-panel').hidden=false;renderSearch();}}
/* F9 LAZY SEARCH INDEX (2026-11-07): the ~8 MB search index is not fetched at boot. ensureIndex() loads it once — on the first focus/input on #search, or immediately when the URL carries ?buscar=1 — and indexPromise is the single-flight guard: concurrent triggers share one fetch, and a failure clears the guard so the next interaction retries. F12 (2026-11-07) restricted the haystack to the visible headline + summaries; the 2026-11-08 ruling reverses it for two fields: the haystack is now headline + summaries + newspaper name + the record's year (h + s + x + n + year), and newspaper-name matches form their own labeled tier in renderSearch. Place and topic labels/keys still do not match. (Split note: the original also re-rendered the evidence list from here; the evidence list lives on the Eras hub now, in timeline.js.) */
function ensureIndex(){if(!peopleRequested){peopleRequested=true;fetch('assets/people-index.json').then(async rr=>{if(rr.ok){people=await rr.json();if(indexLoaded)renderSearch();}}).catch(()=>{});}if(indexLoaded)return Promise.resolve();if(indexPromise)return indexPromise;indexLoading=true;indexFailed=false;renderSearch();indexPromise=fetch('assets/search-index.json').then(async rr=>{if(!rr.ok)throw Error('index unavailable');records=await rr.json();records.forEach(r=>{r.searchable=normalize([r.h,r.s,r.x,r.n,(r.d||'').slice(0,4),r.v||'',r.w||''].join(' '));r.headlineSearch=normalize(r.h||'');r.paperSearch=normalize(r.n||'')});indexLoaded=true;indexLoading=false;renderSearch();}).catch(()=>{indexFailed=true;indexLoading=false;indexPromise=null;renderSearch();});return indexPromise;}
document.body.dataset.ready='true';
