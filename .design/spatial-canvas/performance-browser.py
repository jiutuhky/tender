"""通过 browser-use 执行；PERF_URL、PERF_LABEL、PERF_OUTPUT 指定验收实例与产物。"""

import base64
import gzip
import json
import os
import time
from pathlib import Path

OUT = Path(os.environ.get("PERF_OUTPUT", "/tmp/prose-canvas-perf-implementation/results"))
OUT.mkdir(parents=True, exist_ok=True)
LABEL = os.environ.get("PERF_LABEL", "after")
URL = os.environ.get("PERF_URL", "http://127.0.0.1:3102")


def wait_js(condition, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if js(condition):
            return
        time.sleep(0.1)
    raise AssertionError(condition)


def button(label):
    nodes = cdp("Accessibility.getFullAXTree")["nodes"]
    node = next(n for n in nodes if n.get("role", {}).get("value") == "button"
                and n.get("name", {}).get("value") == label)
    q = cdp("DOM.getBoxModel", backendNodeId=node["backendDOMNodeId"])["model"]["content"]
    click_at_xy(sum(q[0::2]) / 4, sum(q[1::2]) / 4)


def key(name, modifiers=0):
    code = {"Escape": 27, "Enter": 13, "z": 90, "a": 65}.get(name, 0)
    for event in ("keyDown", "keyUp"):
        cdp("Input.dispatchKeyEvent", type=event, key=name, code=name,
            windowsVirtualKeyCode=code, modifiers=modifiers)


def send(content):
    nodes = cdp("Accessibility.getFullAXTree")["nodes"]
    node = next(n for n in nodes if n.get("role", {}).get("value") == "textbox"
                and n.get("name", {}).get("value") == "补充要求或向智能体发送指令")
    q = cdp("DOM.getBoxModel", backendNodeId=node["backendDOMNodeId"])["model"]["content"]
    click_at_xy(sum(q[0::2]) / 4, sum(q[1::2]) / 4)
    cdp("Input.insertText", text=content)
    key("Enter", 2)


def screenshot(name):
    result = cdp("Page.captureScreenshot", format="png")
    (OUT / f"{LABEL}-{name}.png").write_bytes(base64.b64decode(result["data"]))


def install_sampler():
    js('''window.canvasPerf = async (kind, duration = 5000, point = null) => {
      const vp = document.querySelector('.sp-viewport');
      const intervals = [], longs = [];
      const observer = new PerformanceObserver(list => longs.push(...list.getEntries().map(e => ({start:e.startTime,duration:e.duration}))));
      observer.observe({type:'longtask'});
      let start, previous, offset = 0;
      const move = next => {
        if (kind === 'pan') vp.dispatchEvent(new WheelEvent('wheel', {bubbles:true,cancelable:true,deltaY:next-offset,clientX:760,clientY:450}));
        if (kind === 'drag') vp.dispatchEvent(new PointerEvent('pointermove', {bubbles:true,pointerId:1,pointerType:'mouse',buttons:1,clientX:point.x+next,clientY:point.y}));
        offset = next;
      };
      await new Promise(resolve => {
        function frame(t) {
          start ??= t;
          if (previous !== undefined) intervals.push(t-previous);
          previous = t;
          if (t-start >= duration) {move(0);resolve();return;}
          move(Math.sin((t-start)*Math.PI*2/2500)*140);
          requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);
      });
      observer.disconnect();
      const sorted = intervals.toSorted((a,b)=>a-b);
      return {kind,frames:intervals.length,mean:intervals.reduce((a,b)=>a+b,0)/intervals.length,
        p95:sorted[Math.floor(sorted.length*.95)],max:Math.max(...intervals),
        over25:intervals.filter(t=>t>25).length,over50:intervals.filter(t=>t>50).length,
        intervals,longTasks:longs};
    }; "采样器就绪"''')


def card_point():
    return js('''(() => {for(const e of document.querySelectorAll('.sp-card[data-kind="scoring"]')) {
      const r=e.getBoundingClientRect(), x=r.x+r.width/2, y=r.y+r.height/2;
      if(x>600 && x<1080 && y>250 && y<700 && e.contains(document.elementFromPoint(x,y))) return {x,y,id:e.dataset.placement};
    } throw Error('缺少可操作的评分卡片')})()''')


def sample_drag(duration=5000):
    p = card_point()
    cdp("Input.dispatchMouseEvent", type="mousePressed", x=p["x"], y=p["y"], button="left", buttons=1, clickCount=1)
    result = sample("drag", duration, p)
    cdp("Input.dispatchMouseEvent", type="mouseReleased", x=p["x"], y=p["y"], button="left", buttons=0, clickCount=1)
    return result


def sample(kind, duration=5000, point=None):
    # CDP 通道单次等待上限为 5 秒；采样在页面内完成后再取结果。
    js(f"window.canvasSample=null; canvasPerf({json.dumps(kind)},{duration},{json.dumps(point)}).then(r=>window.canvasSample=r); true")
    time.sleep(duration / 1000 + 0.2)
    wait_js("window.canvasSample !== null")
    return js("window.canvasSample")


def record_trace():
    cdp("Tracing.start", categories="devtools.timeline,blink.user_timing,cc", transferMode="ReturnAsStream")
    js("canvasPerf('pan',1500)")
    cdp("Tracing.end")
    stream = None
    deadline = time.monotonic() + 10
    while not stream and time.monotonic() < deadline:
        for event in drain_events():
            if event.get("method") == "Tracing.tracingComplete":
                stream = event["params"]["stream"]
        time.sleep(0.1)
    assert stream
    with gzip.open(OUT / f"{LABEL}-trace.json.gz", "wb") as output:
        while True:
            chunk = cdp("IO.read", handle=stream)
            output.write(base64.b64decode(chunk["data"]) if chunk.get("base64Encoded") else chunk["data"].encode())
            if chunk.get("eof"):
                break
    cdp("IO.close", handle=stream)


new_tab(f"{URL}/workspace?project=perf-a")
cdp("Emulation.setDeviceMetricsOverride", width=1440, height=1000, deviceScaleFactor=1, mobile=False)
cdp("Page.bringToFront")
wait_for_load()
wait_js("document.querySelector('[data-placement=\"scoring\"]')?.getAttribute('aria-label')?.includes('80')")
button("展开评分要点")
wait_js("document.querySelectorAll('.sp-card[data-kind=scoring]').length >= 8")
send("准备基准")
wait_js("document.querySelector('.cv-msgwin')?.dataset.busy === '0' && document.querySelector('.stream-inner')?.textContent.includes('编制成果')")
install_sampler()
js("canvasPerf('pan',1000)")
sample_drag(1000)
screenshot("desktop-light")

results = {"label": LABEL, "url": URL, "browser": cdp("Browser.getVersion"),
           "viewport": {"width": 1440, "height": 1000, "deviceScaleFactor": 1},
           "fixture": {"matrices": 4, "items": 200, "assets": 100}, "samples": []}
for round_number in range(3):
    for kind in ("pan", "drag"):
        value = sample("pan") if kind == "pan" else sample_drag()
        value["round"] = round_number + 1
        results["samples"].append(value)
        print(LABEL, {k:v for k,v in value.items() if k not in ("intervals", "longTasks")}, flush=True)
        js("new Promise(r=>setTimeout(r,500))")
for attempt in ("first", "warm"):
    p = card_point()
    js(f"document.querySelector('[data-placement=\"{p['id']}\"]').focus({{preventScroll:true}}); window.readerFrames=canvasPerf('reader',1500)")
    key("Enter")
    wait_js("!!document.querySelector('.sp-reader-host')")
    value = js("readerFrames")
    value["attempt"] = attempt
    results["samples"].append(value)
    key("Escape")
    wait_js("!document.querySelector('.sp-reader-host')")
record_trace()
results["mountedCards"] = js("document.querySelectorAll('[data-placement]').length")
results["filters"] = js("[...document.querySelectorAll('.cv-msgwin *')].map(e=>getComputedStyle(e).backdropFilter).filter(v=>v!=='none')")
(OUT / f"{LABEL}.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
print(f"结果已保存：{OUT / (LABEL + '.json')}", flush=True)
