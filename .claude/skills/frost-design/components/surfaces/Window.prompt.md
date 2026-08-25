# Window

macOS window chrome — soft-glass (霜) toolbar with traffic-light dots, title + subtitle, trailing `actions`, 12px corners, floating level-3 shadow. The frame for any full app view; sit it on a `.frost-wallpaper`.

```jsx
<Window
  title="仿真软件开发服务采购项目"
  subtitle="投标文件"
  actions={<>
    <IconButton icon="sidebar-simple" label="侧栏" />
    <Segmented options={["编制", "预览"]} defaultValue="编制" />
  </>}
  style={{ height: 620 }}
>
  {/* sidebar + stream + inspector */}
</Window>
```

Set an explicit height on the window; the body fills the rest below the 52px toolbar. The toolbar is embedded chrome (`frost-glass--flush`): no float, no rim, a .5px contact edge where it meets the body — never a 1px divider. Pass `toolbarClassName=""` for a solid toolbar.
