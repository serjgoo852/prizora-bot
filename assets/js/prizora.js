/* ===== Original script block 1 ===== */
(()=>{
 const track=document.getElementById('slides');
 if(!track)return;
 const cards=[...track.querySelectorAll('.slide')], dots=document.getElementById('dots');
 const prev=document.getElementById('prev'), next=document.getElementById('next');
 if(!cards.length||!dots||!prev||!next)return;
 let index=0,startX=0,dragging=false,angle=0,lastTime=0,paused=false,raf=0;
 const count=cards.length;
 const slideImages=cards.map(card=>card.querySelector('.slide-art img'));
 slideImages.forEach(img=>{
   if(!img)return;
   img.decoding='async';img.loading='lazy';
   if(img.dataset.lazySrc){
     img.removeAttribute('src');
   }else if(img.getAttribute('src')){
     img.dataset.lazySrc=img.getAttribute('src');
     img.removeAttribute('src');
   }
 });
 function loadNearby(center){
   /* Load all prize images in parallel so cards do not appear blank as the drum turns. */
   slideImages.forEach((img,i)=>{
     if(!img)return;
     img.loading='eager';
     img.decoding='async';
     if(img.dataset.lazySrc){
       img.src=img.dataset.lazySrc;
       delete img.dataset.lazySrc;
     }
     if(i===center) img.fetchPriority='high';
   });
 }
 loadNearby(0);
 /* Keep a clean, dark reverse face inside the 3D drum.
    Prize artwork stays only on the visitor-facing side; no duplicate images. */
 cards.forEach(card=>{
   const back=document.createElement('div');
   back.className='slide-back';
   back.setAttribute('aria-hidden','true');
   card.append(back);
 });
 const mobile=window.matchMedia('(max-width:700px)').matches;
 const cardWidth=mobile?Math.min(148,window.innerWidth*.42):300;
 const radius=mobile?Math.max(175,Math.ceil(cardWidth/(2*Math.sin(Math.PI/count))+18)):500;
 const step=360/count;
 cards.forEach((card,i)=>{
   card.style.setProperty('transform',`translate(-50%,-50%) rotateY(${i*step}deg) translateZ(${radius}px)`,'important');
   const dot=document.createElement('button');
   dot.type='button';dot.className='dot'+(i===0?' active':'');
   dot.setAttribute('aria-label',`Приз ${i+1}`);
   dot.addEventListener('click',()=>go(i,true));dots.appendChild(dot);
 });
 const dotsList=[...dots.children];
 let paintedIndex=-1;
 function paint(){
   /* Keep the 3D rotation lightweight while prize images download. */
   track.style.setProperty('transform',`translateZ(-${radius}px) rotateY(${-angle}deg)`,'important');
   index=((Math.round(angle/step)%count)+count)%count;
   if(index!==paintedIndex){
     paintedIndex=index;
     cards.forEach((card,i)=>{
       const d=(i-index+count)%count,near=Math.min(d,count-d);
       card.style.opacity=near>Math.ceil(count/2)?'.45':'1';
       card.style.filter=near===0?'none':`brightness(${near===1?.88:.68})`;
     });
     dotsList.forEach((d,i)=>d.classList.toggle('active',i===index));
   }
 }
 function go(i,manual=false){angle=i*step;paint();if(manual)paused=false}
 function animate(t){if(!lastTime)lastTime=t;const dt=Math.min(50,t-lastTime);lastTime=t;if(!paused&&!dragging){angle=(angle+dt*0.012)%360;paint()}raf=requestAnimationFrame(animate)}
 prev.addEventListener('click',()=>go(Math.round(angle/step)-1,true));
 next.addEventListener('click',()=>go(Math.round(angle/step)+1,true));
 const drum=document.querySelector('.carousel');
 drum.addEventListener('mouseenter',()=>{paused=true});
 /* Desktop wheel: rotate one or more prize positions without scrolling the page. */
 let wheelDelta=0;
 drum.addEventListener('wheel',e=>{
   if(window.matchMedia('(max-width:700px)').matches)return;
   e.preventDefault();
   wheelDelta+=e.deltaY;
   const threshold=45;
   if(Math.abs(wheelDelta)>=threshold){
     const direction=wheelDelta>0?1:-1;
     const steps=Math.min(3,Math.floor(Math.abs(wheelDelta)/threshold));
     wheelDelta-=direction*steps*threshold;
     go(Math.round(angle/step)+direction*steps,true);
     paused=true;
   }
 },{passive:false});
 drum.addEventListener('mouseleave',()=>{paused=false});
 drum.addEventListener('focusin',()=>{paused=true});
 drum.addEventListener('focusout',()=>{paused=false});
 drum.addEventListener('touchstart',e=>{startX=e.touches[0].clientX;dragging=true;paused=true},{passive:true});
 drum.addEventListener('touchend',e=>{if(!dragging)return;dragging=false;const dx=e.changedTouches[0].clientX-startX;if(Math.abs(dx)>18)go(Math.round(angle/step)+(dx<0?1:-1),true);paused=false},{passive:true});
 /* Desktop: drag the 3D drum with the left mouse button, like a swipe on mobile. */
 let mouseDown=false,mouseStartX=0,mouseLastX=0;
 drum.addEventListener('mousedown',e=>{
   if(e.button!==0)return;
   mouseDown=true;dragging=true;paused=true;
   mouseStartX=mouseLastX=e.clientX;
   e.preventDefault();
 });
 document.addEventListener('mousemove',e=>{
   if(!mouseDown)return;
   mouseLastX=e.clientX;
 });
 document.addEventListener('mouseup',e=>{
   if(!mouseDown)return;
   mouseDown=false;dragging=false;
   const dx=e.clientX-mouseStartX;
   if(Math.abs(dx)>18)go(Math.round(angle/step)+(dx<0?1:-1),true);
   paused=drum.matches(':hover')?true:false;
 });
 paint();raf=requestAnimationFrame(animate);
})();
 const menuPanel=document.getElementById('menu');
 const menuNav=[...document.querySelectorAll('.bottom nav a')].find(a=>a.getAttribute('href')==='#menu');
 const homeNav=document.querySelector('.bottom nav a[href="#"]');
 if(menuPanel&&menuNav){
   menuNav.addEventListener('click',e=>{e.preventDefault();menuPanel.hidden=false;menuPanel.scrollIntoView({behavior:'smooth',block:'start'});menuNav.classList.add('active');if(homeNav)homeNav.classList.remove('active')});
   if(homeNav)homeNav.addEventListener('click',e=>{e.preventDefault();menuPanel.hidden=true;window.scrollTo({top:0,behavior:'smooth'});homeNav.classList.add('active');menuNav.classList.remove('active')});
 }

