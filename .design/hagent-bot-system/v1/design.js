/* 独立设计播放器：所有几何与动作均为本次样片绘制；不连接产品状态。 */
(() => {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const $ = id => document.getElementById(id);
  const states = [
    ['idle','待命','安静地在场，偶尔抬眼看一眼。','柔和双眼，保持正面','7–12 秒自然眨眼','当前没有活跃任务','',0],
    ['listening','倾听','注意力朝向输入区域，接住用户的话。','略张双眼，轻侧头','轻点头后稳定注视','用户正在输入；语音需真实录音能力','',0],
    ['connecting','准备环境','目光集中，连接端点靠近后停一下。','双眼聚焦，微微前倾','3 秒，动作与停顿交替','会话创建或真实环境准备','link',3],
    ['uploading','上传文件','视线追随向上的文件，身体保持安定。','短暂向上看，再归中','2.4 秒；无进度时不显示百分比','实际文件上传中','upload',2.4],
    ['parsing','解析原文','读完一行，再把目光移到下一行。','横向扫视，轻微换行','2.8 秒，逐行扫描','原文解析事件与真实页数','scan',2.8],
    ['thinking','思考','看向左上，停一拍，再回到眼前。','双眼略不对称，目光上移','4.8 秒；身体大部分时间安定','思考增量或更具体活动尚未到达','',4.8],
    ['planning','规划步骤','从第一个落点看到第三个，逐步组织顺序。','三个有停留的视线落点','3.2 秒，阶梯式节奏','明确的计划工具或规划阶段','steps',3.2],
    ['searching','检索','先定位，再扫向另一侧；每次都有短暂停留。','左右寻找，头部稍后跟随','2.8 秒；非匀速摇头','搜索与查询定位工具活跃','search',2.8],
    ['reading','阅读','眼睛沿短行移动，身体几乎不动。','顺序阅读，行尾停顿','3 秒，扫视与换行','正在读取文件或矩阵内容','read',3],
    ['working','执行','沉下注意力，专注于当前操作。','略收双眼，短暂下视','4.8 秒，一次轻微重心交换','未分类的真实活跃工具','work',4.8],
    ['writing','编写','落笔、停笔、再写一小段，偶尔抬眼。','沿书写方向移动','2.6 秒，两段书写后停顿','文件写入、编辑或整理文字回复','pen',2.6],
    ['verifying','核验','先聚焦，再对齐，逐项检查。','双眼收拢，再平齐','3.2 秒；检查不代表已通过','显式校验工具正在执行','verify',3.2],
    ['coordinating','协同','留意每个子任务的来回，主角色保持稳定。','依次看向左右任务','3.6 秒，连接点传递','确有活跃子任务需要协调','nodes',3.6],
    ['waiting','等待结果','知道在等什么，也给过程一点空间。','放松双眼，短看任务方向','6 秒一次轻移眼','已知外部依赖或队列等待','clock',6],
    ['awaiting-input','等待确认','停止手头的动作，抬眼看向你。','睁眼注视，微微前倾','200 毫秒入场后落定','明确的人工介入请求','question',0],
    ['blocked','需要处理','收起工作动作，把需要处理的事交代清楚。','轻不对称，保持清醒','200 毫秒内收束，随后静止','确定缺少资源、权限或关键依赖','alert',0],
    ['reconnecting','连接恢复中','关注正在重新接上的连接。','中性眼神看向连接点','3.6 秒，端点间轻呼应','真实重连或重试已经开始','retry',3.6],
    ['delivering','整理交付','从工作中抬起头，把成果安放到位。','抬眼、回正、落定','3 秒，文件滑入托盘','发布、装载结果或真实导出过程','deliver',3],
    ['completed','已完成','一次满意的点头之后，留住完成的神态。','上拱双眼，正面安定','持续姿态；庆祝是另一个事件','本轮成功且适用的产物已经就绪','check',0],
    ['partial','部分完成','保留已经完成的部分，也留意未解决的问题。','一眼柔和，一眼关注','静态，不播放成功庆祝','有证据的缺页或部分产物失败','partial',0],
    ['failed','执行失败','停止动作，保留清晰的错误与下一步。','目光略低，眼睛仍清醒','一次收束后静止','执行终止且没有恢复','cross',0],
    ['cancelled','已停止','工作减速，身体回正，安静落定。','双眼平齐，中性表达','停止后保持','明确确认的取消；关闭面板不触发','stop',0],
    ['paused','已暂停','暂时收起动作，保持可恢复的状态。','双眼半开','静态，等真实恢复信号','后端确认暂停；切后台不触发','pause',0],
    ['sleeping','休息','轻轻合眼，安静地休息。','两道闭合眼缝，轻侧头','静态；工作中禁止自动睡着','非工作展示或明确的休息形象','',0],
  ].map(a => ({id:a[0],name:a[1],desc:a[2],eyes:a[3],rhythm:a[4],trigger:a[5],glyph:a[6],period:a[7],group:'state'}));
  const cues = [
    ['appear','出现','轮廓展开，双眼打开，然后站稳。','由闭合到睁开','480 毫秒，单次','新身份首次出现','',.48],
    ['acknowledge','收到任务','先注意到输入，再给一个干脆的小点头。','看向输入，再回正','420 毫秒，单次','用户任务已被接收','',.42],
    ['dispatch','派发任务','看向子任务，一个小连接点向外移出。','视线先行，身体后随','560 毫秒，单次','新的子调用；批量派发合并','nodes',.56],
    ['receive-result','收到结果','迎向回来的结果，再轻轻点头。','侧看，回中','480 毫秒，单次','子调用返回了结果','nodes',.48],
    ['milestone','阶段完成','抬眼，一点短暂的亮意，继续手头的工作。','双眼短暂微弯','520 毫秒，单次','重要阶段已有可信成果','spark',.52],
    ['notify','有新消息','轻抬头，双眼略张，再回落。','注意到变化','600 毫秒，单次','一次明确提醒，不反复催促','notice',.6],
    ['recover','恢复连接','连接重新接合，注意力回到任务上。','从放松到聚焦','560 毫秒，单次','已经收到恢复成功的证据','link',.56],
    ['celebrate','交付完成','预压、轻跃、落定，最后留住满意的眼神。','落定后双眼微弯','720 毫秒，单次','被见证的真实成功交付','spark',.72],
  ].map(a=>({id:a[0],name:a[1],desc:a[2],eyes:a[3],rhythm:a[4],trigger:a[5],glyph:a[6],duration:a[7],group:'cue'}));
  const micros = [
    ['blink','眨眼','合拢、短停、睁开，自然地换一口气。','双眼同步开合','200 毫秒','自然节奏或局部回应','',.2],
    ['glance','看一眼','眼睛先看过去，头部稍后跟上，再回正。','局部注意力转移','650 毫秒','主头像附近的指针或焦点','',.65],
    ['curious','好奇','一只眼睛稍大，轻轻歪头，然后回到待命。','轻微不对称','850 毫秒','待命期稀疏出现','',.85],
    ['content','会心','双眼微弯，给一个很轻的肯定。','满意的弧形眼','800 毫秒','明确的正向反馈或非工作展示','',.8],
  ].map(a=>({id:a[0],name:a[1],desc:a[2],eyes:a[3],rhythm:a[4],trigger:a[5],glyph:a[6],duration:a[7],group:'micro'}));
  const entries=[...states,...cues,...micros], lookup=new Map(entries.map(s=>[s.id,s]));
  const glyphs={
    link:'M66 77H71M79 77H84M72 73L78 81M72 81L78 73',
    upload:'M76 85V68M70 74L76 68L82 74M67 85H85',
    scan:'M68 66H83V87H68ZM65 76H86',
    steps:'M65 83H71V77H77V71H84',
    search:'M79 79L87 87M82 74A8 8 0 1 1 66 74A8 8 0 1 1 82 74',
    read:'M68 68H84V87H68ZM72 74H80M72 79H80M72 84H77',
    work:'M68 70L75 77L68 84M78 84H86',
    pen:'M68 86L70 78L81 67L87 73L76 84ZM72 76L78 82M68 89H88',
    verify:'M65 70H77M65 77H74M65 84H77M84 69H89V85H84M80 77H86',
    nodes:'M65 82L76 71L87 82M68 82A3 3 0 1 1 62 82A3 3 0 1 1 68 82M79 70A3 3 0 1 1 73 70A3 3 0 1 1 79 70M90 82A3 3 0 1 1 84 82A3 3 0 1 1 90 82',
    clock:'M86 77A10 10 0 1 1 66 77A10 10 0 1 1 86 77M76 70V77L81 80',
    question:'M72 72C72 66 82 66 82 72C82 77 76 76 76 80M76 85V85.2',
    alert:'M76 67V79M76 85V85.2',
    retry:'M67 77A9 9 0 0 1 82 70L86 73M86 67V73H80M86 80A9 9 0 0 1 71 86L67 83M67 89V83H73',
    deliver:'M67 82V88H87V82M77 66V81M71 75L77 81L83 75',
    check:'M67 78L74 85L87 70',
    partial:'M86 77A10 10 0 1 1 66 77A10 10 0 1 1 86 77M76 67V87M76 70L82 74M76 76L83 80M76 82L80 85',
    cross:'M69 70L83 84M83 70L69 84',
    stop:'M69 70H83V84H69Z',
    pause:'M71 69V85M81 69V85',
    spark:'M83 17V27M78 22H88M18 72V78M15 75H21',
    notice:'M79 65V72M86 69L83 74M69 69L72 74',
  };
  const terminals=new Set(['question','alert','check','partial','cross','stop','pause','clock','retry']);
  const colors={question:'amber',alert:'amber',partial:'amber',cross:'red',check:'green',retry:'blue',upload:'blue',link:'blue',scan:'blue',deliver:'blue'};
  function svgEl(tag,attrs={}){const n=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);return n;}
  const base={x:0,y:0,r:0,sx:1,sy:1,gx:0,gy:0,lh:18,rh:18,lw:7.6,rw:7.6,la:0,ra:0,ls:0,rs:0};
  const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
  const smooth=x=>{x=clamp(x);return x*x*(3-2*x)};
  const pulse=(t,a,b)=>t<=a||t>=b?0:Math.sin(Math.PI*(t-a)/(b-a));
  function eyePath(cx,cy,w,h,slope,arch){
    const l=cx-w/2,r=cx+w/2,top=cy-h/2,bot=cy+h/2,k=Math.min(w*.46,h*.5);
    return `M${l} ${cy-slope}C${l} ${top-slope} ${cx-k} ${top-arch} ${cx} ${top-arch}C${cx+k} ${top-arch} ${r} ${top+slope} ${r} ${cy+slope}C${r} ${bot+slope} ${cx+k} ${bot-arch} ${cx} ${bot-arch}C${cx-k} ${bot-arch} ${l} ${bot-slope} ${l} ${cy-slope}Z`;
  }
  function poseFor(id,t,staticPose=false){
    const p={...base},s=lookup.get(id),cycle=s.period?((t%s.period)/s.period):0;
    const wave=Math.sin(cycle*Math.PI*2),hold=Math.tanh(wave*2.7);
    switch(id){
      case'idle':p.gx=staticPose?0:1.2*pulse(t%11,7,8.5);break;
      case'listening':Object.assign(p,{lh:20,rh:20,r:3,gx:2,gy:1});break;
      case'connecting':Object.assign(p,{lh:16,rh:16,gy:-1,y:-.4*(staticPose?1:pulse(cycle,0,.5))});break;
      case'uploading':p.gy=staticPose?-3:-3*pulse(cycle,.05,.7);p.r=-1;break;
      case'parsing':case'reading':{const q=staticPose?.68:cycle;p.gx=q<.65?-3+6*smooth(q/.65):3-6*smooth((q-.65)/.35);p.gy=1+(q>.65?1:0);p.lh=15;p.rh=15;p.r=id==='parsing'?-.7:0;break;}
      case'thinking':Object.assign(p,{gx:-2.5,gy:-2.8,r:-3,lh:11,rh:17,ls:1.1,rs:1});if(!staticPose){const f=pulse(cycle,.60,.96);p.gx+=f*2.5;p.gy+=f*2;p.r+=f*2;}break;
      case'planning':p.gx=staticPose?2.6:cycle<.3?-3:cycle<.63?0:3;p.gy=-1;p.lh=15;p.rh=18;p.r=1;break;
      case'searching':p.gx=staticPose?4:4*hold;p.r=staticPose?3:3*hold;p.lh=19;p.rh=19;p.gy=-.4;break;
      case'working':p.lh=12;p.rh=12;p.ls=1;p.rs=-1;p.gy=2;p.r=staticPose?-2:-1.5*pulse(cycle,.2,.6);p.y=staticPose?.5:.6*pulse(cycle,.2,.6);break;
      case'writing':p.lh=14;p.rh=14;p.gy=2;p.gx=staticPose?2:cycle<.7?-2+4*((cycle*3)%1):0;p.r=2;p.y=staticPose?.5:.5*pulse(cycle,.1,.7);break;
      case'verifying':p.lh=staticPose?10:12-3*pulse(cycle,.1,.5);p.rh=p.lh;p.lw=9;p.rw=9;p.gx=staticPose?1.2:1.8*hold;p.gy=1.8;break;
      case'coordinating':p.gx=staticPose?-3:3*hold;p.r=staticPose?-1:hold;p.lh=16;p.rh=16;break;
      case'waiting':p.lh=11;p.rh=11;p.gx=staticPose?1.2:1.5*pulse(cycle,.65,.95);p.r=1;break;
      case'awaiting-input':Object.assign(p,{lh:22,rh:22,lw:8,rw:8,gy:-1,r:2,sy:1.015,sx:.985});break;
      case'blocked':Object.assign(p,{lh:12,rh:18,ls:-1,rs:.5,r:-2});break;
      case'reconnecting':p.lh=13;p.rh=13;p.gx=staticPose?1.7:2*hold;p.gy=1;break;
      case'delivering':p.gy=-1.2;p.lh=19;p.rh=19;p.y=staticPose?-1:-pulse(cycle,.1,.7);break;
      case'completed':Object.assign(p,{lh:4,rh:4,lw:12,rw:12,la:5,ra:5});break;
      case'partial':Object.assign(p,{lh:4,rh:16,lw:11,la:4,r:-1});break;
      case'failed':Object.assign(p,{lh:11,rh:11,ls:-1.5,rs:1.5,gy:2,y:1});break;
      case'cancelled':p.lh=10;p.rh=10;p.lw=9;p.rw=9;break;
      case'paused':p.lh=7;p.rh=7;p.lw=10;p.rw=10;break;
      case'sleeping':Object.assign(p,{lh:2.2,rh:2.2,lw:12,rw:12,r:4,gy:2});break;
    }
    if(s.group!=='state'){
      const q=staticPose?.45:clamp(t/s.duration),a=Math.sin(q*Math.PI),done=q>=1;
      if(id==='appear'){p.sx=.90+.10*smooth(q/.65);p.sy=p.sx;p.lh=18*smooth(q/.7)+.2;p.rh=p.lh;p.y=(1-smooth(q))*3;}
      if(id==='acknowledge'){p.gy=2*a;p.y=2.3*a;p.r=-1.2*a;p.lh=18-5*a;p.rh=p.lh;}
      if(id==='dispatch'||id==='receive-result'){const dir=id==='dispatch'?1:-1;p.gx=3.8*a*dir;p.r=2*a*dir;p.gy=a;}
      if(id==='milestone'||id==='content'){p.lh=18-14*a;p.rh=p.lh;p.lw=7.6+3*a;p.rw=p.lw;p.la=4*a;p.ra=p.la;p.y=-a;}
      if(id==='notify'){p.lh=18+5*a;p.rh=p.lh;p.y=-2.5*a;p.r=2*a;}
      if(id==='recover'){p.lh=18-5*(1-q);p.rh=p.lh;p.gx=2*a;p.y=-a;}
      if(id==='celebrate'){let squash=0,hop=0;if(q<.14)squash=.06*smooth(q/.14);else if(q<.4){squash=-.04;hop=5*Math.sin((q-.14)/.26*Math.PI/2);}else if(q<.76){hop=5*Math.cos((q-.4)/.36*Math.PI/2);squash=.025*Math.sin((q-.4)/.36*Math.PI);}p.sx=1+squash;p.sy=1-squash;p.y=-hop;p.r=-4*a;p.lh=18-14*smooth(q/.6);p.rh=p.lh;p.lw=7.6+4.4*smooth(q/.6);p.rw=p.lw;p.la=5*smooth(q/.6);p.ra=p.la;}
      if(id==='blink'){const f=staticPose?1:q<.275?smooth(q/.275):q<.45?1:1-smooth((q-.45)/.55);p.lh=18-15.8*f;p.rh=p.lh;p.lw=7.6+2*f;p.rw=p.lw;}
      if(id==='glance'){p.gx=4*a;p.gy=-a;p.r=a;}
      if(id==='curious'){p.r=-3*a;p.lh=18-7*a;p.rh=18+4*a;p.gx=-1.5*a;}
      if(done&&id!=='celebrate')Object.assign(p,base);
    }
    return p;
  }
  class Bot {
    constructor(host,size,id,opts={}){
      this.size=size;this.state=lookup.get(id);this.time=0;this.frozen=!!opts.frozen;this.motionScale=size<28?0:size<48?.55:1;this.pose={...base};this.vel=Object.fromEntries(Object.keys(base).map(k=>[k,0]));this.fxOpacity={};this.pointer={x:0,y:0};
      this.svg=svgEl('svg',{viewBox:'0 0 100 100',class:'bot-svg','aria-hidden':'true'});
      if(opts.ink)this.svg.style.setProperty('--ink',opts.ink);
      this.group=svgEl('g');this.body=svgEl('rect',{x:14,y:14,width:72,height:72,rx:16.13,class:'bot-body'});this.face=svgEl('g');this.eyes=[svgEl('path',{class:'bot-eye'}),svgEl('path',{class:'bot-eye'})];this.face.append(...this.eyes);this.group.append(this.body,this.face);this.svg.append(this.group);this.glyphEls={};
      for(const[k,d]of Object.entries(glyphs)){
        const g=svgEl('g',{class:'bot-glyph'+(terminals.has(k)?' bot-terminal':''),opacity:0,'data-color':colors[k]||'ink'});
        if(k!=='spark')g.append(svgEl('circle',{cx:76,cy:77,r:14,class:'bot-mark-back'}));
        const path=svgEl('path',{d});g.append(path);this.svg.append(g);this.glyphEls[k]={g,path};this.fxOpacity[k]=0;
      }
      host.append(this.svg);this.draw(0,true);
    }
    set(id){this.state=lookup.get(id);this.time=0;}
    draw(dt,staticPose=false){
      if(!staticPose)this.time+=dt;
      const quiet=staticPose||this.frozen||reduce||this.motionScale===0;
      const s=this.state;let t=quiet?(s.group==='state'?0:s.duration*.45):this.time;
      let p=poseFor(s.id,t,quiet);
      if(!quiet&&s.group==='state'&&!['sleeping','paused','completed','failed','cancelled','partial','blocked','awaiting-input'].includes(s.id)){
        const b=this.time%8.3;
        if(b>6.9&&b<7.1){const f=Math.sin((b-6.9)/.2*Math.PI);p.lh=Math.max(2.2,p.lh*(1-.87*f));p.rh=Math.max(2.2,p.rh*(1-.87*f));}
      }
      if(!quiet&&s.id==='idle'){p.gx+=this.pointer.x;p.gy+=this.pointer.y;}
      if(this.motionScale<1){p.x*=this.motionScale;p.y*=this.motionScale;p.r*=this.motionScale;p.sx=1+(p.sx-1)*this.motionScale;p.sy=1+(p.sy-1)*this.motionScale;}
      if(this.size<28){p.lw=Math.max(p.lw,150/this.size);p.rw=Math.max(p.rw,150/this.size);}
      else if(this.size<48){p.lw=Math.max(p.lw,200/this.size);p.rw=Math.max(p.rw,200/this.size);}
      for(const k of Object.keys(base)){
        if(quiet||dt===0){this.pose[k]=p[k];this.vel[k]=0;}
        else{const eyelid=(k==='lh'||k==='rh')&&(s.id==='blink'||this.time%8.3>6.9&&this.time%8.3<7.3);const freq=eyelid?60:['gx','gy','lh','rh','la','ra','lw','rw','ls','rs'].includes(k)?28:20;const damping=k==='sx'||k==='sy'?.82:.98;let left=dt;while(left>0){const h=Math.min(left,1/120);this.vel[k]+=(freq*freq*(p[k]-this.pose[k])-2*damping*freq*this.vel[k])*h;this.pose[k]+=this.vel[k]*h;left-=h;}}
      }
      const v=this.pose,boost=this.size<28?1.14:1;
      this.group.setAttribute('transform',`translate(${v.x} ${v.y}) translate(50 50) rotate(${v.r}) scale(${v.sx*boost} ${v.sy*boost}) translate(-50 -50)`);
      this.face.setAttribute('transform',`translate(${v.gx} ${v.gy})`);
      this.eyes[0].setAttribute('d',eyePath(40,46,v.lw,Math.max(2,v.lh),v.ls,v.la));this.eyes[1].setAttribute('d',eyePath(60,46,v.rw,Math.max(2,v.rh),v.rs,v.ra));
      for(const[k,el]of Object.entries(this.glyphEls)){
        const small=this.size<48,show=(!small||terminals.has(k)||this.size>=32&&['upload','link','scan','deliver'].includes(k));
        let target=s.glyph===k&&show?1:0;
        if(s.group!=='state'&&!quiet){if(s.id==='celebrate'&&k==='spark')target=this.size>=64&&this.time>.14&&this.time<s.duration?Math.sin(Math.PI*clamp((this.time-.14)/.58)):0;else target*=1-smooth((this.time/s.duration-.72)/.28);}
        if(k==='spark'&&this.size<64)target=0;
        if(quiet||dt===0)this.fxOpacity[k]=target;else this.fxOpacity[k]+=(target-this.fxOpacity[k])*(1-Math.exp(-dt*18));
        el.g.setAttribute('opacity',this.fxOpacity[k].toFixed(3));
        let x=0,y=0,r=0;
        if(!quiet&&target>0){const c=s.period?this.time%s.period/s.period:clamp(this.time/(s.duration||1));
          if(k==='upload')y=-2*pulse(c,.1,.8);
          if(k==='pen'){x=1.3*Math.sin(c*Math.PI*6);y=.6*Math.cos(c*Math.PI*6);r=-3*pulse(c,.15,.7);}
          if(k==='search'){x=1.5*Math.tanh(Math.sin(c*2*Math.PI)*2);y=.7*Math.sin(c*2*Math.PI);}
          if(k==='scan')y=1.2*Math.sin(c*2*Math.PI);
          if(k==='nodes'){x=1.2*Math.sin(c*2*Math.PI);y=-.6*Math.sin(c*4*Math.PI);}
          if(k==='retry'||k==='link'){x=1.2*Math.sin(c*2*Math.PI);}
          if(k==='deliver')y=2*pulse(c,.1,.65);
          if(k==='spark'){r=5*Math.sin(c*Math.PI);}
        }
        const badgeScale=this.size<28?1.18:1;
        el.g.setAttribute('transform',`translate(${x} ${y}) rotate(${r} 76 77) translate(76 77) scale(${badgeScale}) translate(-76 -77)`);
      }
    }
  }
  let reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches,paused=false,selected='thinking',filter='state';
  let last=0,raf=0,scene=null,sceneIndex=-1,sceneElapsed=0,waitingApproval=false;
  const mainBot=new Bot($('hero'),176,selected);
  const sizeBots=[20,24,32,48,64].map(size=>{const item=document.createElement('div');item.className='size-item';const host=document.createElement('div');host.style.width=size+'px';host.style.height=size+'px';const label=document.createElement('span');label.textContent=size+'px';item.append(host,label);$('sizes').append(item);return new Bot(host,size,selected);});
  const activeBots=[mainBot,...sizeBots];
  const families=[['主智能体','协调全局',null,'idle'],['文档解析','理解原文','var(--role-a)','reading'],['商务应答','整理要求','var(--role-b)','writing'],['技术应答','编排内容','var(--role-c)','thinking'],['评分核验','检查证据','var(--role-d)','verifying']];
  families.forEach(([name,sub,ink,id])=>{const el=document.createElement('article');el.className='identity';const host=document.createElement('div');const h=document.createElement('p');h.textContent=name;const small=document.createElement('small');small.textContent=sub;el.append(host,h,small);$('identities').append(el);new Bot(host,70,id,{frozen:true,ink});});
  function renderCatalog(){
    $('catalog-grid').replaceChildren();
    const list=entries.filter(s=>s.group===filter);
    list.forEach(s=>{const btn=document.createElement('button');btn.type='button';btn.className='state-tile';btn.dataset.state=s.id;btn.setAttribute('aria-pressed',String(s.id===selected));btn.setAttribute('aria-label',`预览${s.name}`);new Bot(btn,58,s.id,{frozen:true});const label=document.createElement('span');label.className='tile-name';label.textContent=s.name;const meta=document.createElement('span');meta.className='tile-meta';meta.textContent=s.group==='state'?(s.period?'持续 · 有停顿':'持续 · 可落定'):'单次 · '+Math.round(s.duration*1000)+'ms';btn.append(label,meta);btn.addEventListener('click',()=>{stopScene();select(s.id);document.querySelector('.playground').scrollIntoView({block:'start',behavior:'instant'});});$('catalog-grid').append(btn);});
    document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.filter===filter)));
  }
  function select(id,announce=true){
    selected=id;const s=lookup.get(id);activeBots.forEach(b=>b.set(id));
    $('detail-name').textContent=s.name;$('detail-desc').textContent=s.desc;$('detail-eyes').textContent=s.eyes;$('detail-rhythm').textContent=s.rhythm;$('detail-trigger').textContent=s.trigger;$('hero-state').textContent=s.name;$('state-code').textContent=s.id;$('family-label').textContent={state:'持续状态',cue:'事件动作',micro:'微表情'}[s.group];
    const list=entries.filter(x=>x.group===s.group);$('state-index').textContent=String(list.indexOf(s)+1).padStart(2,'0')+' / '+list.length;
    document.querySelectorAll('[data-state]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.state===id)));
    if(announce)$('announcement').textContent='正在预览：'+s.name+(s.group==='state'?'':' · 播完后落定，可重播');
    if(reduce||paused)activeBots.forEach(b=>b.draw(0,true));
    wake();
  }
  const scenarios={
    normal:[['acknowledge',.65],['uploading',2.4],['parsing',3.2],['thinking',2.8],['coordinating',3.2],['writing',2.8],['verifying',2.8],['delivering',2.5],['celebrate',1.2],['completed',0]],
    approval:[['writing',2.7],['awaiting-input',-1],['acknowledge',.6],['writing',2.6],['verifying',2.6],['delivering',2.2],['completed',0]],
    recovery:[['searching',2.7],['blocked',2.1],['reconnecting',3.5],['recover',.8],['reading',2.7],['completed',0]],
    partial:[['parsing',3.2],['reading',2.7],['writing',2.7],['verifying',2.8],['delivering',2.2],['partial',0]],
    rapid:[['reading',.24],['writing',.24],['reading',.24],['thinking',.24],['searching',.24],['writing',.24],['awaiting-input',0]],
  };
  function track(){[...$('sequence-track').children].forEach((li,i)=>li.className=i===sceneIndex?'active':i<sceneIndex?'past':'');}
  function enterStep(){
    sceneElapsed=0;const [id,duration]=scene[sceneIndex];select(id);track();
    waitingApproval=duration===-1;$('continue').hidden=!waitingApproval;
    $('sequence-label').textContent=waitingApproval?'演示已停住：等你操作后才继续。':id==='completed'?'演示结束 · 完成姿态保留。':id==='partial'?'演示结束 · 部分完成，保留注意信息。':'演示中 · '+lookup.get(id).name;
    if(id==='parsing')$('sequence-label').textContent='演示中 · 原文解析 20 / 60 页';
    if(duration===0){scene=null;$('stop').hidden=true;}
  }
  function startScene(name){
    stopScene();paused=false;syncPause();scene=scenarios[name];sceneIndex=0;sceneElapsed=0;
    $('sequence-track').replaceChildren();scene.forEach(([id])=>{const li=document.createElement('li');li.textContent=lookup.get(id).name;$('sequence-track').append(li);});
    document.querySelectorAll('[data-scenario]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.scenario===name)));
    $('stop').hidden=false;enterStep();wake();
  }
  function stopScene(){scene=null;waitingApproval=false;$('continue').hidden=true;$('stop').hidden=true;document.querySelectorAll('[data-scenario]').forEach(b=>b.setAttribute('aria-pressed','false'));$('sequence-label').textContent='手动预览 · 可选择任意动作。';}
  function syncPause(){$('pause').textContent=paused?'继续预览':'暂停预览';$('pause').setAttribute('aria-pressed',String(paused));$('motion-indicator').textContent=reduce?'减少动效':paused?'当前帧已暂停':'标准动效';}
  function tick(now){
    raf=0;if(document.hidden||paused)return;const dt=last?Math.min((now-last)/1000,.04):0;last=now;
    if(scene&&!waitingApproval){sceneElapsed+=dt;const duration=scene[sceneIndex][1];if(duration>0&&sceneElapsed>=duration){sceneIndex++;enterStep();}}
    if(!reduce)activeBots.forEach(b=>b.draw(dt));
    const s=lookup.get(selected),needsMotion=!reduce&&(s.period>0||s.id==='idle'||s.group!=='state'&&mainBot.time<s.duration+.6||mainBot.time<.8);
    if(needsMotion||scene&&!waitingApproval)raf=requestAnimationFrame(tick);
  }
  function wake(){if(!raf&&!document.hidden&&!paused){last=0;raf=requestAnimationFrame(tick);}}
  document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{filter=b.dataset.filter;renderCatalog();}));
  document.querySelectorAll('[data-scenario]').forEach(b=>b.addEventListener('click',()=>startScene(b.dataset.scenario)));
  $('rapid').addEventListener('click',()=>startScene('rapid'));
  $('urgent').addEventListener('click',()=>{stopScene();paused=false;syncPause();select('awaiting-input');$('sequence-label').textContent='高优先级打断：立即停止当前动作，等待确认。';});
  $('continue').addEventListener('click',()=>{if(!scene||!waitingApproval)return;waitingApproval=false;sceneIndex++;enterStep();wake();});
  $('stop').addEventListener('click',()=>{stopScene();$('sequence-track').replaceChildren();select('idle');});
  $('pause').addEventListener('click',()=>{paused=!paused;syncPause();if(paused){cancelAnimationFrame(raf);raf=0;}else wake();});
  $('replay').addEventListener('click',()=>{stopScene();paused=false;syncPause();select(selected);});
  function setReduce(v){reduce=v;$('reduce').checked=v;syncPause();activeBots.forEach(b=>b.draw(0,true));if(raf){cancelAnimationFrame(raf);raf=0;}wake();}
  $('reduce').checked=reduce;$('reduce').addEventListener('change',e=>setReduce(e.target.checked));window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',e=>setReduce(e.matches));
  $('theme').addEventListener('click',()=>{const dark=document.documentElement.dataset.theme!=='dark';document.documentElement.dataset.theme=dark?'dark':'light';$('theme').textContent=dark?'切换浅色':'切换深色';});
  if(window.matchMedia('(prefers-color-scheme: dark)').matches){document.documentElement.dataset.theme='dark';$('theme').textContent='切换浅色';}
  $('stage').addEventListener('pointermove',e=>{if(e.pointerType!=='mouse'||selected!=='idle'||reduce)return;const r=$('stage').getBoundingClientRect();mainBot.pointer.x=clamp((e.clientX-r.left)/r.width-.5,-.5,.5)*6;mainBot.pointer.y=clamp((e.clientY-r.top)/r.height-.5,-.5,.5)*4;wake();});
  $('stage').addEventListener('pointerleave',()=>{mainBot.pointer={x:0,y:0};wake();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(raf);raf=0;}else wake();});
  window.addEventListener('pagehide',()=>{cancelAnimationFrame(raf);raf=0;});
  /* 只读快照供样片验收，所有状态切换仍从实际界面操作。 */
  window.hagentDesign={entries:entries.map(({id,group})=>({id,group})),snapshot:()=>({selected,reduce,paused,scene:!!scene,waitingApproval,time:mainBot.time,raf:!!raf,pose:{...mainBot.pose}})};
  renderCatalog();select(selected,false);syncPause();wake();
})();
