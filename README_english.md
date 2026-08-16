[中文](README.md) | English

# Droidspaces USB Manager

USB device management tool designed for the **Droidspaces** Linux container environment. Automatically detects and manages USB storage devices and ADB devices.

## Features

- Auto-detect USB storage devices (USB drives, portable hard drives, etc.)
- Auto-create device nodes
- Auto-mount/unmount partitions
- Support opening mounted directories (Dolphin file manager)
- Support ejecting devices (safe removal)
- **Accurate USB device classification** (based on USB class codes): Hub / ADB / Fastboot / Storage / HID / Network / Audio / Printer, etc.
- Auto-detect ADB devices (Android phones, etc.); **Fastboot devices auto-connect**
- **MTP mounting**: phone MTP storage auto-mounts, browse phone files with a file manager
- System tray icon
- **Chinese/English language switching** (auto-detect system language)
- Support Wayland and X11
- Multi-partition support (each partition mounted independently)
- Auto-clean stale mounts and leftover directories under `~/USB-Storage`
- **Cross-distro support**: Debian/Ubuntu, Arch, Fedora
- **Passwordless NTFS access**: automatically handles newer ntfs-3g permission issues (ntfsusb group)

## Installation

### Method 1: Cross-distro install script (recommended, all platforms)

The repository bundles a cross-distro installer `install.sh` that auto-detects apt / dnf / pacman and installs dependencies. Supports Debian/Ubuntu, Arch, and Fedora:

```bash
git clone https://github.com/Yizhou147/Droidspaces-USB-Manager.git
cd Droidspaces-USB-Manager
sudo bash install.sh
```

You can also download and run the script directly without cloning the whole repository:

```bash
curl -fsSL -o /tmp/usb-manager-install.sh https://raw.githubusercontent.com/Yizhou147/Droidspaces-USB-Manager/main/install.sh
sudo bash /tmp/usb-manager-install.sh
```

Script features:
- Pulls the latest sources for installation (or `--source DIR` to use a local source directory)
- Auto-installs dependencies (PyQt5, udev, util-linux, ntfs-3g, etc.)
- Configures passwordless mounting (with visudo validation) and a desktop shortcut
- Adds the desktop user to the `ntfsusb` group to fix NTFS permission issues with newer ntfs-3g
- `--user USER` to specify the desktop user

> **Author credit**: `install.sh` was written by [Goldzxcbug](https://github.com/Goldzxcbug) (from `scripts/install-usb-manager.sh` in his [Droidspaces-rootfs-KDE-builder](https://github.com/Goldzxcbug/Droidspaces-rootfs-KDE-builder) repository), used when building container images. This repository maintains and extends the original script with: MTP dependencies (gvfs/kio-extras), dynamic blkid path detection, and dual-path sudoers authorization.

### Method 2: Packages (deb for Debian/Ubuntu, rpm for Fedora, Arch package for Arch)

Download the latest release (v1.3, includes deb / rpm / Arch packages) from [Releases](https://github.com/Yizhou147/Droidspaces-USB-Manager/releases):

```bash
sudo dpkg -i usb-manager_1.3-1_all.deb
sudo apt-get install -f  # Auto-install dependencies
```

Fedora: `sudo dnf install ./usb-manager-1.3-1.fc44.noarch.rpm`
Arch:

```bash
# Locally built package has no GPG signature; temporarily disable signature checks (or sign it yourself)
printf '[options]\nSigLevel = Never\n' > /tmp/pacman-nosig.conf
sudo pacman -U --config /tmp/pacman-nosig.conf ./usb-manager-1.3-1-any.pkg.tar.zst
```

### Method 3: Manual Installation (Debian/Ubuntu)

> Permission setup (sudoers / ntfsusb group) is tedious; **Method 1 with `install.sh` is recommended**. Manual install only needs:

```bash
# Install dependencies
sudo apt-get install python3 python3-pyqt5 udev util-linux gvfs-backends gvfs-fuse kio-extras

# Copy files
sudo cp src/usb-manager.py /usr/share/usb-manager/
sudo cp src/usb-passthrough.sh /usr/share/usb-manager/
sudo cp src/usb-storage-passthrough.sh /usr/share/usb-manager/

# Create desktop shortcut
sudo cp desktop/usb-manager.desktop /usr/share/applications/

# Create launch script
sudo cp debian/usr/bin/usb-manager /usr/bin/
sudo chmod +x /usr/bin/usb-manager
```

## Usage

### Launch Application

```bash
# Launch from application menu
# Or launch from terminal
usb-manager
```

### Feature Description

1. **Auto-detect**: Application automatically scans USB storage devices and classifies USB devices (by class codes)
2. **Auto-mount**: Newly inserted USB drives are automatically mounted to `~/USB-Storage/<partition_name>`
3. **Open Directory**: Click "Open" button to open Dolphin file manager
4. **Eject Device**: Click "Eject" button to unmount device and prompt safe removal
5. **ADB Device**: Auto-detect Android phones and other ADB devices (interface `ff,42,01`)
6. **Fastboot**: Fastboot-mode devices (interface `ff,42,03`) auto-connect; use `fastboot` directly
7. **MTP**: Phone MTP storage auto-mounts (gvfs); click "Open" to browse phone files in a file manager

### Mount Points

- Default mount point: `~/USB-Storage/<partition_name>`
- Each partition is mounted to its own subdirectory
- Can modify `MOUNT_BASE` variable in code

## Dependencies

### Packages per distribution

| Distro | PyQt5 | Other core deps | NTFS/exFAT | ADB | MTP |
|---|---|---|---|---|---|
| Debian/Ubuntu | `python3-pyqt5` | `python3 udev util-linux xdg-utils` | `ntfs-3g exfatprogs` | `android-tools-adb` | `gvfs-backends gvfs-fuse kio-extras` |
| Arch | `python-pyqt5` | `util-linux xdg-utils` (udev ships with systemd) | `ntfs-3g exfatprogs` | `android-tools` | `gvfs gvfs-mtp kio-extras` |
| Fedora | `python3-qt5` | `systemd-udev util-linux xdg-utils` | `ntfs-3g* exfatprogs` | `android-tools*` | `gvfs-mtp gvfs-fuse kio-extras` |

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
- `gvfs` / `gvfs-backends` / `gvfs-mtp` / `gvfs-fuse`: MTP mounting and local-directory mapping (Arch's `gvfs` includes gvfsd-fuse; no `gvfs-fuse` needed)
- `kio-extras`: MTP support for KDE file manager (Dolphin)

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
- `install.sh`: Cross-distro installer (written by [Goldzxcbug](https://github.com/Goldzxcbug), from `scripts/install-usb-manager.sh` in his [Droidspaces-rootfs-KDE-builder](https://github.com/Goldzxcbug/Droidspaces-rootfs-KDE-builder))
- `icons/`: Application icons

## License

MIT License