(()=>{const items=[...document.querySelectorAll('.pro-fade-item')];if(items.length<2)return;let i=0;setInterval(()=>{items[i].classList.remove('active');i=(i+1)%items.length;items[i].classList.add('active')},5200)})();

(()=>{
 const slider=document.querySelector('.pro-contest-slider');
 const track=document.getElementById('proContestTrack');
 if(!slider||!track)return;
 const cards=[...track.children];let index=0,startX=0,timer=null,paused=false;
 function show(i){index=(i+cards.length)%cards.length;track.style.transform=`translateX(-${index*100}%)`}
 function stop(){if(timer)clearInterval(timer);timer=null}
 function start(){stop();if(!paused&&!matchMedia('(prefers-reduced-motion: reduce)').matches)timer=setInterval(()=>show(index+1),4700)}

 slider.addEventListener('mouseenter',()=>{paused=true;stop()});slider.addEventListener('mouseleave',()=>{paused=false;start()});
 slider.addEventListener('focusin',()=>{paused=true;stop()});slider.addEventListener('focusout',()=>{paused=false;start()});
 slider.addEventListener('touchstart',e=>{startX=e.touches[0].clientX;paused=true;stop()},{passive:true});
 slider.addEventListener('touchend',e=>{const dx=e.changedTouches[0].clientX-startX;if(Math.abs(dx)>35)show(index+(dx<0?1:-1));paused=false;start()},{passive:true});
 show(0);start();
})();

