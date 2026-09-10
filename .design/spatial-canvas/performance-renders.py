"""独立开发实例的 React 渲染验证；帧率验收使用 performance-browser.py 的生产构建。"""

exec(open('.design/spatial-canvas/performance-browser.py').read().rsplit('\nnew_tab(', 1)[0])
new_tab(f"{URL}/workspace?project=perf-a")
cdp("Emulation.setDeviceMetricsOverride", width=1440, height=1000, deviceScaleFactor=1, mobile=False)
cdp("Page.bringToFront")
wait_for_load()
wait_js("document.querySelector('[data-placement=\"scoring\"]')?.getAttribute('aria-label')?.includes('80')", 30)
button("展开评分要点")
send("准备基准")
wait_js("document.querySelector('.cv-msgwin')?.dataset.busy==='0' && document.querySelector('.stream-inner')?.textContent.includes('编制成果')", 30)
install_sampler()
js("new Promise(r=>setTimeout(r,1000))")
js('''(() => {
  const hook=window.__REACT_DEVTOOLS_GLOBAL_HOOK__, previous=hook.onCommitFiberRoot;
  const targets=new Set(['SpatialWorkspace','WorkspaceChrome','MessageWindow','AgentStream','AgentBoard','CanvasDock','Composer']);
  window.renderCounts={}; window.renderTimes=new Map(); window.renderStart=performance.now();
  hook.onCommitFiberRoot=function(id,root,...rest){
    function visit(f){if(!f)return;const name=f.type?.name;
      if(targets.has(name)&&(f.flags&1)&&f.actualStartTime>window.renderStart&&f.actualStartTime>(renderTimes.get(name)??0)){
        renderCounts[name]=(renderCounts[name]??0)+1;renderTimes.set(name,f.actualStartTime);
      }
      visit(f.child);visit(f.sibling);
    }
    visit(root.current);return previous?.call(this,id,root,...rest);
  };
  window.resetRenderCounts=()=>{window.renderCounts={};window.renderTimes=new Map();window.renderStart=performance.now()};
})()''')
sample("pan", 3000)
button("放大画布")
js("new Promise(r=>setTimeout(r,500))")
button("缩小画布")
js("new Promise(r=>setTimeout(r,500))")
sample_drag(1000)
js("new Promise(r=>setTimeout(r,500))")
static = js("renderCounts")
assert static.get("SpatialWorkspace", 0) > 5
targets = ["WorkspaceChrome", "MessageWindow", "AgentStream", "AgentBoard", "CanvasDock", "Composer"]
if LABEL == "after":
    assert all(static.get(name, 0) == 0 for name in targets), static
else:
    assert all(static.get(name, 0) > 0 for name in targets if name != "WorkspaceChrome"), static
print(LABEL, "画布交互渲染", static, flush=True)
js("resetRenderCounts()")
send("检查状态更新")
wait_js("document.querySelector('.cv-msgwin')?.dataset.busy==='0' && document.querySelector('.stream-inner')?.textContent.includes('检查状态更新')")
updates = js("renderCounts")
assert all(updates.get(name, 0) > 0 for name in targets if name != "WorkspaceChrome"), updates
print(LABEL, "业务订阅渲染", updates, flush=True)
(OUT / f"{LABEL}-renders.json").write_text(json.dumps({"canvasInteraction":static,"businessUpdate":updates},ensure_ascii=False,indent=2))
