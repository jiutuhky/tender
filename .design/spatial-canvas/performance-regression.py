"""在修复后生产实例运行 performance-browser.py 后，通过同一 browser-use 连接执行。"""

from urllib.request import Request, urlopen

exec(open('.design/spatial-canvas/performance-browser.py').read().rsplit('\nnew_tab(', 1)[0])
checks = {}

new_tab(f"{URL}/workspace?project=perf-a")
cdp("Emulation.setDeviceMetricsOverride", width=1440, height=1000, deviceScaleFactor=1, mobile=False)
cdp("Page.bringToFront")
wait_for_load()
wait_js("document.querySelector('[data-placement=\"scoring\"]')?.getAttribute('aria-label')?.includes('80')")
button("展开评分要点")
send("准备基准")
wait_js("document.querySelector('.cv-msgwin')?.dataset.busy==='0' && document.querySelector('.stream-inner')?.textContent.includes('编制成果')")
install_sampler()


def save_check(name, condition):
    assert condition, name
    checks[name] = True
    print(name, flush=True)


def screenshot_state(name):
    js("new Promise(r=>setTimeout(r,400))")
    screenshot(name)


save_check("单层毛玻璃", js("document.querySelectorAll('.cv-msgwin .lg-diffusion').length === 1 && !document.querySelector('.cv-msgwin .lg-warp') && getComputedStyle(document.querySelector('.lg-diffusion')).backdropFilter==='blur(8px) saturate(1.25)'"))
js("window.savedNodes={msg:document.querySelector('.cv-msgwin'),input:document.querySelector('.composer textarea')}; const s=document.querySelector('.stream-scroll');s.scrollTop=180;s.dispatchEvent(new Event('scroll'));window.savedScroll=s.scrollTop;document.querySelector('.composer textarea').focus()")
cdp("Input.insertText", text="保留草稿：继续核验技术条款")
sample("pan", 1000)
sample_drag(1000)
button("放大画布")
js("new Promise(r=>setTimeout(r,450))")
button("缩小画布")
js("new Promise(r=>setTimeout(r,450))")
save_check("交互保留草稿、滚动位置与浮层节点", js("savedNodes.msg===document.querySelector('.cv-msgwin') && savedNodes.input===document.querySelector('.composer textarea') && savedNodes.input.value==='保留草稿：继续核验技术条款' && Math.abs(document.querySelector('.stream-scroll').scrollTop-savedScroll)<1"))

# Shift 多选与位移差、撤销和重做均通过真实 DOM 手势检查。
click_at_xy(1390, 690)
points = js('''[...document.querySelectorAll('.sp-card[data-kind="scoring"]')].map(e=>{const r=e.getBoundingClientRect();return {id:e.dataset.placement,x:r.x+r.width/2,y:r.y+r.height/2}}).filter(p=>p.x>500&&p.x<1080&&p.y>300&&p.y<700&&document.elementFromPoint(p.x,p.y)?.closest('[data-placement]')?.dataset.placement===p.id).slice(0,2)''')
assert len(points) == 2
for i, p in enumerate(points):
    for event in ("mousePressed", "mouseReleased"):
        cdp("Input.dispatchMouseEvent", type=event, x=p["x"], y=p["y"], button="left",
            buttons=1 if event == "mousePressed" else 0, clickCount=1, modifiers=8 if i else 0)
save_check("Shift 多选", js("document.querySelectorAll('.sp-card.is-selected').length===2"))
js("window.originalTransforms=[...document.querySelectorAll('.sp-card.is-selected')].map(e=>({id:e.dataset.placement,transform:e.style.transform}))")
p = points[0]
cdp("Input.dispatchMouseEvent", type="mousePressed", x=p["x"], y=p["y"], button="left", buttons=1, clickCount=1)
for i in range(1, 9):
    cdp("Input.dispatchMouseEvent", type="mouseMoved", x=p["x"]+i*8, y=p["y"]+i*4, buttons=1)
    time.sleep(0.03)
cdp("Input.dispatchMouseEvent", type="mouseReleased", x=p["x"]+64, y=p["y"]+32, button="left", buttons=0, clickCount=1)
wait_js("!document.querySelector('.is-moving')")
save_check("多卡同步位移", js('''(()=>{const ds=originalTransforms.map(p=>{const e=document.querySelector(`[data-placement="${p.id}"]`),a=new DOMMatrix(p.transform),b=new DOMMatrix(e.style.transform);return {x:b.e-a.e,y:b.f-a.f}});return ds.every(d=>d.x>10&&d.y>10)&&Math.abs(ds[0].x-ds[1].x)<.01&&Math.abs(ds[0].y-ds[1].y)<.01})()'''))
button("撤销")
save_check("撤销恢复位置", js('originalTransforms.every(p=>document.querySelector(`[data-placement="${p.id}"]`).style.transform===p.transform)'))
button("重做")
save_check("重做恢复移动", js('originalTransforms.every(p=>document.querySelector(`[data-placement="${p.id}"]`).style.transform!==p.transform)'))
button("撤销")
key("Escape")
key("Escape")
wait_js("!!document.querySelector('[data-placement=\"materials\"]')")
js("new Promise(r=>setTimeout(r,500))")
button("展开评分要点")
wait_js("document.querySelectorAll('.sp-card[data-kind=scoring]').length>=8")
js("new Promise(r=>setTimeout(r,500))")
p = card_point()
js(f"document.querySelector('[data-placement=\"{p['id']}\"]').focus({{preventScroll:true}})")
key("Enter")
wait_js("!!document.querySelector('.sp-reader-host')")
js("new Promise(r=>setTimeout(r,500))")
save_check("真实条目阅读与原文入口", js("document.querySelector('.sp-reader-host').textContent.includes('编制要求') && document.querySelector('.rd-source-link')!==null"))
js("document.querySelector('.cv-item-confirm').scrollIntoView({block:'center'})")
button("核验确认")
wait_js("document.querySelector('.sp-reader-host').textContent.includes('已核验')")
save_check("矩阵订阅正常更新", True)
key("Escape")
wait_js("!document.querySelector('.sp-reader-host')")
save_check("阅读关闭焦点恢复", js(f"document.activeElement?.dataset.placement === '{p['id']}'"))

