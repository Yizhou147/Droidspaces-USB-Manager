# Droidspaces USB Manager

USB device management tool designed for the **Droidspaces** Linux container environment. Automatically detects and manages USB storage devices and ADB devices.

---

## English

### Features

- Auto-detect USB storage devices (USB drives, portable hard drives, etc.)
- Auto-create device nodes
- Auto-mount/unmount partitions
- Support opening mounted directories (Dolphin file manager)
- Support ejecting devices (safe removal)
- Auto-detect ADB devices (Android phones, etc.)
- System tray icon
- **Chinese/English language switching** (auto-detect system language)
- Support Wayland and X11
- Multi-partition support (each partition mounted independently)

### Installation

#### Method 1: Using deb package (Recommended)

```bash
sudo dpkg -i usb-manager-v1.2.deb
sudo apt-get install -f  # Auto-install dependencies
```

#### Method 2: Manual Installation

```bash
# Install dependencies
sudo apt-get install python3 python3-pyqt5 udev util-linux

# Copy files
sudo cp src/usb-manager.py /usr/share/usb-manager/
sudo cp src/usb-passthrough.sh /usr/share/usb-manager/
sudo cp src/usb-storage-passthrough.sh /usr/share/usb-manager/

# Create desktop shortcut
sudo cp desktop/usb-manager.desktop /usr/share/applications/

# Create launch script
sudo cp debian/usr/bin/usb-manager /usr/bin/
sudo chmod +x /usr/bin/usb-manager

# Configure sudoers (optional, for passwordless mount)
sudo cp debian/etc/sudoers.d/usb-storage /etc/sudoers.d/
sudo chmod 440 /etc/sudoers.d/usb-storage
```

### Usage

#### Launch Application

```bash
# Launch from application menu
# Or launch from terminal
usb-manager
```

#### Feature Description

1. **Auto-detect**: Application automatically scans USB storage devices and ADB devices
2. **Auto-mount**: Newly inserted USB drives are automatically mounted to `~/USB-Storage/<partition_name>`
3. **Open Directory**: Click "Open Dir" button to open Dolphin file manager
4. **Eject Device**: Click "Eject" button to unmount device and prompt safe removal
5. **ADB Device**: Auto-detect Android phones and other ADB devices

#### Mount Points

- Default mount point: `~/USB-Storage/<partition_name>`
- Each partition is mounted to its own subdirectory
- Can modify `MOUNT_BASE` variable in code

### Dependencies

#### Required

- `python3`: Python 3.x
- `python3-pyqt5`: Qt5 GUI library
- `udev`: Device management
- `util-linux`: blkid, mount, etc.

#### Optional

- `ntfs-3g`: NTFS filesystem support (for Windows-formatted USB drives)
- `exfat-fuse`: exFAT filesystem support
- `kio-admin`: KDE Dolphin admin mode support

#### NTFS Support

To mount NTFS-formatted USB drives, manually install ntfs-3g:

```bash
sudo apt-get install ntfs-3g
```

### Uninstall

```bash
sudo dpkg -r usb-manager
```

### File Description

- `usb-manager.py`: Main program
- `usb-passthrough.sh`: ADB device node creation script
- `usb-storage-passthrough.sh`: USB storage device node creation script
- `usb-manager.desktop`: Desktop shortcut
- `usb-manager`: Launch script
- `usb-storage`: sudoers configuration file

### License

MIT License

---

## 中文

### 功能特性

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

### 安装方法

#### 方法 1：使用 deb 包（推荐）

```bash
sudo dpkg -i usb-manager-v1.2.deb
sudo apt-get install -f  # 自动补齐依赖
```

#### 方法 2：手动安装

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

### 使用方法

#### 启动应用

```bash
# 从应用菜单启动
# 或者从终端启动
usb-manager
```

#### 功能说明

1. **自动检测**：应用会自动扫描 USB 存储设备和 ADB 设备
2. **自动挂载**：新插入的 U 盘会自动挂载到 `~/USB-Storage/<分区名>`
3. **打开目录**：点击"打开目录"按钮会打开 Dolphin 文件管理器
4. **弹出设备**：点击"弹出"按钮会卸载设备并提示可安全移除
5. **ADB 设备**：自动检测 Android 手机等 ADB 设备

#### 挂载点

- 默认挂载点：`~/USB-Storage/<分区名>`
- 每个分区独立挂载到子目录
- 可以在代码中修改 `MOUNT_BASE` 变量

### 依赖说明

#### 必需依赖

- `python3`：Python 3.x
- `python3-pyqt5`：Qt5 图形界面库
- `udev`：设备管理
- `util-linux`：blkid、mount 等工具

#### 可选依赖

- `ntfs-3g`：NTFS 文件系统支持（用于挂载 Windows 格式的 U 盘）
- `exfat-fuse`：exFAT 文件系统支持
- `kio-admin`：KDE Dolphin 管理员模式支持

#### NTFS 支持

如果需要挂载 NTFS 格式的 U 盘，需要手动安装 ntfs-3g：

```bash
sudo apt-get install ntfs-3g
```

### 卸载方法

```bash
sudo dpkg -r usb-manager
```

### 文件说明

- `usb-manager.py`：主程序
- `usb-passthrough.sh`：ADB 设备节点创建脚本
- `usb-storage-passthrough.sh`：USB 存储设备节点创建脚本
- `usb-manager.desktop`：桌面快捷方式
- `usb-manager`：启动脚本
- `usb-storage`：sudoers 配置文件

### 许可证

MIT License
