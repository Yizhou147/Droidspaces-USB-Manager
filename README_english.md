[中文](README.md) | English

# Droidspaces USB Manager

USB device management tool designed for the **Droidspaces** Linux container environment. Automatically detects and manages USB storage devices and ADB devices.

## Features

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
- **Cross-distro support**: Debian/Ubuntu, Arch, Fedora
- **Passwordless NTFS access**: automatically handles newer ntfs-3g permission issues (ntfsusb group)

## Installation

### Method 1: Using deb package (Debian/Ubuntu)

```bash
sudo dpkg -i usb-manager-v1.2.deb
sudo apt-get install -f  # Auto-install dependencies
```

### Method 2: Manual Installation (Debian/Ubuntu)

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

### Method 3: Cross-distro Install Script (Arch / Fedora, recommended)

The repository bundles a cross-distro installer `install.sh` that auto-detects apt / dnf / pacman and installs dependencies. Supports Debian/Ubuntu, Arch, and Fedora:

```bash
# Clone the repository (use the mirror prefix if direct GitHub access is unstable)
git clone https://gh-proxy.com/https://github.com/Yizhou147/Droidspaces-USB-Manager.git
cd Droidspaces-USB-Manager

# Run the installer
sudo bash install.sh
```

Script features:
- Pulls the latest sources for installation (or `--source DIR` to use a local source directory)
- Auto-installs dependencies (PyQt5, udev, util-linux, ntfs-3g, etc.)
- Configures passwordless mounting (with visudo validation) and a desktop shortcut
- Adds the desktop user to the `ntfsusb` group to fix NTFS permission issues with newer ntfs-3g
- `--user USER` to specify the desktop user

> This script is derived from `scripts/install-usb-manager.sh` in the [Droidspaces-rootfs-KDE-builder](https://github.com/Goldzxcbug/Droidspaces-rootfs-KDE-builder) repository, used when building container images.

## Usage

### Launch Application

```bash
# Launch from application menu
# Or launch from terminal
usb-manager
```

### Feature Description

1. **Auto-detect**: Application automatically scans USB storage devices and ADB devices
2. **Auto-mount**: Newly inserted USB drives are automatically mounted to `~/USB-Storage/<partition_name>`
3. **Open Directory**: Click "Open Dir" button to open Dolphin file manager
4. **Eject Device**: Click "Eject" button to unmount device and prompt safe removal
5. **ADB Device**: Auto-detect Android phones and other ADB devices

### Mount Points

- Default mount point: `~/USB-Storage/<partition_name>`
- Each partition is mounted to its own subdirectory
- Can modify `MOUNT_BASE` variable in code

## Dependencies

### Packages per distribution

| Distro | PyQt5 | Other core deps | NTFS/exFAT | ADB |
|---|---|---|---|---|
| Debian/Ubuntu | `python3-pyqt5` | `python3 udev util-linux xdg-utils` | `ntfs-3g exfatprogs` | `android-tools-adb` |
| Arch | `python-pyqt5` | `util-linux xdg-utils` (udev ships with systemd) | `ntfs-3g exfatprogs` | `android-tools` |
| Fedora | `python3-qt5` | `systemd-udev util-linux xdg-utils` | `ntfs-3g* exfatprogs` | `android-tools*` |

> `*` On Fedora, `ntfs-3g` / `android-tools` live in RPM Fusion; enable it first:
>
> ```bash
> sudo dnf install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
> ```

### Notes

- `python3`: Python 3.x
- PyQt5: Qt5 GUI library (see table above for package names)
- `udev`: Device management (ships with systemd on Arch)
- `util-linux`: blkid, mount, umount, mknod, etc.
- `xdg-utils`: provides `xdg-open` (fallback when Dolphin etc. is not found)
- `ntfs-3g`: NTFS support
- `exfatprogs`: exFAT support
- `dolphin`: KDE file manager (falls back to nautilus/thunar/xdg-open when missing)

### NTFS Permissions (important)

ntfs-3g builds using the **integrated FUSE** architecture (2026.x on Fedora/Arch, and `2022.10.3 integrated FUSE` on Ubuntu 26.04) ignore the `uid/gid/umask/chmod` options entirely and map every file to `root:1023 770`, making it inaccessible to normal users. `install.sh` handles this automatically by adding the desktop user to the gid 1023 `ntfsusb` group, granting direct read/write access without a password (**log out and back in for the group to take effect**).

On Debian 13 stable (traditional ntfs-3g 2022.10.3, non-integrated-FUSE), the `uid/gid` options work normally, so the mount point is owned by the user and no password is needed.

## Uninstall

Debian/Ubuntu (installed via deb package):

```bash
sudo dpkg -r usb-manager
```

Installed via install.sh:

```bash
sudo rm -rf /usr/share/usb-manager /usr/bin/usb-manager \
    /usr/share/applications/usb-manager.desktop \
    /etc/sudoers.d/droidspaces-usb-manager
# Optional: remove the ntfsusb group
sudo groupdel ntfsusb
```

## File Description

- `src/usb-manager.py`: Main program
- `src/usb-passthrough.sh`: ADB device node creation script
- `src/usb-storage-passthrough.sh`: USB storage device node creation script
- `desktop/usb-manager.desktop`: Desktop shortcut
- `debian/`: Debian/Ubuntu deb packaging directory
- `install.sh`: Cross-distro installer (derived from `scripts/install-usb-manager.sh` in [Droidspaces-rootfs-KDE-builder](https://github.com/Goldzxcbug/Droidspaces-rootfs-KDE-builder))
- `icons/`: Application icons

## License

MIT License
