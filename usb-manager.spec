Name:           usb-manager
Version:        1.3
Release:        1%{?dist}
Summary:        Droidspaces USB Device Manager - detect and manage USB storage and ADB devices

License:        MIT
URL:            https://github.com/Yizhou147/Droidspaces-USB-Manager
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
Requires:       python3, python3-qt5, util-linux, android-tools, ntfs-3g, exfatprogs, gvfs-mtp, gvfs-fuse, kio-extras, xdg-utils

%description
自动检测和管理 USB 存储设备和 ADB 设备。支持自动挂载、弹出、打开目录、
MTP 挂载与打开、Fastboot 设备直通等功能。

%prep
%setup -q -n %{name}-%{version}

%install
mkdir -p %{buildroot}%{_datadir}/usb-manager/icons
install -m 0644 src/usb-manager.py %{buildroot}%{_datadir}/usb-manager/
install -m 0755 src/usb-passthrough.sh %{buildroot}%{_datadir}/usb-manager/
install -m 0755 src/usb-storage-passthrough.sh %{buildroot}%{_datadir}/usb-manager/
install -m 0644 icons/*.svg %{buildroot}%{_datadir}/usb-manager/icons/
install -m 0644 icons/LICENSE %{buildroot}%{_datadir}/usb-manager/icons/
mkdir -p %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/usb-manager <<'EOF'
#!/usr/bin/env bash
exec python3 %{_datadir}/usb-manager/usb-manager.py "$@"
EOF
chmod 0755 %{buildroot}%{_bindir}/usb-manager
mkdir -p %{buildroot}%{_datadir}/applications
install -m 0644 desktop/usb-manager.desktop %{buildroot}%{_datadir}/applications/

%files
%{_datadir}/usb-manager/
%{_bindir}/usb-manager
%{_datadir}/applications/usb-manager.desktop

%changelog
* Wed Aug 12 2026 Droidspaces <droidspaces@example.com> - 1.3-1
- USB 设备准确识别（class 码分类）、MTP 挂载、Fastboot 支持
- blkid 路径动态检测、幽灵挂载清理、列宽可调
