// Navigation is plain HTML; this script adds only a subtle light response.
const finePointer=matchMedia('(hover: hover) and (pointer: fine)');
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
for(const [i,card] of [...document.querySelectorAll('.card')].entries()){
  card.style.setProperty('--order',i);
  card.addEventListener('pointermove',event=>{
    if(!finePointer.matches||reducedMotion.matches)return;
    const box=card.getBoundingClientRect();
    card.style.setProperty('--mx',`${(event.clientX-box.left)/box.width*100}%`);
    card.style.setProperty('--my',`${(event.clientY-box.top)/box.height*100}%`);
  },{passive:true});
}
