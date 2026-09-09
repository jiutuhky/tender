import test from 'node:test';
import assert from 'node:assert/strict';
import { validateMapping, locatePdfRegions, regionPixels, visiblePageRange } from './pdf-mapping.ts';
const doc={sha256:'a'.repeat(64),origin_sha256:'b'.repeat(64),preview_sha256:'c'.repeat(64)};
const sizes=[{width:600,height:800},{width:800,height:600}];
const mapping=()=>({schema:2,coordinateSpace:'page-display-normalized',mdSha256:doc.sha256,originSha256:doc.origin_sha256,previewSha256:doc.preview_sha256,mdLineCount:30,
  pages:sizes.map((p,index)=>({...p,index})),blocks:[{mdStart:4,mdEnd:8,label:'table',rects:[{page:0,bbox:[.1,.2,.8,.9]},{page:1,bbox:[.1,.1,.8,.3]}]},
  {mdStart:20,mdEnd:22,label:'text',rects:[{page:1,bbox:[.1,.5,.8,.6]}]}]});
test('跨页引用保持两个原页区域，重复文字只按行号定位',()=>{
 const m=mapping();assert.ok(validateMapping(m,doc,sizes).mapping);
 assert.deepEqual(locatePdfRegions(m,[6,6]).map(r=>r.page),[0,1]);
 assert.equal(locatePdfRegions(m,[21,21]).length,1);
 assert.equal(locatePdfRegions(m,[8,20]).length,3);
 for(const span of [undefined,[],[4],[0,4],[8,4],[4,31],[NaN,5],[10,12]]) assert.equal(locatePdfRegions(m,span).length,0);
});
test('版本、页数、比例、行号与矩形不可信时禁用高亮',()=>{
 const changes=[m=>m.schema=1,m=>m.mdSha256='d'.repeat(64),m=>m.originSha256='d'.repeat(64),m=>m.previewSha256='d'.repeat(64),m=>m.pages.pop(),m=>m.pages[0].width=800,m=>m.pages[0].index=1,m=>m.blocks[0].mdEnd=31,m=>m.blocks[0].rects[0].page=2,m=>m.blocks[0].rects[0].bbox=[0,0,Infinity,1],m=>m.blocks[0].rects[0].bbox=[.5,0,.2,1],m=>m.blocks[0].rects[0].bbox=[-.1,0,.2,1]];
 for(const change of changes){const m=mapping();change(m);assert.equal(validateMapping(m,doc,sizes).mapping,null);}
 assert.equal(validateMapping(null,doc,sizes).mapping,null);
});
test('归一化坐标按显示几何换算，旋转已包含于页宽高，像素比不参与',()=>{
 const r={page:0,bbox:[.1,.2,.5,.6]};
 for(const scale of [.25,1,1.5,3])for(const [w,h] of [[600,800],[800,600]]) {
  const got=regionPixels(r,{width:w*scale,height:h*scale});
  for(const [key,value] of Object.entries({x:w*scale*.1,y:h*scale*.2,width:w*scale*.4,height:h*scale*.4}))assert.ok(Math.abs(got[key]-value)<1e-6);
 }
});
test('800 页只分配可见窗口与相邻页面',()=>{
 const pages=Array.from({length:800},()=>({width:600,height:800}));
 const tops=pages.map((_,i)=>24+i*824);
 for(const target of [0,30,400,799]){
  const [first,last]=visiblePageRange(tops,pages,tops[target],600);
  assert.ok(target>=first&&target<=last);assert.ok(last-first<=2);
 }
});

test('同一条目的多处引用合并页码，并去除重复区域', async()=>{
 const {locatePdfReferences}=await import('./pdf-mapping.ts');
 const m=mapping();
 const result=locatePdfReferences(m,[[4,4],[6,8],[21,21]]);
 assert.equal(result.length,3);
 assert.deepEqual(result.map(r=>r.page),[0,1,1]);
 assert.deepEqual(locatePdfReferences(m,[[21,21],[4,4]]),result);
});
