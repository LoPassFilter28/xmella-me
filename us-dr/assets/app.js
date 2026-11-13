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
/* SEARCH RESULTS (2026-11-10): an article row carries the first
   sentence of the record's summary in the active language, not a
   truncated summary. The sentence reader is abbreviation-aware in
   both languages (titles, months, initials and dotted or spaced
   initialisms), handles decimals, closing quotation marks and
   brackets, ellipses, and preserves Spanish inverted opening marks
   as part of the sentence they open. When the stored summary offers
   no clean sentence break, the row falls back to the established
   120-character word-boundary cut. */
const ABBREV=new Set(['st','mr','mrs','ms','dr','sr','jr','u.s','u.s.a','no','vol','pp','gen','sen','rep','capt','lt','col','sgt','rev','hon','inc','co','ave','jan','feb','mar','apr','jun','jul','aug','sep','sept','oct','nov','dec','e.g','i.e','vs','al','mt','ft','p.m','a.m']);
const SENTENCE_ABBREV=new Set([...ABBREV,'sra','sres','srta','dra','lic','ing','arq','gral','fig','pag','pág','num','núm','aprox','dept','dist','est','gob','pres','prof','d.c']);
const SENTENCE_STARTERS=new Set(['the','this','that','it','he','she','they','we','there','here','but','and','yet','so','then','later','after','before','in','on','at','as','by','for','from','with','when','while','if','although','however','meanwhile','finally','el','la','los','las','este','esta','esto','ese','esa','eso','pero','luego','después','entonces','finalmente','sin']);
const SENTENCE_CLOSERS=new Set(['"','\'','”','’','»','›',')',']','}','*']);
const shortSummary=s=>{s=String(s??'').trim();return s.length>120?s.slice(0,120).replace(/\s+\S*$/,'')+'…':s;};
function firstSentence(summary){
 const s=String(summary??'').replace(/\s+/g,' ').trim();
 if(!s)return {text:'',fallback:true};
 for(let i=0;i<s.length;i++){
  const ch=s[i];
  if(!'.!?…'.includes(ch))continue;
  let end=i+1;
  if(ch==='.'){
   while(end<s.length&&s[end]==='.')end++;
   const run=end-i;
   if(/\d/.test(s[i-1]||'')&&/\d/.test(s[end]||''))continue;
   if(run===1){
    let j=i;
    while(j>0&&/[A-Za-zÁÉÍÓÚÜÑáéíóúüñ.]/.test(s[j-1]))j--;
    const token=s.slice(j,i).replace(/\.$/,'').toLowerCase();
    const after=s.slice(end).replace(/^[\s"'”’»›)\]}*]+/,'');
    const afterWord=(after.match(/^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+/)||[''])[0].toLowerCase();
    const afterStartsLower=/^[a-záéíóúüñ]/.test(after);
    const dottedAbbreviationEndsSentence=token.includes('.')&&!['e.g','i.e'].includes(token)&&SENTENCE_STARTERS.has(afterWord);
    const spacedInitialismContinues=/^[A-ZÁÉÍÓÚÜÑ]{2,4}$/.test(s.slice(j,i))&&/^\s+[A-ZÁÉÍÓÚÜÑ]{1,4}\./.test(s.slice(end));
    if(!dottedAbbreviationEndsSentence&&(spacedInitialismContinues||SENTENCE_ABBREV.has(token)||token.length===1||(/^[A-ZÁÉÍÓÚÜÑ]{2,4}$/.test(s.slice(j,i))&&afterStartsLower))){
     if(end<s.length)continue;
    }
   }else{
    let k=end;
    while(k<s.length&&SENTENCE_CLOSERS.has(s[k]))k++;
    const rest=s.slice(k).trimStart();
    if(rest&&!/^[A-ZÁÉÍÓÚÜÑ¿¡"“«]/.test(rest))continue;
   }
  }
  while(end<s.length&&SENTENCE_CLOSERS.has(s[end]))end++;
  if(end<s.length&&!/\s/.test(s[end]))continue;
  return {text:s.slice(0,end).trim(),fallback:false};
 }
 return {text:shortSummary(s),fallback:true};
}
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
$('#search-results').innerHTML=doorHtml+(found.length?(()=>{return found.slice(0,searchLimit).map(x=>{const r=x.r;const translated=lang==='es'&&r.x!==r.s;const headline=(lang==='es'&&r.g)?r.g:r.h;const sentence=firstSentence(translated?r.x:r.s).text;return `<a class="search-result article-result" href="${recURL(r)}"><h3 class="search-result-title" lang="${lang==='es'&&r.g?'es':'en'}">${esc(headline)}</h3><time class="search-result-date" datetime="${esc(r.d)}">${esc(date(r.d))}</time><p class="search-result-sentence" lang="${translated?'es':'en'}">${esc(sentence)}</p></a>`;}).join('');})():(doors.length?'':`<p class="empty-message">${t('noResults')}</p>`));$('#search-more').hidden=found.length<=searchLimit;}
/* ONE BUILDER PASS (2026-11-07): the section's own preference buttons are gone; the masthead toggle is the site's one toggle design. The search follows the shared body state the masthead flips (and that applyLanguage/applyTheme write back with the same values, so this observer never loops). */new MutationObserver(()=>{const L=document.body.dataset.lang,T=document.body.dataset.theme;if((L==='es'||L==='en')&&L!==lang){lang=L;applyLanguage()}if((T==='light'||T==='dark')&&T!==theme){theme=T;applyTheme()}}).observe(document.body,{attributes:true,attributeFilter:['data-lang','data-theme']});
$('#search').addEventListener('input',()=>{ensureIndex();clearTimeout(searchTimer);searchTimer=setTimeout(()=>{searchLimit=15;$('#search-panel').hidden=false;renderSearch()},120)});$('#search').addEventListener('focus',()=>{ensureIndex();if($('#search').value){$('#search-panel').hidden=false;renderSearch()}});/* GRAFT P5: topic/full filter listeners removed with their controls */$('#search-more').addEventListener('click',()=>{searchLimit+=20;renderSearch()});$('#close-search').addEventListener('click',()=>{$('#search-panel').hidden=true;$('#search').blur()});
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();$('#search').focus()}if(e.key==='Escape'){$('#search-panel').hidden=true;$('#search').blur()}});document.addEventListener('click',e=>{if(!e.target.closest('#search-panel')&&!e.target.closest('.search-wrap'))$('#search-panel').hidden=true});
applyLanguage();applyTheme();if(new URL(location.href).searchParams.get('buscar')){ensureIndex();$('#search')?.focus();}const _q=new URL(location.href).searchParams.get('q');if(_q){const _si=$('#search');if(_si){_si.value=_q;ensureIndex();$('#search-panel').hidden=false;renderSearch();}}
/* F9 LAZY SEARCH INDEX (2026-11-07): the ~8 MB search index is not fetched at boot. ensureIndex() loads it once — on the first focus/input on #search, or immediately when the URL carries ?buscar=1 — and indexPromise is the single-flight guard: concurrent triggers share one fetch, and a failure clears the guard so the next interaction retries. F12 (2026-11-07) restricted the haystack to the visible headline + summaries; the 2026-11-08 ruling reverses it for two fields: the haystack is now headline + summaries + newspaper name + the record's year (h + s + x + n + year), and newspaper-name matches form their own labeled tier in renderSearch. Place and topic labels/keys still do not match. (Split note: the original also re-rendered the evidence list from here; the evidence list lives on the Eras hub now, in timeline.js.) */
function ensureIndex(){if(!peopleRequested){peopleRequested=true;fetch('assets/people-index.json').then(async rr=>{if(rr.ok){people=await rr.json();if(indexLoaded)renderSearch();}}).catch(()=>{});}if(indexLoaded)return Promise.resolve();if(indexPromise)return indexPromise;indexLoading=true;indexFailed=false;renderSearch();indexPromise=fetch('assets/search-index.json').then(async rr=>{if(!rr.ok)throw Error('index unavailable');records=await rr.json();records.forEach(r=>{r.searchable=normalize([r.h,r.s,r.x,r.n,(r.d||'').slice(0,4),r.v||'',r.w||''].join(' '));r.headlineSearch=normalize(r.h||'');r.paperSearch=normalize(r.n||'')});indexLoaded=true;indexLoading=false;renderSearch();}).catch(()=>{indexFailed=true;indexLoading=false;indexPromise=null;renderSearch();});return indexPromise;}
document.body.dataset.ready='true';

/* SEARCH PANEL PLACEMENT (2026-11-13, reader report via the owner):
   the results sheet was fixed to the top of the viewport, so on
   mobile it opened over the bar and hid the search box itself —
   the reader could not see what they had typed. The sheet now
   opens directly below the upper section (the bar that carries
   the search box): its top is set to the bar's bottom edge plus a
   small gap, re-measured whenever the sheet opens and on scroll
   or resize while it is open, and its height is capped to the
   space remaining under the bar, so the box and the typed text
   stay visible above the results at every width. */
const _panel=$('#search-panel'),_bar=document.querySelector('.topbar');
function placePanel(){if(!_panel||!_bar||_panel.hidden)return;const top=Math.max(0,Math.round(_bar.getBoundingClientRect().bottom)+8);_panel.style.top=top+'px';_panel.style.maxHeight='calc(100dvh - '+(top+8)+'px)';}
if(_panel&&_bar){new MutationObserver(()=>placePanel()).observe(_panel,{attributes:true,attributeFilter:['hidden']});addEventListener('resize',placePanel);addEventListener('scroll',placePanel,{passive:true});if(window.visualViewport){visualViewport.addEventListener('resize',placePanel);visualViewport.addEventListener('scroll',placePanel);}placePanel();}
