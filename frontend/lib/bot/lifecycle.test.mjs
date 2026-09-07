import { test } from "node:test";
import assert from "node:assert/strict";
import { ProseBotEngine } from "./character.ts";
import { getBotRuntimeStats } from "./scheduler.ts";

class SvgNode {
  children=[];dataset={};attributes=new Map();parent=null;
  style={removeProperty(name){delete this[name];}};
  setAttribute(k,v){this.attributes.set(k,String(v));}
  append(...children){for(const c of children){c.parent=this;this.children.push(c);}}
  remove(){if(this.parent)this.parent.children=this.parent.children.filter(c=>c!==this);}
  querySelector(){return this.children.find(c=>c.attributes.has("data-bot-rest"))??null;}
}
function environment(t) {
  let now=100,id=0;const frames=new Map(),timers=new Map(),listeners=new Map(),observers=[];
  const previous={document:globalThis.document,window:globalThis.window,IntersectionObserver:globalThis.IntersectionObserver,requestAnimationFrame:globalThis.requestAnimationFrame,cancelAnimationFrame:globalThis.cancelAnimationFrame};
  globalThis.document={hidden:false,createElementNS:()=>new SvgNode(),addEventListener:(k,f)=>listeners.set(k,f),removeEventListener:k=>listeners.delete(k)};
  globalThis.window={matchMedia:()=>({matches:false,addEventListener:(k,f)=>listeners.set(`media:${k}`,f),removeEventListener:k=>listeners.delete(`media:${k}`)})};
  globalThis.IntersectionObserver=class {constructor(fn){this.fn=fn;observers.push(this);}observe(){}disconnect(){this.disconnected=true;}};
  globalThis.requestAnimationFrame=fn=>{frames.set(++id,fn);return id;};
  globalThis.cancelAnimationFrame=id=>frames.delete(id);
  t.mock.method(performance,"now",()=>now);
  t.mock.method(globalThis,"setTimeout",fn=>{timers.set(++id,fn);return id;});
  t.mock.method(globalThis,"clearTimeout",id=>timers.delete(id));
  const engines=[];
  t.after(()=>{for(const e of engines)e.destroy();Object.assign(globalThis,previous);});
  return {
    create(options={}){const svg=new SvgNode(),rest=new SvgNode();rest.setAttribute("data-bot-rest","");svg.append(rest);const engine=new ProseBotEngine(svg,options);engines.push(engine);observers.at(-1).fn([{isIntersecting:true}]);return {engine,svg,rest};},
    step(ms){for(let left=ms;left>0;){const n=Math.min(left,16);now+=n;left-=n;const pending=[...frames.values()];frames.clear();pending.forEach(f=>f(now));}},
    hide(hidden){document.hidden=hidden;listeners.get("visibilitychange")?.();},
    reduce(value){listeners.get("media:change")?.({matches:value});},
    frames,timers,observers,listeners,
  };
}
test("插播可被错误立即打断，结束后不回跳旧状态",t=>{
  const h=environment(t),{engine}=h.create({state:"idle"});
  engine.playOnce("curious","event-a");h.step(160);
  engine.setState("working");engine.setState("failed");h.step(1800);
  assert.equal(engine.snapshot().expression,"failed");assert.equal(engine.snapshot().state,"failed");assert.equal(h.timers.size,0);
});
test("只有亲历的同轮工作完成才庆祝，历史完成挂载不重播",t=>{
  const h=environment(t),{engine}=h.create({state:"working",completionKey:"turn-1"});h.step(120);
  engine.setState("completed");assert.equal(engine.snapshot().expression,"celebrate");h.step(2300);
  assert.equal(engine.snapshot().expression,"completed");
  const history=h.create({state:"completed",completionKey:"turn-1"}).engine;
  assert.equal(history.snapshot().expression,"completed");
});
test("相同事件 key 不重新起播，插播落定后返回基础态",t=>{
  const h=environment(t),{engine}=h.create({state:"idle"});
  engine.playOnce("curious",1);h.step(600);engine.playOnce("curious",1);h.step(500);
  assert.equal(engine.snapshot().expression,"idle");
});
test("暂停冻结当前姿态，继续时不回到第一帧",t=>{
  const h=environment(t),{engine}=h.create({state:"thinking"});h.step(500);
  engine.configure({paused:true});const pose=engine.snapshot().pose;h.step(1000);
  assert.deepEqual(engine.snapshot().pose,pose);
  engine.configure({paused:false});h.step(16);assert.deepEqual(engine.snapshot().pose,pose);
  h.step(150);assert.notDeepEqual(engine.snapshot().pose,pose);
});
test("减少动效与隐藏页签停止帧循环，隐藏期间完成不补播",t=>{
  const h=environment(t),{engine}=h.create({state:"working",completionKey:"turn"});h.step(100);
  h.reduce(true);assert.equal(getBotRuntimeStats().active,0);assert.equal(h.frames.size,0);
  h.reduce(false);h.step(100);h.hide(true);
  engine.setState("completed");h.step(1000);h.hide(false);
  assert.equal(engine.snapshot().expression,"completed");
});
test("销毁清理计时器、观察器、帧与 SVG，只剩 React 静态占位",t=>{
  const h=environment(t),{engine,svg,rest}=h.create({state:"idle",idleMoods:true});h.step(1000);
  assert.ok(h.timers.size>0);engine.destroy();
  assert.equal(h.timers.size,0);assert.equal(h.frames.size,0);assert.equal(h.observers[0].disconnected,true);
  assert.equal(h.listeners.size,0);assert.deepEqual(svg.children,[rest]);assert.equal(rest.style.display,undefined);
  assert.deepEqual(getBotRuntimeStats(),{instances:0,active:0,frameScheduled:false});
});

test("默认 1.5 倍速让一秒事件在约三分之二秒完成",t=>{
  const h=environment(t),{engine}=h.create({state:"idle"});
  engine.playOnce("curious","speed-check");
  h.step(640);assert.equal(engine.snapshot().expression,"curious");
  h.step(48);assert.equal(engine.snapshot().expression,"idle");
});
