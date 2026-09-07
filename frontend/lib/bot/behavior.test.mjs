import { test } from "node:test";
import assert from "node:assert/strict";
import { ALL_STATES, isBotState } from "./states.ts";
import { poseFor, REST_POSE } from "./pose.ts";
import { turnFrame } from "./geometry.ts";
import { botIdentityTone } from "./identity.ts";
import { emptyBotSignals, reduceBotSignals, scopeActivity, activityBotState } from "../hagent/botSignals.ts";
import { deriveMainBotState, deriveSubagentBotState } from "./derive.ts";

const apply=(signals,event,data={})=>reduceBotSignals(signals,{event,data});
const start=(id,name,parent)=>({call_id:id,tool_name:name,parent_tool_use_id:parent,args_chunk:""});

test("侧向不压成纸片，侧面与背面不露双眼",()=>{
  const front=turnFrame({...REST_POSE,yaw:0});
  assert.equal(front.sideOpacity,0);assert.equal(front.faceOpacity,1);
  for(const yaw of [90,180,270,-90]){
    const frame=turnFrame({...REST_POSE,yaw});assert.ok(frame.width>=.9);assert.equal(frame.faceOpacity,0);
  }
  assert.equal(turnFrame({...REST_POSE,yaw:360}).faceOpacity,1);
});
test("所有动作跨多个周期保持有效几何，状态入口拒绝原型键",()=>{
  assert.equal(ALL_STATES.length,36);assert.equal(isBotState("toString"),false);assert.equal(isBotState("__proto__"),false);
  for(const state of ALL_STATES)for(let t=0;t<12;t+=.11){
    const pose=poseFor(state,t);assert.ok(Object.values(pose).every(Number.isFinite),state);
    assert.ok(!/NaN|Infinity|undefined/.test(JSON.stringify(turnFrame(pose))),state);
  }
});
test("身份色稳定且落在主题色板内",()=>{
  for(const id of ["worker-a","worker-b","嵌套任务","__proto__"]){assert.equal(botIdentityTone(id),botIdentityTone(id));assert.ok(botIdentityTone(id)>=0&&botIdentityTone(id)<8);}
});
test("同一工具参数分片不重复派发，正文分片不重建活动投影",()=>{
  const a=apply(emptyBotSignals(),"tool_call.started",start("read","Read"));
  const b=apply(a,"tool_call.started",{...start("read",""),args_chunk:'"path":'});
  assert.equal(a,b);
  const c=apply(b,"message.delta",{content_chunk:"一个"});
  assert.equal(apply(c,"message.delta",{content_chunk:"分片"}),c);
  assert.equal(activityBotState(scopeActivity(c)),"reading");
});
test("后来的调用完成不能掩盖较早的活跃调用；并行子代理不串台",()=>{
  let signals=apply(emptyBotSignals(),"tool_call.started",start("old","Read"));
  signals=apply(signals,"tool_call.started",start("new","Edit"));
  signals=apply(signals,"tool_call.completed",start("new","Edit"));
  assert.equal(deriveMainBotState("running",[],signals),"reading");
  signals=apply(signals,"tool_call.started",start("child-call","prose_validate_matrix","worker"));
  assert.equal(activityBotState(scopeActivity(signals,"worker")),"verifying");
  assert.equal(deriveMainBotState("running",[],signals),"reading");
});
test("子代理派发和思考/文本有各自的归属",()=>{
  let s=apply(emptyBotSignals(),"tool_call.started",start("worker","Agent"));
  assert.equal(deriveMainBotState("running",[],s),"coordinating");
  s=apply(s,"message.delta",{parent_tool_use_id:"worker",content_chunk:[{type:"thinking",thinking:"分析"}]});
  assert.equal(activityBotState(scopeActivity(s,"worker")),"thinking");
  assert.equal(deriveMainBotState("running",[],s),"coordinating");
  s=apply(s,"message.delta",{content_chunk:[{type:"text",text:"正在汇总"}]});
  assert.equal(deriveMainBotState("running",[],s),"generating");
});
test("人工介入与 hook 阻断不能被 done 庆祝覆盖",()=>{
  for(const [event,expected] of [["interrupt.requested","awaiting-input"],["hook.blocked","blocked"]]){
    const s=apply(apply(emptyBotSignals(),event),"done");
    assert.equal(deriveMainBotState("done",[],s),expected);
  }
});
test("缺页不会阻止后续工作，但最终保留部分完成；明确错误优先",()=>{
  let s=apply(emptyBotSignals(),"ingest.progress",{done:10,total:20});
  assert.equal(deriveMainBotState("running",[],s),"reading");
  s=apply(s,"ingest.completed",{failed_pages:[2]});
  s=apply(s,"run.started",{run_id:"turn"});
  assert.equal(s.partial,true);assert.equal(s.reading,false);
  assert.equal(deriveMainBotState("done",[],s),"partial");
  s=apply(s,"error",{message:"失败"});
  assert.equal(deriveMainBotState("loading_results",[],s),"failed");
});
test("连接结束不证明未完成子任务已取消，完成的子任务仍保持完成",()=>{
  const run={call:start("worker","Agent"),status:"running",children:[],description:"",prompt:"",subagentType:""};
  assert.equal(deriveSubagentBotState(run,false),"waiting");
  assert.equal(deriveSubagentBotState({...run,status:"done"},false),"completed");
});
test("超长时间线回退仍识别旧的活跃调用并隔离上一轮",()=>{
  const timeline=[{id:"u",role:"user",content:"开始"},{id:"t",role:"tool",call:{call_id:"long",tool_name:"Read",args:"",status:"running"}},...Array.from({length:500},(_,i)=>({id:String(i),role:"tool",call:{call_id:String(i),tool_name:"Edit",args:"",status:"done"}}))];
  assert.equal(deriveMainBotState("running",timeline),"reading");
  assert.equal(deriveMainBotState("running",[...timeline,{id:"new",role:"user",content:"新轮次"}]),"thinking");
});

test("展开、收起和活动条共享确认/部分完成文案与状态点",async()=>{
  const {runStatusText,activityLine,runDotState}=await import("../../app/workspace/_components/runStatus.ts");
  for(const [s,text] of [[{...emptyBotSignals(),attention:"awaiting-input"},"等待回应"],[{...emptyBotSignals(),partial:true},"部分完成"]]){
    assert.equal(runStatusText("done",3,4,s),text);
    assert.equal(activityLine([],"done",s),text);
    assert.equal(runDotState("done",s),"attention");
  }
});
