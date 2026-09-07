/* 通用角色设计引擎：方块形变、双眼、按深度分层的彩色拖尾。无产品依赖。 */
(() => {
  'use strict';
  const definitions = [
    ['idle','待命','方块微微换重心，眼神偶尔游移，始终留在原位。','柔和双眼；偶尔侧看','8 秒长节奏','没有活跃工作','重心微移',8,'none'],
    ['listening','倾听','上半身向输入方向探出，底部留在原位，像认真侧耳。','双眼张开，注视一侧','3.8 秒；前倾后停留','用户输入或真实的监听状态','前倾探身',3.8,'none'],
    ['connecting','建立连接','两侧向内收，随后展开；第二拍比第一拍更接近完整方形。','目光从两侧回到中央','2.8 秒；收合—展开','连接正在建立','横向收合',2.8,'join'],
    ['receiving','接收','方块接住一股向下的动量，轻压后回弹，重心随之落下。','视线从上落到中央','2.8 秒；承接—回弹','正在接收输入、数据或结果','向下承接',2.8,'inward'],
    ['sending','发送','先压低，再向上伸展，把动量送出去；身体随后回收。','视线先抬起，动作后跟上','2.6 秒；蓄力—推出','正在发送数据或消息','向上推出',2.6,'outward'],
    ['thinking','思考','身体慢慢扭向一侧，再悬停转回；彩线顺着转身绕过腰部。','一眼收窄，目光略向上','5.2 秒；慢转—悬停—回转','显式思考或推理阶段','悬停扭转',5.2,'orbit'],
    ['planning','规划','方块依次倾向左、中、右三个稳定落点，最后把自己摆正。','视线先到下一个落点','3.6 秒；三段落点','显式计划与安排阶段','三段落点',3.6,'none'],
    ['searching','搜索','身体侧转探出，停一下，再去另一侧；横向行程清晰可见。','宽眼寻找，眼神先于转身','3.2 秒；探左—停—探右','正在寻找信息或目标','左右探寻',3.2,'none'],
    ['reading','阅读','方块很轻地顺着行进方向倾斜；行尾复位，再小幅下沉。','从左至右，回扫换行','3 秒；横扫—回扫—换行','顺序消费文本、图像或内容','逐行下沉',3,'none'],
    ['working','执行','底部撑住，身体压缩向前推进，再弹回准备下一拍。','双眼聚焦，注视前下方','2.2 秒；压缩—推进—回弹','工具或计算正在执行','弹性推进',2.2,'drive'],
    ['generating','生成','身体左右交替舒展，像有节奏地织出连续内容。','双眼随左右节奏交替聚焦','2.6 秒；左展—右展—停顿','正在生成内容或持续输出','左右舒展',2.6,'weave'],
    ['verifying','检查','方块先横向收紧，再纵向拉直，最后严格回到中轴。','双眼同时眯起，再恢复平齐','3 秒；收紧—对齐—停顿','正在验证、评估或复核','收紧对齐',3,'none'],
    ['coordinating','协同','上、下半身形成轻微反向扭转，随后换边，带动两条交错轨迹。','轮流关注两个方向','3.8 秒；换边扭转','正在协调多个活跃工作单元','交替扭身',3.8,'cross'],
    ['waiting','等待','方块向一侧轻靠，双眼放松；等候时留在这个重心。','半开双眼，安静侧望','6 秒；只轻移一次眼神','已知外部依赖正在等待','侧靠停留',6,'none'],
    ['awaiting-input','等待回应','先直起身，再向前探一点；双眼看向用户，保持这个姿态。','正面睁眼，注视用户','360 毫秒进入后保持','需要用户输入、选择或确认','挺身注视',0,'none'],
    ['blocked','受阻','方块向右尝试推进，仿佛受到阻力，侧面被压住后停下。','一眼收紧，一眼留意阻力','480 毫秒进入后保持','确定的障碍使工作无法继续','侧向受压',0,'none'],
    ['retrying','重试','先略向后撤，把身体重新拧紧，再沿原方向试着起步。','回望一下，再重新聚焦','3.2 秒；撤回—蓄力—再试','真实重试已开始','撤回再起',3.2,'rewind'],
    ['settling','收尾','大幅动作逐步收小，身体从轻扭转归正；彩带顺势收拢。','眼神回中，逐渐放松','3.4 秒后安定；仍可保持此态','工作进入最终整理阶段','归拢安定',0,'settle'],
    ['completed','完成','向上舒展一次，双眼弯起，落在高而端正的姿态。','对称的满意眼形','600 毫秒进入后保持','工作已经成功结束','舒展站稳',0,'none'],
    ['partial','部分完成','身体一侧已经舒展，另一侧仍略收着，保留未完全落定的形状。','一眼柔和，一眼保持注意','420 毫秒进入后保持','部分结果就绪，仍有未完成部分','非对称舒展',0,'none'],
    ['failed','失败','力气卸下来，上缘略低、底部变宽；身体稳住，不再试着推进。','双眼稍低，仍然清醒','480 毫秒卸力后保持','本次工作已失败并结束','向下卸力',0,'none'],
    ['cancelled','已停止','向前的动量被收回，身体短暂后坐，再回到较低的稳定姿态。','中性横眼，视线回中','450 毫秒刹住后保持','明确的停止或取消已经确认','回收刹停',0,'none'],
    ['paused','暂停','保持一半转身，身体收窄，像把动作暂时留在空中。','双眼半开，方向仍保留','240 毫秒收束后保持','工作明确暂停，可继续','半转悬停',0,'none'],
    ['sleeping','休息','身体柔软地压低，靠向一侧，眼睛合成两条弧线。','完全闭眼','600 毫秒进入后保持','明确休息或非工作展示','低伏合眼',0,'none'],
  ];
  const eventDefs = [
    ['appear','出现','从紧凑的小方块展开，双眼随身体睁开，落定。','从合眼到睁眼','600 毫秒','新角色首次出现','展开成形',.6,'none'],
    ['acknowledge','收到','眼睛先回应，方块前倾并点一下头，回正。','正面注意','480 毫秒','输入被确认接收','短促点头',.48,'none'],
    ['dispatch','派发','方块向右拧身再回弹，彩线随这个甩动向外舒展。','先看派发方向','720 毫秒','一次真实工作派发','拧身甩出',.72,'outward'],
    ['receive-result','接住','侧转迎向来处，身体压下接住，再舒展回中。','迎向来处，再回正','680 毫秒','一个结果返回','侧身承接',.68,'inward'],
    ['milestone','有进展','一侧肩角轻抬，身体转出短弧，再继续工作。','短暂满意','680 毫秒','有意义的阶段进展','轻抬一角',.68,'arc'],
    ['notify','注意到了','方块短促挺高，双眼放大，然后带一点弹性落回。','双眼同时张开','640 毫秒','明确的新信息提醒','挺高回落',.64,'none'],
    ['recover','恢复','受压的身体释放开来，先宽后高，沿顺滑轨迹回正。','重新聚焦','820 毫秒','收到真实的恢复证据','解压复位',.82,'join'],
    ['celebrate','庆祝','预压、跃起、转身，三条彩带绕着身形展开，再收进满意的落定。','转身时收眼，落定时弯眼','1400 毫秒','被见证的一次成功','跃起回旋',1.4,'celebrate'],
  ];
  const microDefs = [
    ['blink','眨眼','快速合拢，短停，再自然睁开。','同步开合','220 毫秒','自然眨眼','自然开合',.22,'none'],
    ['glance','看一眼','眼睛先动，头部轻跟随，再回正。','侧看回正','720 毫秒','局部注意力变化','视线先行',.72,'none'],
    ['curious','好奇','一边肩角抬起，身体轻歪，双眼一大一小。','不对称张眼','1000 毫秒','待命时的稀疏表达','歪身打量',1,'none'],
    ['content','会心','身体略向上松开，双眼柔和弯起，回落。','轻微笑眼','900 毫秒','明确的积极回应','轻松舒展',.9,'none'],
  ];
  const convert=(a,group)=>({id:a[0],name:a[1],desc:a[2],eyes:a[3],rhythm:a[4],trigger:a[5],signature:a[6],period:group==='state'?a[7]:0,duration:group==='state'?0:a[7],ribbon:a[8],group});
  const entries=[...definitions.map(a=>convert(a,'state')),...eventDefs.map(a=>convert(a,'cue')),...microDefs.map(a=>convert(a,'micro'))];
  const lookup=new Map(entries.map(s=>[s.id,s]));
  const NS='http://www.w3.org/2000/svg';
  const el=(tag,attrs={})=>{const n=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));return n;};
  const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
  const smooth=x=>{x=clamp(x);return x*x*(3-2*x);};
  const hump=(x,a,b)=>x<a||x>b?0:Math.sin(Math.PI*(x-a)/(b-a));
  const base={x:0,y:0,r:0,sx:1,sy:1,lean:0,top:0,bottom:0,shoulder:0,yaw:0,gx:0,gy:0,lh:18,rh:18,lw:8,rw:8,la:0,ra:0,ls:0,rs:0};
  const samples={idle:.18,listening:.28,connecting:.30,receiving:.47,sending:.37,thinking:.22,planning:.14,searching:.22,reading:.45,working:.28,generating:.23,verifying:.27,coordinating:.23,waiting:.18,retrying:.30};
  function poseFor(id,time,still=false){
    const s=lookup.get(id),p={...base};let c=s.period?(time%s.period)/s.period:0;
    if(still)c=samples[id]??.4;
    const tau=2*Math.PI,w=Math.sin(c*tau),soft=Math.tanh(w*2),entry=still?1:smooth(time/.48);
    switch(id){
      case'idle':p.r=.8*Math.sin(c*tau);p.y=.3*Math.sin(c*tau);p.gx=still?0:1.5*hump(c,.7,.92);break;
      case'listening':Object.assign(p,{r:-6,lean:-4,sx:.97,sy:1.05,gx:-3,gy:-1,lh:22,rh:21});p.r-=hump(c,.1,.4);break;
      case'connecting':{const q=hump(c,.05,.65);Object.assign(p,{sx:1-.17*q,sy:1+.09*q,top:3*q,bottom:-q,lh:18-5*q,rh:18-5*q,gx:0,gy:-1});break;}
      case'receiving':{const q=hump(c,.23,.65),up=hump(c,.04,.23);Object.assign(p,{y:4*q-2*up,sx:1+.13*q,sy:1-.17*q,top:-2*q,gx:0,gy:-4*(1-q),lh:20-6*q,rh:20-6*q});break;}
      case'sending':{const coil=hump(c,0,.25),push=hump(c,.25,.72);Object.assign(p,{y:3*coil-7*push,sx:1+.1*coil-.13*push,sy:1-.1*coil+.17*push,top:2*push,gy:-4*push,lh:17,rh:17});break;}
      case'thinking':Object.assign(p,{r:-9+4*w,y:-2-hump(c,.1,.55)*1.3,yaw:26*soft,lean:2*w,sx:.97,sy:1.03,gx:-3+2*w,gy:-3,lh:10,rh:19,ls:1.2,rs:1});break;
      case'planning':{const step=c<.28?-1:c<.60?0:1;Object.assign(p,{x:step*3,r:step*8,y:-hump(c%(.32),.03,.27),lean:step*2,gx:step*4,gy:-2,lh:14,rh:18});break;}
      case'searching':Object.assign(p,{x:7*soft,r:9*soft,yaw:36*soft,sx:.95,sy:1.025,gx:4.5*soft,gy:-.5,lh:23,rh:23});break;
      case'reading':{let x=c<.7?-1+2*c/.7:1-2*smooth((c-.7)/.3);Object.assign(p,{r:2*x,lean:1.7*x,y:c<.7?c*2:1.4*(1-smooth((c-.7)/.3)),gx:4*x,gy:2,lh:13,rh:13,sy:.98});break;}
      case'working':{const q=hump(c,.06,.7);Object.assign(p,{x:3*q,y:3*q,r:-6*q,lean:5*q,sx:1+.10*q,sy:1-.12*q,top:-2*q,gx:3,gy:3,lh:10,rh:10,ls:1,rs:-1});break;}
      case'generating':Object.assign(p,{r:5*w,lean:4*soft,shoulder:2*w,sx:1+.06*Math.abs(w),sy:1-.04*Math.abs(w),gx:3*soft,gy:1,lh:14-3*w,rh:14+3*w});break;
      case'verifying':{const q=hump(c,.08,.43),v=hump(c,.47,.80);Object.assign(p,{sx:1-.16*q,sy:1+.09*q+.05*v,y:-v,top:2*q,bottom:2*q,lh:6+6*v,rh:6+6*v,lw:11,rw:11,gy:1});break;}
      case'coordinating':Object.assign(p,{lean:7*soft,shoulder:3*w,r:2*w,yaw:22*soft,gx:4*soft,gy:-.5,lh:16,rh:16,top:1.5,bottom:-1});break;
      case'waiting':Object.assign(p,{r:8,lean:3,x:2,y:2,sx:1.03,sy:.97,gx:2+hump(c,.72,.93),lh:10,rh:10});break;
      case'awaiting-input':Object.assign(p,{r:0,y:-3,top:-2,bottom:2,sx:.94,sy:1.10,lh:24,rh:24,lw:9,rw:9,gy:-1});break;
      case'blocked':Object.assign(p,{x:5*entry,r:-8,lean:-6,sx:.82,sy:1.05,top:2,bottom:-2,shoulder:-2,gx:4,gy:0,lh:8,rh:19,ls:1.7});break;
      case'retrying':{const back=hump(c,.02,.42),push=hump(c,.45,.85);Object.assign(p,{x:-5*back+3*push,r:11*back-5*push,lean:-5*back+4*push,sx:1-.1*back,sy:1+.08*back,gx:-3*back+3*push,lh:12,rh:15,gy:1});break;}
      case'settling':{const a=still?0:1-smooth(time/3.4);Object.assign(p,{r:10*a*Math.cos(time*2.8),lean:3*a,y:-2*a,sx:1+.04*a,sy:1-.04*a,lh:16,rh:16});break;}
      case'completed':Object.assign(p,{y:-2,sy:1.05,sx:1.02,top:-1,bottom:0,lh:4,rh:4,lw:12,rw:12,la:5,ra:5});if(!still)p.y-=2*hump(time,0,.6);break;
      case'partial':Object.assign(p,{r:-4,shoulder:8,lean:-2,top:-1,sy:1.02,lh:4,rh:17,lw:11,la:4,gx:1});break;
      case'failed':Object.assign(p,{y:6,sx:1.12,sy:.78,top:3,bottom:-4,shoulder:1,lh:9,rh:9,ls:-2,rs:2,gy:4});break;
      case'cancelled':Object.assign(p,{y:3,sx:1.04,sy:.89,lean:0,top:0,bottom:0,lh:4,rh:4,lw:12,rw:12,gy:1});if(!still){p.x=-5*hump(time,0,.45);p.r=7*hump(time,0,.45);}break;
      case'paused':Object.assign(p,{r:-12,y:-3,yaw:38,sx:.92,sy:1.05,gx:-2,lh:7,rh:7,lw:9,rw:9});break;
      case'sleeping':Object.assign(p,{r:10,y:7,sx:1.14,sy:.70,top:4,bottom:-4,lh:2.2,rh:2.2,lw:12,rw:12,la:-2,ra:-2,gy:3});break;
    }
    if(s.group!=='state'){
      const q=still?(id==='celebrate'?.84:.46):clamp(time/s.duration),a=Math.sin(q*Math.PI);
      if(id==='appear')Object.assign(p,{sx:.60+.40*smooth(q/.7),sy:.60+.40*smooth(q/.7),y:8*(1-smooth(q/.8)),lh:2+16*smooth((q-.1)/.6),rh:2+16*smooth((q-.1)/.6)});
      if(id==='acknowledge')Object.assign(p,{r:-3*a,lean:-2*a,y:4*a,sx:1+.04*a,sy:1-.06*a,gy:3*a,lh:18-7*a,rh:18-7*a});
      if(id==='dispatch')Object.assign(p,{r:14*a,lean:7*a,yaw:50*a,x:4*a,gx:4*a,lh:16,rh:16});
      if(id==='receive-result')Object.assign(p,{r:-9*a,lean:-4*a,x:-3*a,y:3*a,sx:1+.12*a,sy:1-.15*a,gx:-4*a,gy:2*a});
      if(id==='milestone')Object.assign(p,{r:-8*a,shoulder:5*a,y:-3*a,lh:18-13*a,rh:18-13*a,la:4*a,ra:4*a});
      if(id==='notify')Object.assign(p,{y:-5*a,sx:1-.09*a,sy:1+.15*a,lh:18+7*a,rh:18+7*a,top:-2*a});
      if(id==='recover'){const back=1-smooth(q),release=hump(q,.15,.85);Object.assign(p,{sx:1-.18*back+.06*release,sy:1+.1*back-.04*release,lean:-5*back,r:-8*back,y:-2*release,lh:18-8*back,rh:18});}
      if(id==='celebrate'){const coil=hump(q,0,.18),jump=hump(q,.18,.80),turn=smooth((q-.2)/.54);Object.assign(p,{y:4*coil-10*jump,r:-12*jump,sy:1-.12*coil+.09*jump,sx:1+.1*coil-.07*jump,yaw:360*turn,lh:18-14*smooth((q-.65)/.25),rh:18-14*smooth((q-.65)/.25),lw:8+4*smooth((q-.65)/.25),rw:8+4*smooth((q-.65)/.25),la:5*smooth((q-.65)/.25),ra:5*smooth((q-.65)/.25)});}
      if(id==='blink'){const f=still?1:q<.25?smooth(q/.25):q<.43?1:1-smooth((q-.43)/.57);Object.assign(p,{lh:18-15.8*f,rh:18-15.8*f,lw:8+2*f,rw:8+2*f});}
      if(id==='glance')Object.assign(p,{gx:4*a,gy:-a,r:2*a,yaw:9*a});
      if(id==='curious')Object.assign(p,{r:-10*a,shoulder:4*a,lean:-2*a,lh:18-8*a,rh:18+5*a,gx:-2*a});
      if(id==='content')Object.assign(p,{y:-2*a,sy:1+.035*a,lh:18-14*a,rh:18-14*a,lw:8+3*a,rw:8+3*a,la:4*a,ra:4*a});
      if(q>=1&&id!=='celebrate')Object.assign(p,base);
    }
    return p;
  }
  function eye(cx,cy,w,h,slope,arch){const l=cx-w/2,r=cx+w/2,top=cy-h/2,bot=cy+h/2,k=Math.min(w*.46,h*.5);return `M${l} ${cy-slope}C${l} ${top-slope} ${cx-k} ${top-arch} ${cx} ${top-arch}C${cx+k} ${top-arch} ${r} ${top+slope} ${r} ${cy+slope}C${r} ${bot+slope} ${cx+k} ${bot-arch} ${cx} ${bot-arch}C${cx-k} ${bot-arch} ${l} ${bot-slope} ${l} ${cy-slope}Z`;}
  function bodyPath(p){
    const points=[[14+p.top+p.lean,14-p.shoulder],[86-p.top+p.lean,14+p.shoulder],[86-p.bottom-p.lean,86],[14+p.bottom-p.lean,86]];
    const mix=(a,b,k)=>[a[0]+(b[0]-a[0])*k,a[1]+(b[1]-a[1])*k];
    let d='';for(let i=0;i<4;i++){const cur=points[i],prev=points[(i+3)%4],next=points[(i+1)%4],a=mix(cur,prev,.224),b=mix(cur,next,.224);d+=`${i?'L':'M'}${a[0]} ${a[1]}Q${cur[0]} ${cur[1]} ${b[0]} ${b[1]}`;}return d+'Z';
  }
  const ribbonStyles={none:{strength:0},orbit:{strength:.70,speed:.70,tilt:-15,length:2.7,lanes:2},drive:{strength:.80,speed:1.9,tilt:-12,length:2.8,lanes:2},weave:{strength:.82,speed:1.3,tilt:24,length:2.5,lanes:2},cross:{strength:.88,speed:1.05,tilt:32,length:3.0,lanes:3},join:{strength:.72,speed:1.15,tilt:-22,length:2.5,lanes:2},inward:{strength:.9,speed:-1.15,tilt:20,length:3.5,lanes:2},outward:{strength:.9,speed:1.5,tilt:-24,length:3.5,lanes:2},rewind:{strength:.65,speed:-1.4,tilt:-14,length:2.7,lanes:2},settle:{strength:.75,speed:.9,tilt:18,length:3.1,lanes:2},arc:{strength:.8,speed:1.3,tilt:-20,length:2.4,lanes:1},celebrate:{strength:1,speed:2.5,tilt:30,length:4.1,lanes:3}};
  let nextId=0;
  class Bot {
    constructor(host,size,id,{frozen=false,ink=null}={}){
      this.size=size;this.state=lookup.get(id);this.time=0;this.frozen=frozen;this.visible=true;this.initial=false;this.pose={...base};this.velocity=Object.fromEntries(Object.keys(base).map(k=>[k,0]));this.pointer={x:0,y:0};this.ribbonPhase=.6;this.ribbon={strength:0,speed:1,tilt:0,length:2.7,lanes:2};this.id='ribbon-'+nextId++;
      this.svg=el('svg',{viewBox:'0 0 100 100',class:'bot-svg','aria-hidden':'true'});if(ink)this.svg.style.setProperty('--ink',ink);
      const defs=el('defs');this.gradient=el('linearGradient',{id:this.id,x1:'0%',y1:'85%',x2:'100%',y2:'15%'});
      ['var(--ribbon-cyan)','var(--ribbon-blue)','var(--ribbon-violet)','var(--ribbon-pink)','var(--ribbon-gold)'].forEach((color,i)=>this.gradient.append(el('stop',{offset:i*25+'%','stop-color':color})));defs.append(this.gradient);this.svg.append(defs);
      this.back=el('g',{'data-layer':'ribbon-back'});this.front=el('g',{'data-layer':'ribbon-front'});this.group=el('g',{'data-layer':'body'});this.body=el('path',{class:'bot-body'});this.side=el('path',{class:'bot-turn-side'});this.outerClip=el('path');this.faceClip=el('path');const outer=el('clipPath',{id:this.id+'-body'}),frontClip=el('clipPath',{id:this.id+'-face'});outer.append(this.outerClip);frontClip.append(this.faceClip);defs.append(outer,frontClip);this.details=el('g',{'clip-path':`url(#${this.id}-body)`});this.faceWindow=el('g',{'clip-path':`url(#${this.id}-face)`});this.face=el('g');this.eyes=[el('path',{class:'bot-eye'}),el('path',{class:'bot-eye'})];this.face.append(...this.eyes);this.faceWindow.append(this.face);this.details.append(this.side,this.faceWindow);this.group.append(this.body,this.details);this.svg.append(this.back,this.group,this.front);
      this.paths=[0,1,2].map(()=>{const b=el('path',{fill:`url(#${this.id})`}),f=el('path',{fill:`url(#${this.id})`});this.back.append(b);this.front.append(f);return{back:b,front:f};});host.append(this.svg);this.draw(0,{still:true});
    }
    set(id){this.state=lookup.get(id);this.time=0;}
    draw(dt,{still=false,reduce=false,trails=true,repeat=false,instantRibbons=false}={}){
      if(!still)this.time+=dt;
      const s=this.state,quiet=still||this.frozen||reduce;
      const time=repeat&&s.duration?this.time%(s.duration+1.25):this.time;
      const p=poseFor(s.id,time,quiet);
      const scale=this.size<28?.34:this.size<48?.55:1;
      if(!quiet&&s.group==='state'&&s.period&&s.id!=='verifying'){
        const b=this.time%8.3;if(b>6.9&&b<7.12){const f=Math.sin((b-6.9)/.22*Math.PI);p.lh=Math.max(2.2,p.lh*(1-.9*f));p.rh=Math.max(2.2,p.rh*(1-.9*f));}
      }
      if(!quiet&&s.id==='idle'){p.gx+=this.pointer.x;p.gy+=this.pointer.y;}
      for(const k of ['x','y','r','lean','shoulder'])p[k]*=scale;
      p.sx=1+(p.sx-1)*Math.max(.6,scale);p.sy=1+(p.sy-1)*Math.max(.6,scale);
      if(this.size<32){p.lw=Math.max(p.lw,160/this.size);p.rw=Math.max(p.rw,160/this.size);}
      for(const k of Object.keys(base)){
        if(quiet||!this.initial){this.pose[k]=p[k];this.velocity[k]=0;continue;}
        let target=p[k];if(k==='yaw')target=this.pose[k]+((target-this.pose[k]+540)%360)-180;
        const lids=(k==='lh'||k==='rh')&&(s.id==='blink'||this.time%8.3>6.9&&this.time%8.3<7.4);
        const f=lids?65:['gx','gy','lh','rh','lw','rw','la','ra','ls','rs'].includes(k)?30:20;
        const damping=['sx','sy','y'].includes(k)?.83:.96;
        for(let left=dt;left>0;){const h=Math.min(left,1/120);this.velocity[k]+=(f*f*(target-this.pose[k])-2*damping*f*this.velocity[k])*h;this.pose[k]+=this.velocity[k]*h;left-=h;}
      }
      this.initial=true;const v={...this.pose,yaw:this.turnOverride??this.pose.yaw},angle=v.yaw*Math.PI/180,front=Math.cos(angle),direction=Math.sin(angle)>=0?1:-1;
      // 平面转向绘制：外轮廓保持体量，正面让出的面积由侧面接住。
      const faceWidth=Math.abs(front),width=.9+.1*faceWidth,edge=direction>0?14+72*(1-faceWidth):86-72*(1-faceWidth);
      this.group.setAttribute('transform',`translate(${v.x} ${v.y}) translate(50 50) rotate(${v.r}) scale(${v.sx*width} ${v.sy}) translate(-50 -50)`);
      const contour=bodyPath(v);this.body.setAttribute('d',contour);this.outerClip.setAttribute('d',contour);
      const seam=`M${edge} -20C${edge-2*direction} 25 ${edge+2*direction} 75 ${edge} 120`;
      this.side.setAttribute('d',seam+(direction>0?'H-20V-20Z':'H120V-20Z'));
      this.side.setAttribute('opacity',smooth((1-faceWidth)/.12)*.65);
      this.faceClip.setAttribute('d',seam+(direction>0?'H120V-20Z':'H-20V-20Z'));
      const faceCenter=50+direction*36*(1-faceWidth);
      this.face.setAttribute('transform',`translate(${faceCenter+v.gx*faceWidth} ${v.gy}) scale(${faceWidth} 1) translate(-50 0)`);
      this.face.setAttribute('opacity',smooth((front-.12)/.28));
      this.eyes[0].setAttribute('d',eye(40,46,v.lw,Math.max(2,v.lh),v.ls,v.la));this.eyes[1].setAttribute('d',eye(60,46,v.rw,Math.max(2,v.rh),v.rs,v.ra));
      const style={speed:1,tilt:0,length:2.7,lanes:2,...ribbonStyles[s.ribbon]};
      if(s.group!=='state')style.strength*=quiet?.8:hump(time/s.duration,.06,1);
      if(s.id==='settling'){const fade=quiet?0:1-smooth(time/3.4);style.strength*=fade;style.speed*=fade;style.length*=.4+.6*fade;}
      if(!trails||this.size<48||reduce)style.strength=0;
      for(const k of Object.keys(this.ribbon)){const target=style[k]??this.ribbon[k];this.ribbon[k]=quiet||instantRibbons?target:this.ribbon[k]+(target-this.ribbon[k])*(1-Math.exp(-dt*9));}
      if(!quiet)this.ribbonPhase+=dt*this.ribbon.speed*(1+.12*Math.min(1,Math.abs(this.velocity.r)/40));
      this.paintRibbons(quiet?.85:this.ribbonPhase,quiet,time);
    }
    paintRibbons(phase,quiet,time){
      const cfg=this.ribbon,s=this.state;const intensity=cfg.strength;
      for(let lane=0;lane<3;lane++){
        const alpha=intensity*clamp(cfg.lanes-lane);const paths={front:[],back:[]};
        if(alpha>.004){
          const tilt=(cfg.tilt*(lane===1?-1:1)+lane*9+this.pose.r*.4)*Math.PI/180;
          const radius=51+lane*3;const ry=17+lane*3;const phaseOffset=lane*2.3;
          const prog=s.period?(time%s.period)/s.period:clamp(time/(s.duration||3.4));
          const drift=(s.ribbon==='inward'?-6*hump(prog,.05,.95):s.ribbon==='outward'?7*hump(prog,.1,.9):s.ribbon==='join'?-5*hump(prog,.05,.85):0)+(1-this.pose.sy)*12;
          const at=u=>{const a=phase+phaseOffset-(1-u)*cfg.length;const x=(radius+drift)*Math.cos(a),y=ry*Math.sin(a);return{x:50+x*Math.cos(tilt)-y*Math.sin(tilt)+this.pose.x*.35,y:58+x*Math.sin(tilt)+y*Math.cos(tilt)+this.pose.y*.35,z:Math.sin(a)};};
          const steps=this.size<80?30:54;
          const points=Array.from({length:steps+1},(_,i)=>({...at(i/steps),u:i/steps}));
          const edges=points.map((p,i)=>{const a=points[Math.max(0,i-1)],b=points[Math.min(steps,i+1)],dx=b.x-a.x,dy=b.y-a.y,len=Math.hypot(dx,dy)||1;
            const width=.08+2.4*Math.pow(Math.sin(Math.PI*p.u),.7)*(.4+.6*p.u);
            return{left:[p.x-dy/len*width,p.y+dx/len*width],right:[p.x+dy/len*width,p.y-dx/len*width]};});
          let start=0;
          while(start<steps){
            const front=(points[start].z+points[start+1].z)>0;let end=start+1;
            while(end<steps&&((points[end].z+points[end+1].z)>0)===front)end++;
            const slice=edges.slice(start,end+1),outline=[...slice.map(p=>p.left),...slice.map(p=>p.right).reverse()];
            paths[front?'front':'back'].push(outline.map((p,i)=>(i?'L':'M')+p[0]+' '+p[1]).join('')+'Z');
            start=end;
          }
        }
        this.paths[lane].front.setAttribute('d',paths.front.join(''));this.paths[lane].back.setAttribute('d',paths.back.join(''));
        this.paths[lane].front.setAttribute('opacity',alpha*.95);this.paths[lane].back.setAttribute('opacity',alpha*.62);
      }
    }
  }
  window.BotMotion={Bot,entries,lookup,poseFor,base};
})();
