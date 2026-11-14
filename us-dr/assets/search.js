/* Sitewide search (2026-11-14, owner order): the results pop-up is a
   sitewide phenomenon. Every us-dr page except the home page carries
   the shared bar's search form, which used to GET-submit to the home
   page (index.html?q=...) and take the reader away from the page they
   were reading. This module turns that form into the same in-place
   search the home page has (assets/app.js): same index
   (assets/search-index.json + assets/people-index.json), same ranking
   (year tier, then newspaper tier, then headline tier), same result
   rows (headline, date, first sentence of the summary, nothing
   underlined), same person doors, same language behaviour (results
   follow the page's body[data-lang] state), same close behaviour.
   The panel markup reuses the home panel's ids and is wrapped in a
   .timeline scope so the shipped panel stylesheet applies verbatim;
   the ids are unique on interior pages because app.js is not loaded
   there. This module stays inert on the home page (guarded by the
   loader in chatrd.js and again below) and on pages without the bar
   form. The bar is anchored at the top of interior pages, so the
   panel opens under it in place: nothing travels, at any width.
   Loaded by assets/chatrd.js, the one script every us-dr page
   already includes. */
(function(){
'use strict';
const form=document.querySelector('.topbar form.search-wrap');
if(!form)return;
if(document.querySelector('#search-panel')||document.querySelector('#search'))return; /* home page: app.js owns search */
const input=form.querySelector('input[name="q"]')||form.querySelector('input');
if(!input)return;
const rootURL=new URL('./',form.action).href; /* the us-dr root, from the form's own action */
const $=s=>document.querySelector(s);
const STRINGS={
 records:['registros','records'],record:['registro','record'],loadMore:['Ver más registros','Show more records'],searchResults:['Resultados de búsqueda','Search results'],noResults:['No encontramos registros. Prueba otro nombre, periódico o año.','No records found. Try another name, newspaper or year.'],closeSearch:['Cerrar búsqueda','Close search'],loading:['Cargando…','Loading…'],loadError:['No pudimos cargar los registros. Recarga la página.','We could not load the records. Reload the page.'],profileLabel:['Perfil','Profile']
};
let lang=document.body.dataset.lang==='en'?'en':'es';
let records=[],searchLimit=15,searchTimer,indexLoaded=false,indexFailed=false,indexLoading=false,indexPromise=null,people=[],peopleRequested=false;
const t=k=>STRINGS[k]?.[lang==='es'?0:1]||k;
const fmt=n=>new Intl.NumberFormat(lang==='es'?'es-DO':'en-US').format(n);
const date=d=>new Intl.DateTimeFormat(lang==='es'?'es-DO':'en-US',{year:'numeric',month:'long',day:'numeric',timeZone:'UTC'}).format(new Date(d+'T12:00:00Z'));
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const countText=n=>`${fmt(n)} ${t(n===1?'record':'records')}`;
const normalize=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
/* SEARCH VARIANTS (2026-11-13, Closing Arc A): Jimenes / Jimenez are NOT merged as names; they are cross-linked as search variants, exactly as in app.js. */
const SEARCH_VARIANTS=[['jimenes','jimenez']];
const expandVariants=s=>{for(const[a,b]of SEARCH_VARIANTS){if(s.includes(a)&&!s.includes(b))s+=' '+b;else if(s.includes(b)&&!s.includes(a))s+=' '+a;}return s;};
/* SEARCH RESULTS: first-sentence reader, copied verbatim from app.js (2026-11-10) so interior rows match home rows exactly. */
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
const recURL=r=>rootURL+(r.m?`misc/${encodeURIComponent(r.i)}.html`:`articles/${encodeURIComponent(r.i)}.html`);
/* Panel DOM: built once, mirroring the home panel's markup and ids. */
const scope=document.createElement('div');
scope.className='timeline';
scope.innerHTML=`<section class="search-panel" id="search-panel" aria-labelledby="search-title" hidden><div class="section-top"><h2 id="search-title"></h2><button id="close-search" class="icon-button" type="button">×</button></div><p id="search-count" aria-live="polite"></p><div id="search-results"></div><button id="search-more" class="outline-button" type="button"></button></section>`;
document.body.appendChild(scope);
const panel=$('#search-panel');
function applyStrings(){
 $('#search-title').textContent=t('searchResults');
 const close=$('#close-search');close.setAttribute('aria-label',t('closeSearch'));
 $('#search-more').textContent=t('loadMore');
}
function renderSearch(){
 if(!indexLoaded){$('#search-count').textContent='';$('#search-results').innerHTML=indexFailed?`<p class="empty-message">${t('loadError')}</p>`:indexLoading?`<p class="empty-message">${t('loading')}</p>`:'';$('#search-more').hidden=true;return;}
 const q=normalize(input.value.trim());const terms=q.split(/\s+/).filter(Boolean);
 const found=records.filter(r=>terms.every(s=>r.searchable.includes(s))).map(r=>({r,tier:(()=>{const yq=/^\d{4}$/.test(input.value.trim())?input.value.trim():null;return yq&&r.d.slice(0,4)===yq?-1:(terms.length>0&&terms.every(s=>r.paperSearch.includes(s)))?0:((terms.length>0&&terms.every(s=>r.headlineSearch.includes(s)))?1:2)})()})).sort((a,b)=>a.tier-b.tier||(a.tier===0&&b.tier===0&&a.r.n!==b.r.n?a.r.n.localeCompare(b.r.n):0)||b.r.d.localeCompare(a.r.d));
 $('#search-count').textContent=countText(found.length);
 const doors=(terms.length&&terms.some(s=>s.length>=4))?people.filter(p=>terms.every(s=>p.tokens.includes(s))).slice(0,4):[];
 const doorHtml=doors.map(p=>{const role=(lang==='es'?p.role_es:p.role_en)||'';const roleCut=role.length>120?role.slice(0,120).replace(/\s+\S*$/,'')+'…':role;return `<a class="search-result person-door" href="${rootURL}profiles.html#p-${p.slug}"><small>${t('profileLabel')}</small><strong>${esc(p.name)}${p.dates?` · ${esc(p.dates)}`:''}</strong><small>${esc(roleCut)}</small></a>`;}).join('');
 $('#search-results').innerHTML=doorHtml+(found.length?found.slice(0,searchLimit).map(x=>{const r=x.r;const translated=lang==='es'&&r.x!==r.s;const headline=(lang==='es'&&r.g)?r.g:r.h;const sentence=firstSentence(translated?r.x:r.s).text;return `<a class="search-result article-result" href="${recURL(r)}"><h3 class="search-result-title" lang="${lang==='es'&&r.g?'es':'en'}">${esc(headline)}</h3><time class="search-result-date" datetime="${esc(r.d)}">${esc(date(r.d))}</time><p class="search-result-sentence" lang="${translated?'es':'en'}">${esc(sentence)}</p></a>`;}).join(''):(doors.length?'':`<p class="empty-message">${t('noResults')}</p>`));
 $('#search-more').hidden=found.length<=searchLimit;
}
/* Lazy index load, single-flight, same as app.js (F9). */
function ensureIndex(){
 if(!peopleRequested){peopleRequested=true;fetch(rootURL+'assets/people-index.json').then(async rr=>{if(rr.ok){people=await rr.json();people.forEach(pp=>{for(const[a,b]of SEARCH_VARIANTS){if(pp.tokens.includes(a)&&!pp.tokens.includes(b))pp.tokens.push(b);else if(pp.tokens.includes(b)&&!pp.tokens.includes(a))pp.tokens.push(a);}});if(indexLoaded)renderSearch();}}).catch(()=>{});}
 if(indexLoaded)return Promise.resolve();
 if(indexPromise)return indexPromise;
 indexLoading=true;indexFailed=false;renderSearch();
 indexPromise=fetch(rootURL+'assets/search-index.json').then(async rr=>{if(!rr.ok)throw Error('index unavailable');records=await rr.json();records.forEach(r=>{r.searchable=expandVariants(normalize([r.h,r.s,r.x,r.n,(r.d||'').slice(0,4),r.v||'',r.w||''].join(' ')));r.headlineSearch=normalize(r.h||'');r.paperSearch=normalize(r.n||'')});indexLoaded=true;indexLoading=false;renderSearch();}).catch(()=>{indexFailed=true;indexLoading=false;indexPromise=null;renderSearch();});
 return indexPromise;
}
/* Panel placement: same rule as the home placement fix (2026-11-13): the sheet opens below the bar, top set to the bar's bottom edge + 8px, height capped to the space under the bar. The interior bar is anchored, so nothing travels at any width. */
const bar=document.querySelector('.topbar');
function placePanel(){if(!bar||panel.hidden)return;const top=Math.max(0,Math.round(bar.getBoundingClientRect().bottom)+8);panel.style.top=top+'px';panel.style.maxHeight='calc(100dvh - '+(top+8)+'px)';}
function openPanel(){if(panel.hidden){panel.hidden=false;}placePanel();renderSearch();}
function closePanel(){panel.hidden=true;input.blur();}
new MutationObserver(()=>{const L=document.body.dataset.lang;if((L==='es'||L==='en')&&L!==lang){lang=L;applyStrings();renderSearch();}}).observe(document.body,{attributes:true,attributeFilter:['data-lang']});
form.addEventListener('submit',e=>{e.preventDefault();ensureIndex();searchLimit=15;openPanel();});
input.addEventListener('input',()=>{ensureIndex();clearTimeout(searchTimer);searchTimer=setTimeout(()=>{searchLimit=15;openPanel();},120)});
input.addEventListener('focus',()=>{ensureIndex();if(input.value)openPanel();});
$('#search-more').addEventListener('click',()=>{searchLimit+=20;renderSearch();placePanel();});
$('#close-search').addEventListener('click',closePanel);
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();input.focus();}if(e.key==='Escape'&&!panel.hidden)closePanel();});
document.addEventListener('click',e=>{if(!panel.hidden&&!e.target.closest('#search-panel')&&!e.target.closest('.search-wrap'))panel.hidden=true;});
addEventListener('resize',placePanel);addEventListener('scroll',placePanel,{passive:true});
if(window.visualViewport){visualViewport.addEventListener('resize',placePanel);visualViewport.addEventListener('scroll',placePanel);}
applyStrings();
const params=new URL(location.href).searchParams;
if(params.get('buscar')){ensureIndex();input.focus();}
const q0=params.get('q');
if(q0){input.value=q0;ensureIndex();openPanel();}
})();
