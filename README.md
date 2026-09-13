中文

# Droidspaces USB Manager（C# 版 / 柚坛工具箱集成版）

> 本分支（`feat/csharp-port`）是 USB 管理器的 **C# 原生重写版**，作为 [UotanToolboxNT（柚坛工具箱）](https://github.com/Uotan-Dev/UotanToolboxNT) 的功能模块实现，面向 **Droidspaces 专版、仅适配 ARM64 Linux deb**。
> PyQt5 原版（独立应用，v1.4）仍在 `main` 分支维护，二者功能对齐、实现独立。

## 为什么重写

| | main 分支（PyQt5 原版） | 本分支（C# 版） |
|---|---|---|
| UI | PyQt5 独立窗口 | Avalonia + SukiUI，融入柚坛工具箱侧栏 |
| 运行时 | python3 + PyQt5 + gvfs 等一串依赖 | .NET 10 self-contained，deb 仅依赖系统组件 |
| 分发 | install.sh / deb / rpm / arch | 柚坛工具箱 Droidspaces 专版 deb（arm64） |
| 系统级配置 | install.sh 手动执行 | deb postinst 自动完成 |

## 功能（与 v1.4 对齐）

- **设备识别**：sysfs `bDeviceClass` + 接口 `(Class,SubClass,Protocol)` 三层分类——Hub / HID / 音频 / 视频 / 网络 / 存储 / 打印机 / ADB `(ff,42,01)` / Fastboot `(ff,42,03)`；`0xef`（Misc/IAD）按接口判定；多接口设备按优先级选主类型
- **USB 存储**：自动补齐 `/dev/sdX*` 节点（devtmpfs 静态容器不自动建）、NTFS/exFAT/vfat 带 uid/gid/umask 挂载、幽灵挂载清理（按 sysfs 判断内核块设备是否已消失）、弹出/打开目录
- **NTFS 免密**：`ntfsusb`（gid 1023）组方案，绕过新版 ntfs-3g（integrated FUSE）忽略 uid/gid 的问题
- **MTP**：gio URI 方式挂载 `mtp://[usb:bbb,ddd]`、自动拉起 gvfsd-fuse、按 busnum/devnum 精确匹配 gvfs 本地目录（防幽灵挂载）
- **UVC 采集卡**：`/dev/video*` 节点自校正（libc `stat` 比对 `st_rdev`，识别拔插后漂移的 stale 节点）、`VIDIOC_QUERYCAP` 剔除 metadata 节点、ffplay/mpv 一键预览
- **ADB/Fastboot**：复用 `usb-passthrough.sh` 创建 `/dev/bus/usb` 节点；脚本不 kill-server，adb 命令带超时

## 代码结构（本分支）

```
csharp/
├── Features/UsbManager/          # 柚坛工具箱功能模块（核心代码）
│   ├── UsbHardware.cs            #   硬件层：扫描/分类/节点/挂载/MTP/UVC
│   ├── UsbManagerViewModel.cs    #   视图模型：自动扫描/防重入/后台操作/行渲染
│   └── UsbManagerView.axaml(.cs) #   SukiUI 界面
├── Assets/USB/usb-passthrough.sh # ADB/Fastboot 直通脚本（随包携带）
├── Assets/Linux/control-arm64    # deb control（Depends 已补 ntfs-3g/exfatprogs/gvfs-*）
├── Assets/Linux/postinst         # 装包自动配置：sudoers / ntfsusb 组 / fuse allow_other
└── workflows/droidspaces_deb.yml # GitHub Actions：仅构建 linux-arm64 deb
```

## 集成到 UotanToolboxNT

完整可编译的集成见柚坛工具箱分支 [Yizhou147/UotanToolboxNT `feat/droidspaces-usb-manager`](https://github.com/Yizhou147/UotanToolboxNT/tree/feat/droidspaces-usb-manager)，需做四件事：

1. **拷贝模块**：`csharp/Features/UsbManager/` → `UotanToolbox/Features/UsbManager/`（`MainPageBase` 子类经 DI 自动注册进侧栏，ViewLocator 自动映射视图，无需改导航代码）
2. **脚本随包**：`Assets/USB/` 加入 csproj 的 `Content`（CopyToOutputDirectory），并从 `AvaloniaResource` 排除：
   ```xml
   <AvaloniaResource Include="Assets\**" Exclude="Assets\USB\**" />
   <Content Include="Assets\USB\**" CopyToOutputDirectory="PreserveNewest" />
   ```
3. **i18n**：`Sidebar_UsbManager` + 全部 `Usb_*` 词条（共 56 条）加入 `Assets/Resources.resx`、`Resources.zh-CN.resx`、`Resources.Designer.cs`（键清单可直接从 `UsbManagerViewModel.cs` / `UsbManagerView.axaml` 中 grep）
4. **脚本路径**：运行时按 `AppContext.BaseDirectory/Assets/USB/usb-passthrough.sh` 解析（deb 中即 `/usr/lib/UotanToolbox/Assets/USB/`），sudoers 授权的正是这个路径

## 构建与安装

```bash
# 编译（arm64 self-contained）
dotnet publish -r linux-arm64 --self-contained true -o ./publish-arm64

# 云构建（推荐）：UotanToolboxNT 仓库手动触发 droidspaces_deb workflow
# 产物：UotanToolbox_Droidspaces_arm64_<版本>.deb（约 98MB）

# 安装（会自动执行 postinst：sudoers 免密授权、ntfsusb 组、fuse.conf）
sudo apt install ./UotanToolbox_Droidspaces_arm64_<版本>.deb
```

安装后**需注销重新登录**（ntfsusb 组对新会话才生效）。侧栏进入 **USB Manager / USB 管理器** 页面即可使用。

> fork 仓库若从未跑过 Actions：workflow 需附带 `push` 触发器跑通一次后，`workflow_dispatch` 才会注册可用（GitHub 的 workflow 注册表只反映默认分支）。

## 与 PyQt5 版的行为差异

- 无系统托盘（Droidspaces 容器场景不需要）
- 语言跟随工具箱设置（resx），不再有独立语言配置
- 预览失败提示改为退出码（不再落 /tmp 日志文件）
- 弹出后暂停的是本页面的自动扫描，点"刷新"恢复

## 致谢

- [Uotan-Dev/UotanToolboxNT](https://github.com/Uotan-Dev/UotanToolboxNT) —— 柚坛工具箱（Avalonia + SukiUI）
- [Goldzxcbug/Droidspaces-rootfs-KDE-builder](https://github.com/Goldzxcbug/Droidspaces-rootfs-KDE-builder) —— install.sh 原作者
- PyQt5 原版的全部实践（class 码分类、NTFS gid 1023 方案、MTP URI 挂载、gvfsd-fuse、stale 节点比对等）均沉淀自 `main` 分支的开发过程

## License

MIT（与 main 分支一致）
