中文 | [English](README_english.md)

# Droidspaces USB Manager

USB 设备管理工具，专为 **Droidspaces** Linux 容器环境设计，自动检测和管理 USB 存储设备和 ADB 设备。

## 功能特性

- 自动检测 USB 存储设备（U盘、移动硬盘等）
- 自动创建设备节点
- 自动挂载/卸载分区
- 支持打开挂载目录（Dolphin 文件管理器）
- 支持弹出设备（安全移除）
- **USB 设备准确识别**（基于 USB class 码）：Hub / ADB / Fastboot / 存储 / 键鼠 / 网络 / 音频 / 打印机等真实类型
- 自动检测 ADB 设备（Android 手机等），**Fastboot 模式设备自动连接**
- **MTP 挂载**：手机 MTP 存储自动挂载，可打开浏览手机文件
- 系统托盘图标
- **中英文语言切换**（自动检测系统语言）
- 支持 Wayland 和 X11
- 多分区支持（每个分区独立挂载）
- 自动清理 `~/USB-Storage` 下的幽灵挂载与残留目录
- **跨发行版支持**：Debian/Ubuntu、Arch、Fedora
- **免密访问 NTFS**：自动处理新版 ntfs-3g 的权限问题（ntfsusb 组）

## 安装方法

### 方法 1：使用 deb 包（Debian/Ubuntu）

