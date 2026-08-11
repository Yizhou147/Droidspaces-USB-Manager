中文 | [English](README_english.md)

# Droidspaces USB Manager

USB 设备管理工具，专为 **Droidspaces** Linux 容器环境设计，自动检测和管理 USB 存储设备和 ADB 设备。

## 功能特性

- 自动检测 USB 存储设备（U盘、移动硬盘等）
- 自动创建设备节点
- 自动挂载/卸载分区
- 支持打开挂载目录（Dolphin 文件管理器）
- 支持弹出设备（安全移除）
- 自动检测 ADB 设备（Android 手机等）
- 系统托盘图标
- **中英文语言切换**（自动检测系统语言）
- 支持 Wayland 和 X11
- 多分区支持（每个分区独立挂载）

## 安装方法

### 方法 1：使用 deb 包（推荐）

```bash
sudo dpkg -i usb-manager-v1.2.deb
sudo apt-get install -f  # 自动补齐依赖
```

### 方法 2：手动安装

```bash
# 安装依赖
sudo apt-get install python3 python3-pyqt5 udev util-linux

# 复制文件
sudo cp src/usb-manager.py /usr/share/usb-manager/
sudo cp src/usb-passthrough.sh /usr/share/usb-manager/
sudo cp src/usb-storage-passthrough.sh /usr/share/usb-manager/

# 创建桌面快捷方式
sudo cp desktop/usb-manager.desktop /usr/share/applications/

# 创建启动脚本
sudo cp debian/usr/bin/usb-manager /usr/bin/
sudo chmod +x /usr/bin/usb-manager

# 配置 sudoers（可选，用于无密码挂载）
sudo cp debian/etc/sudoers.d/usb-storage /etc/sudoers.d/
sudo chmod 440 /etc/sudoers.d/usb-storage
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

> 该脚本同样存在于 [Droidspaces-rootfs-KDE-builder](https://github.com/Yizhou147/Droidspaces-rootfs-KDE-builder) 仓库的 `scripts/install-usb-manager.sh`，供构建容器镜像时使用。

## 使用方法

### 启动应用

```bash
# 从应用菜单启动
# 或者从终端启动
usb-manager
```

### 功能说明

1. **自动检测**：应用会自动扫描 USB 存储设备和 ADB 设备
2. **自动挂载**：新插入的 U 盘会自动挂载到 `~/USB-Storage/<分区名>`
3. **打开目录**：点击"打开目录"按钮会打开 Dolphin 文件管理器
4. **弹出设备**：点击"弹出"按钮会卸载设备并提示可安全移除
5. **ADB 设备**：自动检测 Android 手机等 ADB 设备

### 挂载点

- 默认挂载点：`~/USB-Storage/<分区名>`
- 每个分区独立挂载到子目录
- 可以在代码中修改 `MOUNT_BASE` 变量

## 依赖说明

### 必需依赖

- `python3`：Python 3.x
- `python3-pyqt5`：Qt5 图形界面库
- `udev`：设备管理
- `util-linux`：blkid、mount 等工具

### 可选依赖

- `ntfs-3g`：NTFS 文件系统支持（用于挂载 Windows 格式的 U 盘）
- `exfat-fuse`：exFAT 文件系统支持
- `kio-admin`：KDE Dolphin 管理员模式支持

### NTFS 支持

如果需要挂载 NTFS 格式的 U 盘，需要手动安装 ntfs-3g：

```bash
sudo apt-get install ntfs-3g
```

## 卸载方法

```bash
sudo dpkg -r usb-manager
```

## 文件说明

- `usb-manager.py`：主程序
- `usb-passthrough.sh`：ADB 设备节点创建脚本
- `usb-storage-passthrough.sh`：USB 存储设备节点创建脚本
- `usb-manager.desktop`：桌面快捷方式
- `usb-manager`：启动脚本
- `usb-storage`：sudoers 配置文件

## 许可证

MIT License