for _ in range(3):
    button("收起执行流")
    time.sleep(0.08)
    button("展开执行流")
    time.sleep(0.08)
wait_js("document.querySelector('.cv-msgwin')?.dataset.state==='open' && !document.querySelector('.cv-msgwin')?.dataset.tweening")
save_check("快速反向开合", js("document.querySelectorAll('.stream-scroll').length===1 && document.querySelectorAll('.lg-diffusion').length===1"))

js("document.documentElement.dataset.appearance='dark'")
screenshot_state("desktop-dark")
js("document.documentElement.dataset.appearance='light'")
for feature, value in (("prefers-reduced-transparency", "reduce"), ("prefers-contrast", "more"), ("forced-colors", "active")):
    cdp("Emulation.setEmulatedMedia", features=[{"name": feature, "value": value}])
    save_check(feature, js("getComputedStyle(document.querySelector('.lg-diffusion')).display==='none' && getComputedStyle(document.querySelector('.lg-glass')).backgroundColor!=='rgba(0, 0, 0, 0)'"))
cdp("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "reduce"}])
save_check("减少动态效果", js("getComputedStyle(document.querySelector('.lg-sheen')).transform==='none'"))
button("收起执行流")
button("展开执行流")
save_check("减少动态效果下开合", js("document.querySelector('.cv-msgwin')?.dataset.state==='open'"))
cdp("Emulation.setEmulatedMedia", features=[])
cdp("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=1, mobile=True)
button("收起执行流")
screenshot_state("mobile-light")
js("document.documentElement.dataset.appearance='dark'")
screenshot_state("mobile-dark")
save_check("窄屏布局", js("document.documentElement.scrollWidth<=390"))
js("document.documentElement.dataset.appearance='light'")
cdp("Emulation.setDeviceMetricsOverride", width=1440, height=1000, deviceScaleFactor=1, mobile=False)
button("展开执行流")
js("document.querySelector('.composer textarea').focus()")
key("a", 2)
cdp("Input.insertText", text="持续输出验收")
key("Enter", 2)
wait_js("document.querySelector('.cv-msgwin')?.dataset.busy==='1' && document.querySelector('.stream-inner')?.textContent.includes('正在核验第')")
stream_open = sample("pan", 3000)
button("收起执行流")
wait_js("!document.querySelector('.stream-scroll')")
stream_min = sample("pan", 3000)
with urlopen(Request("http://127.0.0.1:8108/__finish", data=b"{}", headers={"Content-Type":"application/json"})) as response:
    response.read()
wait_js("document.querySelector('.cv-msgwin')?.dataset.busy==='0'")
save_check("持续输出与收起后的订阅", js("document.querySelector('.cv-agentboard').textContent.includes('3 / 3')"))
button("展开执行流")
save_check("重新展开显示新增消息", js("document.querySelector('.stream-inner')?.textContent.includes('正在核验第')"))

# 项目切换走现有路由，恢复项目布局只写隔离浏览器的本地存储。
goto_url(f"{URL}/workspace?project=perf-b")
wait_for_load()
wait_js("document.querySelector('.sp-space-title')?.textContent.includes('perf-b')")
save_check("项目切换", js("!document.querySelector('.sp-breadcrumb') && !document.querySelector('.composer textarea').value"))
goto_url(f"{URL}/workspace?project=perf-a")
wait_for_load()
wait_js("document.querySelector('[data-placement=\"materials\"]')?.getAttribute('aria-label')?.includes('100')")
button("打开项目资料")
wait_js("document.querySelector('.sp-pdf-thumbnail')?.width>0")
save_check("PDF 与图片资料加载", js("document.querySelector('.sp-pdf-thumbnail').width>0 && [...document.querySelectorAll('.sp-card img')].some(e=>e.naturalWidth>0)"))
screenshot_state("materials")
(OUT / "regression.json").write_text(json.dumps({"checks": checks, "streamOpen": stream_open, "streamMin": stream_min}, ensure_ascii=False, indent=2))
print("交互与材质回归通过", flush=True)