从 [Releases](https://github.com/Yizhou147/Droidspaces-USB-Manager/releases) 下载最新版（v1.3，含 deb / rpm / Arch 三种包）：

```bash
sudo dpkg -i usb-manager_1.3-1_all.deb
sudo apt-get install -f  # 自动补齐依赖
```

Fedora：`sudo dnf install ./usb-manager-1.3-1.fc44.noarch.rpm`
Arch：

```bash
# 本地构建的包无 GPG 签名，需临时忽略签名验证（或自行签名）
printf '[options]\nSigLevel = Never\n' > /tmp/pacman-nosig.conf
sudo pacman -U --config /tmp/pacman-nosig.conf ./usb-manager-1.3-1-any.pkg.tar.zst
```

### 方法 2：手动安装（Debian/Ubuntu）

> 权限（sudoers / ntfsusb 组）配置较繁琐，**更推荐使用方法 3 的 `install.sh` 自动完成**。手动安装仅需：

```bash
# 安装依赖
sudo apt-get install python3 python3-pyqt5 udev util-linux gvfs-backends gvfs-fuse kio-extras

# 复制文件
sudo cp src/usb-manager.py /usr/share/usb-manager/
sudo cp src/usb-passthrough.sh /usr/share/usb-manager/
sudo cp src/usb-storage-passthrough.sh /usr/share/usb-manager/

# 创建桌面快捷方式
sudo cp desktop/usb-manager.desktop /usr/share/applications/

# 创建启动脚本
sudo cp debian/usr/bin/usb-manager /usr/bin/
sudo chmod +x /usr/bin/usb-manager
```

### 方法 3：Arch / Fedora 通用安装脚本（推荐）

项目内置跨发行版安装脚本 `install.sh`，自动检测 apt / dnf / pacman 并安装依赖，支持 Debian/Ubuntu、Arch、Fedora：

```bash
# 克隆仓库（本机直连 GitHub 不稳定时使用镜像站）
git clone https://gh-proxy.com/https://github.com/Yizhou147/Droidspaces-USB-Manager.git
cd Droidspaces-USB-Manager

# 运行安装脚本
sudo bash install.sh
```

脚本特性：
- 自动拉取最新源码安装（或 `--source DIR` 指定本地源码目录）
- 自动安装依赖（PyQt5、udev、util-linux、ntfs-3g 等）
- 配置免密码挂载（含 visudo 校验）与桌面快捷方式
- 将桌面用户加入 `ntfsusb` 组，解决新版 ntfs-3g 挂载 NTFS 卷的权限问题
- `--user USER` 可指定桌面用户

> **原作者致谢**：`install.sh` 由 [Goldzxcbug](https://github.com/Goldzxcbug) 编写（出自其 [Droidspaces-rootfs-KDE-builder](https://github.com/Goldzxcbug/Droidspaces-rootfs-KDE-builder) 仓库的 `scripts/install-usb-manager.sh`），供构建容器镜像时安装 USB Manager。本仓库在原脚本基础上升级维护，新增：MTP 依赖（gvfs/kio-extras）、blkid 路径动态检测、sudoers 双路径授权等。

## 使用方法

### 启动应用

```bash
# 从应用菜单启动
# 或者从终端启动
usb-manager
```

### 功能说明

1. **自动检测**：应用会自动扫描 USB 存储设备和 USB 设备（按 class 码分类）
2. **自动挂载**：新插入的 U 盘会自动挂载到 `~/USB-Storage/<分区名>`
3. **打开目录**：点击"打开"按钮会打开 Dolphin 文件管理器
4. **弹出设备**：点击"弹出"按钮会卸载设备并提示可安全移除
5. **ADB 设备**：自动检测 Android 手机等 ADB 设备（接口 `ff,42,01`）
6. **Fastboot**：Fastboot 模式设备（接口 `ff,42,03`）自动连接，可直接使用 `fastboot` 命令
7. **MTP**：手机 MTP 存储自动挂载（gvfs），点击"打开"通过文件管理器浏览手机文件

### 挂载点

- 默认挂载点：`~/USB-Storage/<分区名>`
- 每个分区独立挂载到子目录
- 可以在代码中修改 `MOUNT_BASE` 变量

## 依赖说明

### 各发行版安装命令

| 发行版 | PyQt5 | 其他核心依赖 | NTFS/exFAT | ADB | MTP |
|---|---|---|---|---|---|
| Debian/Ubuntu | `python3-pyqt5` | `python3 udev util-linux xdg-utils` | `ntfs-3g exfatprogs` | `android-tools-adb` | `gvfs-backends gvfs-fuse kio-extras` |
| Arch | `python-pyqt5` | `util-linux xdg-utils`（udev 随 systemd 提供） | `ntfs-3g exfatprogs` | `android-tools` | `gvfs gvfs-mtp kio-extras` |
| Fedora | `python3-qt5` | `systemd-udev util-linux xdg-utils` | `ntfs-3g* exfatprogs` | `android-tools*` | `gvfs-mtp gvfs-fuse kio-extras` |

> `*` Fedora 的 `ntfs-3g` / `android-tools` 在 RPM Fusion 仓库，需先启用：
>
> ```bash
> sudo dnf install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
> ```

### 功能说明

- `python3`：Python 3.x
- PyQt5：Qt5 图形界面库（各发行版包名见上表）
- `udev`：设备管理（Arch 随 systemd 提供）
- `util-linux`：blkid、mount、umount、mknod 等工具
- `xdg-utils`：`xdg-open`（未检测到 Dolphin 等文件管理器时的回退方案）
- `ntfs-3g`：NTFS 支持
- `exfatprogs`：exFAT 支持
- `dolphin`：KDE 文件管理器（其他发行版无 Dolphin 时自动回退到 nautilus/thunar/xdg-open）
- `gvfs` / `gvfs-backends` / `gvfs-mtp` / `gvfs-fuse`：MTP 挂载与本地目录映射（Arch 的 `gvfs` 包自带 gvfsd-fuse，无需 `gvfs-fuse`）
- `kio-extras`：KDE 文件管理器（Dolphin）的 MTP 支持

### NTFS 权限说明（重要）

ntfs-3g 的 **integrated FUSE** 架构版本（Fedora/Arch 的 2026.x、Ubuntu 26.04 的 `2022.10.3 integrated FUSE`）挂载 NTFS 卷时，`uid/gid/umask/chmod` 等选项全部失效，所有文件固定映射为 `root:1023 770`，普通用户无法访问。`install.sh` 已自动处理：将桌面用户加入 gid 1023 的 `ntfsusb` 组，即可直接读写，无需输密码（**加入组后需注销重新登录生效**）。

Debian 13 stable 的传统 ntfs-3g（2022.10.3，非 integrated FUSE）`uid/gid` 选项正常生效，挂载后属主即为用户，天然免密。

## 卸载方法

Debian/Ubuntu（deb 包安装）：

```bash
sudo dpkg -r usb-manager
```

install.sh 安装：

```bash
sudo rm -rf /usr/share/usb-manager /usr/bin/usb-manager \
    /usr/share/applications/usb-manager.desktop \
    /etc/sudoers.d/droidspaces-usb-manager
# 可选：移除 ntfsusb 组
sudo groupdel ntfsusb
```

## 文件说明

- `src/usb-manager.py`：主程序
- `src/usb-passthrough.sh`：ADB 设备节点创建脚本
- `src/usb-storage-passthrough.sh`：USB 存储设备节点创建脚本
- `desktop/usb-manager.desktop`：桌面快捷方式
- `debian/`：Debian/Ubuntu deb 打包目录
- `install.sh`：跨发行版安装脚本（原作者 [Goldzxcbug](https://github.com/Goldzxcbug)，出自其 [Droidspaces-rootfs-KDE-builder](https://github.com/Goldzxcbug/Droidspaces-rootfs-KDE-builder) 的 `scripts/install-usb-manager.sh`）
- `icons/`：应用图标

## 许可证

MIT License
