
(function(){
"use strict";
var root=document.documentElement;

/* theme: respect saved preference, default light */
try{
  var saved=localStorage.getItem("hsd-theme");
  if(saved==="dark"||saved==="light"){root.setAttribute("data-theme",saved);}
}catch(e){}

/* font size A-/A+ : 0.9x – 1.25x */
function applyScale(v){root.style.setProperty("--reading-scale",v);}
var scale=1;
try{var s=parseFloat(localStorage.getItem("hsd-scale"));if(s>=0.9&&s<=1.25){scale=s;}}catch(e){}
applyScale(scale);
function setScale(d){
  scale=Math.min(1.25,Math.max(0.9,Math.round((scale+d)*100)/100));
  applyScale(scale);
  try{localStorage.setItem("hsd-scale",String(scale));}catch(e){}
  var lab=document.getElementById("scale-label");
  if(lab){lab.textContent=Math.round(scale*100)+" %";}
}

/* wire controls once DOM is ready */
document.addEventListener("DOMContentLoaded",function(){
  var themeBtn=document.getElementById("theme-toggle");
  if(themeBtn){
    var sync=function(){
      var dark=root.getAttribute("data-theme")==="dark";
      themeBtn.setAttribute("aria-pressed",dark?"true":"false");
      themeBtn.textContent=dark?"Claro":"Oscuro";
    };
    themeBtn.addEventListener("click",function(){
      var dark=root.getAttribute("data-theme")==="dark";
      root.setAttribute("data-theme",dark?"light":"dark");
      try{localStorage.setItem("hsd-theme",dark?"light":"dark");}catch(e){}
      sync();
    });
    sync();
  }
  var am=document.getElementById("font-minus"),ap=document.getElementById("font-plus");
  if(am){am.addEventListener("click",function(){setScale(-0.05);});}
  if(ap){ap.addEventListener("click",function(){setScale(0.05);});}
  var lab=document.getElementById("scale-label");
  if(lab){lab.textContent=Math.round(scale*100)+" %";}

  /* index drawer */
  var drawer=document.getElementById("index-drawer"),openBtn=document.getElementById("drawer-open"),
      closeBtn=document.getElementById("drawer-close");
  if(drawer&&openBtn){
    var setOpen=function(o){
      drawer.classList.toggle("open",o);
      drawer.setAttribute("aria-hidden",o?"false":"true");
      openBtn.setAttribute("aria-expanded",o?"true":"false");
      if(o&&closeBtn){closeBtn.focus();}
    };
    openBtn.addEventListener("click",function(){setOpen(true);});
    closeBtn.addEventListener("click",function(){setOpen(false);});
    drawer.querySelector(".scrim").addEventListener("click",function(){setOpen(false);});
    document.addEventListener("keydown",function(e){if(e.key==="Escape"){setOpen(false);}});
  }

  var reduced=window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* scroll reveals: once per element */
  var revs=document.querySelectorAll(".reveal");
  if(reduced||!("IntersectionObserver" in window)){
    revs.forEach(function(el){el.classList.add("in");});
  }else{
    var io=new IntersectionObserver(function(entries){
      entries.forEach(function(en){
        if(en.isIntersecting){en.target.classList.add("in");io.unobserve(en.target);}
      });
    },{threshold:0.08,rootMargin:"0px 0px -6% 0px"});
    revs.forEach(function(el){io.observe(el);});
  }

  /* reading progress bar */
  var bar=document.getElementById("progress");
  if(bar){
    var tick=function(){
      var h=document.documentElement;
      var max=h.scrollHeight-h.clientHeight;
      var p=max>0?Math.min(1,h.scrollTop/max):0;
      bar.style.transform="scaleX("+p+")";
    };
    document.addEventListener("scroll",tick,{passive:true});
    window.addEventListener("resize",tick);
    tick();
  }

  /* in-chapter find: accent-insensitive highlight + jump */
  var findBox=document.getElementById("find-q");
  if(findBox){
    var article=document.querySelector("main article");
    var norm=function(s){return s.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();};
    var marks=[],cur=-1;
    var countEl=document.getElementById("find-count");
    var clearMarks=function(){
      document.querySelectorAll("mark.hl").forEach(function(m){
        m.parentNode.replaceChild(document.createTextNode(m.textContent),m);
      });
      if(article){article.normalize();}
      marks=[];cur=-1;
      if(countEl){countEl.textContent="";}
    };
    var goTo=function(i){
      marks.forEach(function(m){m.classList.remove("current");});
      if(!marks.length){return;}
      cur=((i%marks.length)+marks.length)%marks.length;
      marks[cur].classList.add("current");
      marks[cur].scrollIntoView({block:"center",behavior:reduced?"auto":"smooth"});
      if(countEl){countEl.textContent=(cur+1)+" de "+marks.length;}
    };
    findBox.addEventListener("input",function(){
      clearMarks();
      var q=norm(findBox.value.trim());
      if(!q||!article){return;}
      var walker=document.createTreeWalker(article,NodeFilter.SHOW_TEXT),nodes=[],nd;
      while((nd=walker.nextNode())){nodes.push(nd);}
      nodes.forEach(function(node){
        var text=node.nodeValue,ntext=norm(text),idx=ntext.indexOf(q);
        if(idx===-1){return;}
        var frag=document.createDocumentFragment(),last=0;
        while(idx!==-1){
          frag.appendChild(document.createTextNode(text.slice(last,idx)));
          var mark=document.createElement("mark");mark.className="hl";
          mark.textContent=text.slice(idx,idx+q.length);
          frag.appendChild(mark);marks.push(mark);
          last=idx+q.length;idx=ntext.indexOf(q,last);
        }
        frag.appendChild(document.createTextNode(text.slice(last)));
        node.parentNode.replaceChild(frag,node);
      });
      goTo(0);
    });
    findBox.addEventListener("keydown",function(e){
      if(e.key==="Enter"){e.preventDefault();goTo(cur+1);}
    });
    var nextBtn=document.getElementById("find-next");
    if(nextBtn){nextBtn.addEventListener("click",function(){goTo(cur+1);});}
  }

  /* cover intro: ~2.4s, skippable, identical every load */
  var cover=document.querySelector(".cover");
  if(cover){
    var body=document.body,skip=document.getElementById("skip-intro");
    var finish=function(){body.classList.remove("intro");body.classList.add("intro-done");};
    if(reduced){finish();}
    else{
      body.classList.add("intro");
      var t=setTimeout(finish,2600);
      if(skip){skip.addEventListener("click",function(){clearTimeout(t);finish();skip.blur();});}
    }
  }
});
})();
/* --- fin de site.js --- */
