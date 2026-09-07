/* 设计评审播放器：通用情境、实际尺寸、纯本体对照与彩带开关。 */
(() => {
  'use strict';
  const {Bot,entries,lookup}=window.BotMotion,$=id=>document.getElementById(id);
  let reduce=matchMedia('(prefers-reduced-motion: reduce)').matches,trails=true,paused=false,speed=1,selected='idle',filter='state';
  let raf=0,last=0,scene=null,sceneIndex=-1,sceneElapsed=0,waitingApproval=false;
  const mainBot=new Bot($('hero'),208,selected);
  const sizeBots=[20,24,32,48,64].map(size=>{const item=document.createElement('div');item.className='size-item';const host=document.createElement('div');host.style.width=size+'px';host.style.height=size+'px';const label=document.createElement('span');label.textContent=size+'px';item.append(host,label);$('sizes').append(item);return new Bot(host,size,selected);});
  const activeBots=[mainBot,...sizeBots];
  const compareBots=[];
  ['thinking','working','sending','coordinating','blocked','celebrate'].forEach(id=>{const s=lookup.get(id),item=document.createElement('article');item.className='motion-comparison';const host=document.createElement('div');host.className='comparison-bot';const title=document.createElement('h3');title.textContent=s.name;const text=document.createElement('p');text.textContent=s.signature;item.append(host,title,text);$('comparisons').append(item);compareBots.push(new Bot(host,94,id));});
  const allBots=[...activeBots,...compareBots];
  const observer=new IntersectionObserver(items=>{for(const item of items){const b=allBots.find(b=>b.svg===item.target);if(b)b.visible=item.isIntersecting;}wake();},{rootMargin:'60px'});
  allBots.forEach(b=>observer.observe(b.svg));
  const identities=[['墨色',null],['靛蓝','var(--role-a)'],['青绿','var(--role-b)'],['紫色','var(--role-c)'],['赭色','var(--role-d)']];
  identities.forEach(([name,ink])=>{const item=document.createElement('article');item.className='identity';const host=document.createElement('div');const label=document.createElement('p');label.textContent=name;item.append(host,label);$('identities').append(item);new Bot(host,70,'idle',{frozen:true,ink});});
  const turnStudies=[];for(const [id,angle]of [['turn-front',0],['turn-quarter',45],['turn-side',90],['turn-back',180]]){const b=new Bot($(id),80,'idle',{frozen:true});b.turnOverride=angle;b.draw(0,{still:true,trails:false});turnStudies.push(b);}
  function renderCatalog(){
    $('catalog-grid').replaceChildren();
    entries.filter(s=>s.group===filter).forEach(s=>{const b=document.createElement('button');b.type='button';b.className='state-tile';b.dataset.state=s.id;b.setAttribute('aria-pressed',String(s.id===selected));b.setAttribute('aria-label',`预览${s.name}`);const bot=new Bot(b,58,s.id,{frozen:true});bot.draw(0,{still:true,trails,reduce});const label=document.createElement('span');label.className='tile-name';label.textContent=s.name;const sub=document.createElement('span');sub.className='tile-meta';sub.textContent=s.signature;b.append(label,sub);b.addEventListener('click',()=>{stopScene();select(s.id);document.querySelector('.playground').scrollIntoView({block:'start',behavior:'instant'});});$('catalog-grid').append(b);});
    document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.filter===filter)));
  }
  function select(id,announce=true){
    selected=id;const s=lookup.get(id);activeBots.forEach(b=>b.set(id));
    for(const [field,value]of Object.entries({'detail-name':s.name,'detail-desc':s.desc,'detail-eyes':s.eyes,'detail-rhythm':s.rhythm,'detail-trigger':s.trigger,'detail-body':s.signature,'hero-state':s.name,'state-code':s.id,'family-label':{state:'持续状态',cue:'事件动作',micro:'微表情'}[s.group]}))$(field).textContent=value;
    const list=entries.filter(x=>x.group===s.group);$('state-index').textContent=String(list.indexOf(s)+1).padStart(2,'0')+' / '+list.length;
    document.querySelectorAll('[data-state]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.state===id)));
    if(announce)$('announcement').textContent='正在预览：'+s.name+' · '+s.signature;
    if(reduce||paused)activeBots.forEach(b=>b.draw(0,{still:true,reduce,trails}));
    wake();
  }
  const scenarios={
    normal:[['acknowledge',.7],['connecting',2.5],['thinking',3],['planning',2.5],['working',2.5],['generating',2.5],['verifying',2.5],['settling',3.5],['celebrate',1.8],['completed',0]],
    approval:[['working',2.5],['awaiting-input',-1],['acknowledge',.6],['generating',2.5],['settling',3.5],['completed',0]],
    recovery:[['working',2.5],['blocked',2],['retrying',3.3],['recover',1.1],['working',2.5],['completed',0]],
    partial:[['receiving',2.5],['working',2.5],['verifying',2.5],['settling',3.5],['partial',0]],
    rapid:[['thinking',.23],['working',.23],['sending',.23],['thinking',.23],['coordinating',.23],['generating',.23],['awaiting-input',0]],
  };
  function enterStep(){sceneElapsed=0;const[id,duration]=scene[sceneIndex];select(id);[...$('sequence-track').children].forEach((li,i)=>li.className=i===sceneIndex?'active':i<sceneIndex?'past':'');waitingApproval=duration===-1;$('continue').hidden=!waitingApproval;$('sequence-label').textContent=waitingApproval?'演示已停住：回应之后才继续。':duration===0?'演示结束 · '+lookup.get(id).name:'演示中 · '+lookup.get(id).name;if(duration===0){scene=null;$('stop').hidden=true;}}
  function startScene(name){stopScene();paused=false;syncControls();scene=scenarios[name];sceneIndex=0;sceneElapsed=0;$('sequence-track').replaceChildren();scene.forEach(([id])=>{const li=document.createElement('li');li.textContent=lookup.get(id).name;$('sequence-track').append(li);});document.querySelectorAll('[data-scenario]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.scenario===name)));$('stop').hidden=false;enterStep();document.querySelector('.playground').scrollIntoView({block:'start',behavior:'instant'});wake();}
  function stopScene(){scene=null;waitingApproval=false;$('continue').hidden=true;$('stop').hidden=true;document.querySelectorAll('[data-scenario]').forEach(b=>b.setAttribute('aria-pressed','false'));$('sequence-label').textContent='手动预览 · 可选择任意动作。';}
  function syncControls(){$('pause').textContent=paused?'继续预览':'暂停预览';$('pause').setAttribute('aria-pressed',String(paused));$('motion-indicator').textContent=reduce?'静态代表姿态':paused?'当前帧已暂停':trails?'本体 + 彩色拖尾':'仅本体';}
  function alive(b){const s=b.state;return s.period>0||b.time<(s.id==='settling'?4.4:s.duration?s.duration+.9:1.1);}
  function tick(now){
    raf=0;if(document.hidden||paused)return;const dt=last?Math.min((now-last)/1000,.04)*speed:0;last=now;
    if(scene&&!waitingApproval){sceneElapsed+=dt;const d=scene[sceneIndex][1];if(d>0&&sceneElapsed>=d){sceneIndex++;enterStep();}}
    if(!reduce){activeBots.filter(b=>b.visible&&alive(b)).forEach(b=>b.draw(dt,{trails}));compareBots.filter(b=>b.visible).forEach(b=>b.draw(dt,{trails,repeat:true}));}
    if((!reduce&&(activeBots.some(b=>b.visible&&alive(b))||compareBots.some(b=>b.visible)))||scene&&!waitingApproval)raf=requestAnimationFrame(tick);
  }
  function wake(){if(!raf&&!document.hidden&&!paused){last=0;raf=requestAnimationFrame(tick);}}
  document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{filter=b.dataset.filter;renderCatalog();}));
  document.querySelectorAll('[data-scenario]').forEach(b=>b.addEventListener('click',()=>startScene(b.dataset.scenario)));
  $('rapid').addEventListener('click',()=>startScene('rapid'));
  $('urgent').addEventListener('click',()=>{stopScene();paused=false;syncControls();select('awaiting-input');$('sequence-label').textContent='立即打断 · 方块收住动作，等待回应。';});
  $('continue').addEventListener('click',()=>{if(scene&&waitingApproval){waitingApproval=false;sceneIndex++;enterStep();wake();}});
  $('stop').addEventListener('click',()=>{stopScene();$('sequence-track').replaceChildren();select('idle');});
  $('pause').addEventListener('click',()=>{paused=!paused;syncControls();if(paused){cancelAnimationFrame(raf);raf=0;}else wake();});
  $('replay').addEventListener('click',()=>{stopScene();paused=false;syncControls();select(selected);});
  function setTrails(value){trails=value;$('trails').checked=value;$('compare-trails').textContent=value?'仅看本体':'显示彩带';allBots.forEach(b=>b.draw(0,{reduce,trails,still:reduce,instantRibbons:true}));renderCatalog();syncControls();wake();}
  $('trails').addEventListener('change',e=>setTrails(e.target.checked));
  $('compare-trails').addEventListener('click',()=>setTrails(!trails));
  $('speed').addEventListener('change',e=>{speed=Number(e.target.value);});
  function setReduce(value){reduce=value;$('reduce').checked=value;allBots.forEach(b=>b.draw(0,{still:true,reduce,trails}));renderCatalog();syncControls();cancelAnimationFrame(raf);raf=0;wake();}
  $('reduce').checked=reduce;$('reduce').addEventListener('change',e=>setReduce(e.target.checked));matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',e=>setReduce(e.matches));
  $('theme').addEventListener('click',()=>{const dark=document.documentElement.dataset.theme!=='dark';document.documentElement.dataset.theme=dark?'dark':'light';$('theme').textContent=dark?'切换浅色':'切换深色';});
  if(matchMedia('(prefers-color-scheme: dark)').matches){document.documentElement.dataset.theme='dark';$('theme').textContent='切换浅色';}
  $('stage').addEventListener('pointermove',e=>{if(e.pointerType!=='mouse'||selected!=='idle'||reduce)return;const r=$('stage').getBoundingClientRect();mainBot.pointer.x=Math.max(-3,Math.min(3,((e.clientX-r.left)/r.width-.5)*6));mainBot.pointer.y=Math.max(-2,Math.min(2,((e.clientY-r.top)/r.height-.5)*4));wake();});
  $('stage').addEventListener('pointerleave',()=>{mainBot.pointer={x:0,y:0};wake();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(raf);raf=0;}else wake();});
  window.addEventListener('pagehide',()=>{cancelAnimationFrame(raf);raf=0;observer.disconnect();});
  window.hagentDesign={version:4,entries:entries.map(({id,group})=>({id,group})),snapshot:()=>({selected,reduce,trails,paused,speed,scene:!!scene,waitingApproval,time:mainBot.time,raf:!!raf,pose:{...mainBot.pose},ribbon:{...mainBot.ribbon},visible:allBots.filter(b=>b.visible).length})};
  renderCatalog();select(selected,false);syncControls();if(reduce)setReduce(true);wake();
})();