;
/* ===== Original script block 2 ===== */
/* Keep the guide character and caption fixed while PRO messages fade. */
document.addEventListener('DOMContentLoaded',()=>{
 const presenter=document.querySelector('.approved-hero');
 const showcase=document.querySelector('.pro-showcase');
 const note=showcase&&showcase.querySelector('.pro-note');
 if(presenter&&showcase) showcase.appendChild(presenter);
 if(note&&showcase) showcase.appendChild(note);
});

;
/* ===== Original script block 3 id="prizora-real-rays-motion" ===== */
/* Animate a dedicated background layer with Web Animations API.
   This avoids every legacy .carousel::before rule and leaves the 3D drum untouched. */
(function(){
  function startPrizoraRays(){
    const drum=document.querySelector('.carousel');
    if(!drum || drum.querySelector('.prizora-rays-layer')) return;
    const rays=document.createElement('div');
    rays.className='prizora-rays-layer';
    rays.setAttribute('aria-hidden','true');
    Object.assign(rays.style,{
      position:'absolute',left:'50%',top:'50%',width:'245%',height:'245%',
      zIndex:'1',pointerEvents:'none',border:'0',borderRadius:'50%',
      opacity:'.82',transform:'translate(-50%,-50%) rotate(0deg)',
      background:'repeating-conic-gradient(from 0deg at 50% 50%, transparent 0deg 12deg, rgba(255,190,78,0) 12deg 15deg, rgba(255,190,78,.64) 15.4deg 16.4deg, rgba(255,232,174,.25) 16.7deg 17deg, transparent 17.4deg 30deg), repeating-conic-gradient(from 9deg at 50% 50%, transparent 0deg 43deg, rgba(255,215,140,.28) 43.4deg 44deg, transparent 44.5deg 90deg)',
      maskImage:'radial-gradient(ellipse at center, transparent 0 16%, #000 28%, #000 62%, transparent 88%)',
      webkitMaskImage:'radial-gradient(ellipse at center, transparent 0 16%, #000 28%, #000 62%, transparent 88%)',
      filter:'blur(.7px)'
    });
    /* On desktop, keep the ray field OUTSIDE the clipped drum frame.
       The drum itself remains clipped, so only the rays can extend beyond it. */
    if(window.matchMedia('(min-width:701px)').matches && drum.parentElement){
      const host=drum.parentElement;
      if(getComputedStyle(host).position==='static') host.style.position='relative';
      host.insertBefore(rays,drum);
      rays.style.position='absolute';
      rays.style.zIndex='0';
      drum.style.position='relative';
      drum.style.zIndex='1';
      const placeRays=()=>{
        const drumRect=drum.getBoundingClientRect();
        const hostRect=host.getBoundingClientRect();
        rays.style.left=(drumRect.left-hostRect.left+host.scrollLeft+drumRect.width/2)+'px';
        rays.style.top=(drumRect.top-hostRect.top+host.scrollTop+drumRect.height/2)+'px';
        rays.style.width=(drumRect.width*2.45)+'px';
        rays.style.height=(drumRect.height*2.45)+'px';
      };
      placeRays();
      window.addEventListener('resize',placeRays,{passive:true});
    }else{
      drum.insertBefore(rays,drum.firstChild);
    }
    if(rays.animate){
      rays.animate(
        [{transform:'translate(-50%,-50%) rotate(0deg)'},{transform:'translate(-50%,-50%) rotate(360deg)'}],
        {duration:18000,iterations:Infinity,easing:'linear'}
      );
    }else{
      let angle=0,last=0;
      function spin(t){if(!last)last=t;angle=(angle+(t-last)*.02)%360;last=t;rays.style.transform='translate(-50%,-50%) rotate('+angle+'deg)';requestAnimationFrame(spin)}
      requestAnimationFrame(spin);
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',startPrizoraRays,{once:true});
  else startPrizoraRays();
})();

;
/* ===== Original script block 4 id="prizora-real-alpha-processing" ===== */
(()=> {
  function makeTransparent(img){
    if(!img || img.dataset.prizoraAlphaDone || !img.complete || !img.naturalWidth) return;
    img.dataset.prizoraAlphaDone='working';
    try{
      const c=document.createElement('canvas'),w=img.naturalWidth,h=img.naturalHeight;
      c.width=w;c.height=h;
      const x=c.getContext('2d',{willReadFrequently:true});
      x.drawImage(img,0,0,w,h);
      const frame=x.getImageData(0,0,w,h),p=frame.data;
      const feather=Math.max(24,Math.round(Math.min(w,h)*.13));
      for(let yy=0;yy<h;yy++){
        for(let xx=0;xx<w;xx++){
          const edge=Math.min(xx,w-1-xx,yy,h-1-yy);
          const t=Math.max(0,Math.min(1,edge/feather));
          const smooth=t*t*(3-2*t);
          const k=(yy*w+xx)*4+3;
          p[k]=Math.round(p[k]*smooth);
        }
      }
      x.putImageData(frame,0,0);
      const png=c.toDataURL('image/png');
      img.onload=()=>{img.dataset.prizoraAlphaDone='yes';};
      img.src=png;
    }catch(e){img.dataset.prizoraAlphaDone='error';}
  }
  function scan(){document.querySelectorAll('.approved-hero img').forEach(img=>{
    if(img.dataset.prizoraAlphaDone) return;
    if(img.complete)makeTransparent(img);
    else img.addEventListener('load',()=>makeTransparent(img),{once:true});
  });}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',scan);
  else scan();
  new MutationObserver(scan).observe(document.documentElement,{childList:true,subtree:true});
})();

;
/* ===== Original script block 5 id="prizora-runner-script" ===== */
(()=>{const bot=document.getElementById('prizora-runner');if(!bot)return;
 const selector='.approved-hero,.carousel,.pro-showcase,#homepage-ad-promo,.pro-contest-slider';
 let targets=[],active=null,raf=0,timer=0;
 const reduced=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
 function collect(){
  targets=Array.from(document.querySelectorAll(selector)).filter(el=>!(el.classList.contains('approved-hero')&&el.closest('.pro-showcase')));
 }
 function update(){
  raf=0;collect();const vh=window.innerHeight;
  const visible=targets.map(el=>({el,r:el.getBoundingClientRect()})).filter(x=>x.r.width>0&&x.r.height>0&&x.r.bottom>0&&x.r.top<vh);
  if(!visible.length)return;
  let chosen=visible[0],score=Infinity;
  visible.forEach(x=>{const overlap=Math.max(0,Math.min(vh,x.r.bottom)-Math.max(0,x.r.top));const center=Math.max(0,Math.min(vh,(x.r.top+x.r.bottom)/2));const distance=Math.abs(center-vh*.43)-Math.min(overlap,vh)*.18;if(distance<score){score=distance;chosen=x;}});
  const r=chosen.r,h=bot.offsetHeight||108,top=Math.max(0,r.top),bottom=Math.min(vh,r.bottom);
  let y=r.top+(r.height-h)/2;if(bottom-top>=h)y=Math.max(top,Math.min(bottom-h,y));else y=Math.max(8,Math.min(vh-h-8,(top+bottom-h)/2));
  bot.style.transform='translate3d(0,'+Math.round(y)+'px,0)';bot.classList.add('is-visible');
  if(chosen.el!==active){active=chosen.el;bot.classList.remove('is-pointing');bot.classList.add('is-running');clearTimeout(timer);timer=setTimeout(()=>{bot.classList.remove('is-running');bot.classList.add('is-pointing');},reduced?0:850);}
 }
 function schedule(){if(!raf)raf=requestAnimationFrame(update);}
 window.addEventListener('scroll',schedule,{passive:true});window.addEventListener('resize',schedule);
 if(window.visualViewport){visualViewport.addEventListener('scroll',schedule);visualViewport.addEventListener('resize',schedule);}
 if('IntersectionObserver'in window){const io=new IntersectionObserver(schedule,{threshold:[0,.1,.25,.5,.75]});collect();targets.forEach(el=>io.observe(el));}
 collect();schedule();
 if(window.matchMedia('(min-width:701px)').matches)setInterval(schedule,300);
})();
