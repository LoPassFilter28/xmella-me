/* Timeline scene + evidence for the Eras hub (us-dr/eras.html).
   Split from assets/app.js on 2026-11-10 when the home timeline scene
   moved to the Eras page (Eras Split amendment): the scene, rail and
   evidence machinery lives here; home keeps only the search machinery
   in app.js. Code below is the app.js original, moved verbatim except
   for the split notes inline. */
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const STRINGS={
 search:['Buscar','Search'],records:['registros','records'],record:['registro','record'],fullTranscriptions:['transcripciones completas','complete transcriptions'],readYear:['Leer este año <span aria-hidden="true">↘</span>','Read this year <span aria-hidden="true">↘</span>'],evidence:['LA EVIDENCIA','THE EVIDENCE'],loadMore:['Ver más','Show more'],searchResults:['Resultados de búsqueda','Search results'],emptyYear:['Este año no tiene registros en la colección. Puedes seguir recorriendo el tiempo.','This year has no records in the collection. You can continue exploring the timeline.'],originalTitle:['Título original en inglés','Original title in English'],originalExcerpt:['Original en inglés','Original in English'],fullAvailable:['Transcripción disponible','Transcription available'],summaryAvailable:['Resumen disponible','Summary available'],read:['Leer el artículo ↗','Read the article ↗'],readEra:['Leer la era completa','Read the full era'],yearRecords:['Los registros de','The records of'],noResults:['No encontramos registros. Prueba otro nombre, periódico o año.','No records found. Try another name, newspaper or year.'],previous:['Año anterior','Previous year'],next:['Año siguiente','Next year'],eraPrevious:['Era anterior','Previous era'],eraNext:['Era siguiente','Next era'],gapHeading:['Entre el Triunvirato y la apertura democrática','Between the Triumvirate and the Democratic Opening'],closeSearch:['Cerrar búsqueda','Close search'],rail:['Desliza para recorrer los años','Swipe to explore the years'],scene:['Línea del tiempo','Timeline'],loading:['Cargando…','Loading…'],loadError:['No pudimos cargar los registros. Recarga la página.','We could not load the records. Reload the page.'],searchInAll:['Buscar en todos los registros','Search all records'],fromPaper:['De','From'],profileLabel:['Perfil','Profile']
};
let lang=document.body.dataset.lang==='en'?'en':'es',theme=document.body.dataset.theme==='dark'?'dark':'light';
let year=Math.max(1820,Math.min(1984,Math.round(Number(new URL(location.href).searchParams.get('year'))||1844)));
let data,records=[],recordLimit=6,scrollFrame,indexLoaded=false,indexFailed=false,indexLoading=false,indexPromise=null,seedRecords=[];
let lastStop=-2;
let railTarget=null,railSyncTimer=null,dragRail=null,suppressTickClick=false;
const reduce=matchMedia('(prefers-reduced-motion: reduce)');
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
const recURL=r=>r.m?`misc/${encodeURIComponent(r.i)}.html`:`articles/${encodeURIComponent(r.i)}.html`; /* GRAFT P1: relative article links (was absolute xmella.me URL) */
function applyLanguage(){
 document.documentElement.lang=lang;document.body.dataset.lang=lang;document.title=(lang==='en'?document.documentElement.dataset.titleEn:document.documentElement.dataset.titleEs)||document.title;
 $$('[data-i18n]').forEach(el=>el.innerHTML=t(el.dataset.i18n));$$('[data-placeholder]').forEach(el=>el.placeholder=t(el.dataset.placeholder));
 /* Split note: the app.js original also labelled #search and
    #close-search here; those elements live on the home page, whose
    slimmed app.js labels them. */
 [['#previous-year','eraPrevious'],['#next-year','eraNext'],['#year-rail','rail'],['.timeline-shell','scene']].forEach(([sel,key])=>$(sel).setAttribute('aria-label',t(key)));
 $$('img[data-en-alt]').forEach(el=>el.alt=el.dataset[lang+'Alt']);
 if(data){const tr=$('#total-records');if(tr)tr.textContent=fmt(data.recordCount);/* GRAFT P7: no stats block in the graft (host intro carries the counts) */renderYear();}
}

