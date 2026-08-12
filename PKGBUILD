# Maintainer: Droidspaces <droidspaces@example.com>
pkgname=usb-manager
pkgver=1.3
pkgrel=1
pkgdesc="Droidspaces USB 设备管理器：自动检测、挂载 USB 存储和 ADB/Fastboot 设备，支持 MTP 挂载"
arch=('any')
url="https://github.com/Yizhou147/Droidspaces-USB-Manager"
license=('MIT')
depends=('python' 'python-pyqt5' 'util-linux' 'android-tools' 'ntfs-3g' 'exfatprogs' 'gvfs' 'gvfs-mtp' 'kio-extras' 'xdg-utils')
source=("$pkgname-$pkgver.tar.gz")
sha256sums=('SKIP')

package() {
  install -d "$pkgdir/usr/share/usb-manager/icons"
  install -m 0644 src/usb-manager.py "$pkgdir/usr/share/usb-manager/"
  install -m 0755 src/usb-passthrough.sh "$pkgdir/usr/share/usb-manager/"
  install -m 0755 src/usb-storage-passthrough.sh "$pkgdir/usr/share/usb-manager/"
  install -m 0644 icons/*.svg "$pkgdir/usr/share/usb-manager/icons/"
  install -m 0644 icons/LICENSE "$pkgdir/usr/share/usb-manager/icons/"
  install -d "$pkgdir/usr/bin"
  cat > "$pkgdir/usr/bin/usb-manager" <<'EOF'
#!/usr/bin/env bash
exec python3 /usr/share/usb-manager/usb-manager.py "$@"
EOF
  chmod 0755 "$pkgdir/usr/bin/usb-manager"
  install -d "$pkgdir/usr/share/applications"
  install -m 0644 desktop/usb-manager.desktop "$pkgdir/usr/share/applications/"
}