function applyTheme(){document.body.dataset.theme=theme;}
function buildRail(){const rail0=$('#year-rail');rail0.style.setProperty('--rail-width',rail0.clientWidth+'px');
 $('#rail-inner').innerHTML=data.years.map(y=>`<button class="year-tick ${y.year%10===0?'major':''} ${y.count===0?'empty':''}" data-year="${y.year}" tabindex="${y.year===1844?0:-1}" aria-label="${y.year}">${y.year%5===0?y.year:'·'}</button>`).join('');
 const maxCount=Math.max(...data.years.map(y=>y.count));/* Ship 7 (2026-11-11): the density strip is baked into eras.html at build time as a relief landscape (build_v7 relief_svg) inside #static-scene; the bars below are only the fallback if that baked SVG is ever absent. The highlight contract is unchanged: per-year [data-y] elements take .lit/.current in renderYear. */const sc=$('#static-scene');if(!sc.querySelector('svg'))sc.innerHTML=data.years.map(y=>`<div data-y="${y.year}" class="${y.count?'':'empty'}" style="height:${y.count?Math.min(100,10+Math.log1p(y.count)/Math.log1p(maxCount)*90):0}%"></div>`).join('');
 new ResizeObserver(()=>{const rail=$('#year-rail');rail.style.setProperty('--rail-width',rail.clientWidth+'px');positionRail()}).observe($('#year-rail'));
}
function positionRail(){const rail=$('#year-rail');if(!rail||!data)return;const left=(year-1820)*52;railTarget=left;clearTimeout(railSyncTimer);railSyncTimer=setTimeout(()=>{railTarget=null},400);rail.scrollTo({left,behavior:'instant'});}
let urlTimer=null;
function commitYearURL(){urlTimer=null;const url=new URL(location.href);if(Number(url.searchParams.get('year'))!==year){url.searchParams.set('year',year);history.replaceState(null,'',url)}}
function setYear(next,{rail=true,urlWrite='now'}={}){if(!data)return;/* GRAFT P14: listeners attach before the boot fetch resolves; ignore year input until data lands */next=Math.max(1820,Math.min(1984,Math.round(next)));if(year!==next){year=next;recordLimit=6;renderYear();if(urlWrite==='defer'){clearTimeout(urlTimer);urlTimer=setTimeout(commitYearURL,200)}else{clearTimeout(urlTimer);commitYearURL()}}if(rail)positionRail();}
function renderYear(){
 if(!data)return;/* GRAFT P14: never render a year before timeline-data lands */
 const cidx=data.chapters.findIndex(c=>year>=c.from&&year<c.to),chapter=data.chapters[cidx];
 const stops=data.chapters.map(c=>Math.max(1820,c.from));
 $('#year-readout').textContent=year;
 $('#chapter-title').textContent=chapter?chapter[lang]:t('gapHeading');$('#chapter-range').textContent=chapter?chapter.years:'';const _bl=$('#chapter-blurb');if(_bl)_bl.textContent=chapter?(lang==='es'?chapter.blurbEs:chapter.blurbEn)||'':'';
 lastStop=cidx;const el=$('#era-link');if(el){if(chapter){el.href=`era/${chapter.slug}.html`;el.textContent=t('readEra');el.hidden=false;}else{el.hidden=true;}}/* Eras Split amendment: the "Read the full era" door targets the era's sub-page (was chapter/<slug>-1.html on home). */
 $('#previous-year').disabled=!stops.some(s=>s<year);$('#next-year').disabled=!stops.some(s=>s>year);
 $$('.year-tick').forEach(el=>{const active=Number(el.dataset.year)===year;el.classList.toggle('selected',active);el.setAttribute('aria-pressed',String(active));el.tabIndex=active?0:-1;el.setAttribute('aria-label',el.dataset.year);el.textContent=active||Number(el.dataset.year)%5===0?el.dataset.year:'·'});
 $$('#static-scene [data-y]').forEach(b=>{const y=Number(b.dataset.y);b.classList.toggle('lit',!!chapter&&y>=chapter.from&&y<chapter.to);b.classList.toggle('current',y===year);});
 renderEvidence();
}
function card(r){const translated=lang==='es'&&r.x!==r.s;const headline=(lang==='es'&&r.g)?r.g:r.h;const summary=dedupeSummary(translated?(r.g||r.h):r.h,translated?r.x:r.s);return `<article class="record-card"><div class="record-paper">${esc(r.n)}</div><div class="record-meta">${esc(date(r.d))}${r.p?' · '+esc(r.p):''}</div>${r.o===1?`<p class="original-label">${t('originalTitle')}</p>`:''}<h3 class="record-title" lang="${lang==='es'&&r.g?'es':'en'}">${esc(headline)}</h3><p class="record-summary" lang="${translated?'es':'en'}">${esc(summary)}</p>${lang==='es'&&!translated?`<span class="record-badge">${t('originalExcerpt')}</span>`:''}<div class="record-bottom">${r.f?`<span class="record-badge">${t('fullAvailable')}</span>`:''}<a class="record-open" href="${recURL(r)}">${t('read')}<span class="sr-only"> · ${esc(r.n)}, ${esc(date(r.d))}</span></a></div></article>`}
function renderEvidence(){/* F-01 (flow-fix Batch 1): the scene shows exactly the era's curated articles — the register's picks on the chapter, in register order — never a per-year slice under the era's name. Thin eras show only what exists; the gap (no chapter) keeps the honest empty-year line. */
 const ch=data?data.chapters.find(c=>year>=c.from&&year<c.to):null;$('#load-more').hidden=true;
 if(!ch){$('#record-list').innerHTML=data?`<p class="empty-message">${t('emptyYear')}</p>`:'';return;}
 const rows=indexLoaded?records:seedRecords;
 if(!rows.length){$('#record-list').innerHTML=indexFailed?`<p class="empty-message">${t('loadError')}</p>`:`<p class="empty-message">${t('loading')}</p>`;return;}
 const byId=new Map(rows.map(r=>[r.i,r]));const subset=(ch.picks||[]).map(id=>byId.get(id)).filter(Boolean);
 $('#record-list').innerHTML=subset.length?subset.map(card).join(''):`<p class="empty-message">${t('emptyYear')}</p>`;}
/* ONE BUILDER PASS (2026-11-07): the section's own preference buttons are gone; the masthead toggle is the site's one toggle design. The timeline follows the shared body state the masthead flips (and that applyLanguage/applyTheme write back with the same values, so this observer never loops). */new MutationObserver(()=>{const L=document.body.dataset.lang,T=document.body.dataset.theme;if((L==='es'||L==='en')&&L!==lang){lang=L;applyLanguage()}if((T==='light'||T==='dark')&&T!==theme){theme=T;applyTheme()}}).observe(document.body,{attributes:true,attributeFilter:['data-lang','data-theme']});
$('#previous-year').addEventListener('click',()=>{if(!data)return;const stops=data.chapters.map(c=>Math.max(1820,c.from)).filter(s=>s<year);if(stops.length)setYear(stops[stops.length-1])});$('#next-year').addEventListener('click',()=>{if(!data)return;const stop=data.chapters.map(c=>Math.max(1820,c.from)).find(s=>s>year);if(stop!==undefined)setYear(stop)});
$('#year-rail').addEventListener('pointerdown',()=>{railTarget=null;clearTimeout(railSyncTimer)},{passive:true});$('#year-rail').addEventListener('wheel',()=>{railTarget=null;clearTimeout(railSyncTimer)},{passive:true});$('#year-rail').addEventListener('touchstart',()=>{railTarget=null;clearTimeout(railSyncTimer)},{passive:true});$('#year-rail').addEventListener('scroll',()=>{const rail=$('#year-rail'),sl=rail.scrollLeft;cancelAnimationFrame(scrollFrame);scrollFrame=requestAnimationFrame(()=>{if(railTarget!==null){if(Math.abs(sl-railTarget)<=1){railTarget=null;clearTimeout(railSyncTimer);}return;}setYear(1820+sl/52,{rail:false,urlWrite:'defer'})})},{passive:true});const railEl=$('#year-rail');railEl.addEventListener('pointerdown',e=>{if(e.pointerType!=='mouse'||e.button!==0)return;dragRail={x:e.clientX,left:railEl.scrollLeft,moved:false};});window.addEventListener('pointermove',e=>{if(!dragRail)return;const dx=e.clientX-dragRail.x;if(Math.abs(dx)>4)dragRail.moved=true;if(dragRail.moved){e.preventDefault();railEl.scrollLeft=dragRail.left-dx;}},{passive:false});window.addEventListener('pointerup',()=>{if(!dragRail)return;if(dragRail.moved){suppressTickClick=true;setTimeout(()=>{suppressTickClick=false},350);}dragRail=null;});window.addEventListener('pointercancel',()=>{dragRail=null;});
$('#year-rail').addEventListener('keydown',e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();setYear(year+(e.key==='ArrowRight'?1:-1))}if(e.key==='Home'||e.key==='End'){e.preventDefault();setYear(e.key==='Home'?1820:1984)}});
$('#rail-inner').addEventListener('click',e=>{const b=e.target.closest('[data-year]');if(b){if(suppressTickClick){suppressTickClick=false;return;}setYear(Number(b.dataset.year))}});;
$('#load-more').addEventListener('click',()=>{recordLimit+=12;if(indexLoaded)renderEvidence();else ensureIndex();});
applyLanguage();applyTheme();
/* GRAFT P8 + F9 (2026-11-07): the year UI — rail, slider, chapters, scene — renders from timeline-data.json alone at boot. The search index is deliberately NOT fetched in this phase; see ensureIndex() directly below. Only the evidence list waits for the lazy index load. */
/* F9 LAZY SEARCH INDEX (2026-11-07): the ~8 MB search index is not fetched at boot. ensureIndex() loads it once — when the evidence list's "show more" asks for records beyond the seed — and indexPromise is the single-flight guard: concurrent triggers share one fetch, and a failure clears the guard so the next interaction retries. (Split note: the app.js original also fetched the people index here for the home search doors; the hub has no search panel, so that fetch stays with app.js.) */
function ensureIndex(){if(indexLoaded)return Promise.resolve();if(indexPromise)return indexPromise;indexLoading=true;indexFailed=false;renderEvidence();indexPromise=fetch('assets/search-index.json').then(async rr=>{if(!rr.ok)throw Error('index unavailable');records=await rr.json();records.forEach(r=>{r.searchable=normalize([r.h,r.s,r.x,r.n,(r.d||'').slice(0,4),r.v||'',r.w||''].join(' '));r.headlineSearch=normalize(r.h||'');r.paperSearch=normalize(r.n||'')});indexLoaded=true;indexLoading=false;if(data){renderEvidence();}}).catch(()=>{indexFailed=true;indexLoading=false;indexPromise=null;if(data){renderEvidence();}});return indexPromise;}
try{const dr=await fetch('assets/timeline-data.json');if(!dr.ok)throw Error('timeline data unavailable');data=await dr.json();buildRail();applyLanguage();requestAnimationFrame(()=>setYear(year));fetch('assets/evidence-seed.json').then(async sr=>{if(sr.ok){seedRecords=await sr.json();if(!indexLoaded)renderEvidence();}}).catch(()=>{});document.body.dataset.ready='true';}catch{$('#data-error').hidden=false;$('#data-error').textContent=t('loadError');}
