#!/usr/bin/env python3
"""
Droidspaces USB Storage Passthrough - 系统托盘版
带 GUI 的 USB 存储设备管理工具
"""

import sys
import os
import subprocess
import pwd
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QAction,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QGroupBox, QStatusBar, QWidget
)
from PyQt5.QtGui import QIcon, QPixmap, QFont
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal


class ScanWorker(QThread):
    """后台扫描 USB 设备的线程"""
    finished = pyqtSignal(list)

    def run(self):
        devices = self.scan_usb_devices()
        self.finished.emit(devices)

    def scan_usb_devices(self):
        """扫描 USB 存储设备"""
        devices = []
        scsi_base = Path("/sys/bus/scsi/devices")

        if not scsi_base.exists():
            return devices

        for scsi_dev in scsi_base.iterdir():
            block_dir = scsi_dev / "block"
            if not block_dir.exists():
                continue

            for block_dev in block_dir.iterdir():
                if not block_dev.is_dir():
                    continue

                # 检查是否是 USB 设备
                real_path = scsi_dev.resolve()
                if "usb" not in str(real_path):
                    continue

                dev_file = block_dev / "dev"
                if not dev_file.exists():
                    continue

                # 读取设备信息
                try:
                    major_minor = dev_file.read_text().strip()
                    major, minor = major_minor.split(":")

                    vendor = (scsi_dev / "vendor").read_text().strip() if (scsi_dev / "vendor").exists() else "Unknown"
                    model = (scsi_dev / "model").read_text().strip() if (scsi_dev / "model").exists() else "Unknown"

                    size_file = block_dev / "size"
                    size_sectors = int(size_file.read_text().strip()) if size_file.exists() else 0
                    size_gb = size_sectors * 512 // 1073741824

                    block_name = block_dev.name
                    node_path = f"/dev/{block_name}"

                    # 检查是否已挂载
                    mounted_at = self.get_mount_point(node_path)

                    device_info = {
                        "name": block_name,
                        "node": node_path,
                        "major": major,
                        "minor": minor,
                        "vendor": vendor,
                        "model": model,
                        "size_gb": size_gb,
                        "mounted": mounted_at is not None,
                        "mount_point": mounted_at,
                        "partitions": []
                    }

                    # 扫描分区
                    for part_dir in block_dev.glob(f"{block_name}*"):
                        if part_dir == block_dev:
                            continue

                        part_dev_file = part_dir / "dev"
                        if not part_dev_file.exists():
                            continue

                        part_major_minor = part_dev_file.read_text().strip()
                        part_major, part_minor = part_major_minor.split(":")

                        part_size_file = part_dir / "size"
                        part_size_sectors = int(part_size_file.read_text().strip()) if part_size_file.exists() else 0
                        part_size_gb = part_size_sectors * 512 // 1073741824

                        part_name = part_dir.name
                        part_node = f"/dev/{part_name}"
                        part_mounted = self.get_mount_point(part_node)

                        device_info["partitions"].append({
                            "name": part_name,
                            "node": part_node,
                            "major": part_major,
                            "minor": part_minor,
                            "size_gb": part_size_gb,
                            "mounted": part_mounted is not None,
                            "mount_point": part_mounted
                        })

                    devices.append(device_info)

                except Exception as e:
                    print(f"Error reading device {block_dev}: {e}")
                    continue

        return devices

    def get_mount_point(self, device):
        """获取设备的挂载点"""
        try:
            result = subprocess.run(
                ["mount"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.splitlines():
                if device in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        return parts[2]
        except:
            pass
        return None


class PasswordDialog(QDialog):
    """密码输入对话框"""
    def __init__(self, device_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("USB 存储设备 - 需要授权")
        self.setFixedSize(400, 200)
        self.device_name = device_name
        self.password = None

        layout = QVBoxLayout()

        # 提示信息
        info_label = QLabel(f"挂载 NTFS 设备 {device_name} 需要 sudo 权限")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 密码输入
        pwd_layout = QHBoxLayout()
        pwd_label = QLabel("密码:")
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.Password)
        self.pwd_input.returnPressed.connect(self.accept_password)
        pwd_layout.addWidget(pwd_label)
        pwd_layout.addWidget(self.pwd_input)
        layout.addLayout(pwd_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept_password)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def accept_password(self):
        self.password = self.pwd_input.text()
        self.accept()

    def get_password(self):
        return self.password


class UsbTrayApp(QSystemTrayIcon):
    """USB 存储设备系统托盘应用"""
    def __init__(self, parent=None):
        super().__init__(parent)

        # 设置图标
        self.setup_icon()

        # 设备列表
        self.devices = []
        self.mount_worker = None

        # 创建菜单
        self.create_menu()

        # 连接信号
        self.activated.connect(self.on_tray_activated)

        # 定时扫描
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.scan_devices)
        self.scan_timer.start(5000)  # 每5秒扫描一次

        # 初始扫描
        self.scan_devices()

    def setup_icon(self):
        """设置系统托盘图标"""
        # 创建一个简单的 USB 图标
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)

        from PyQt5.QtGui import QPainter, QColor, QPen
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制 USB 图标
        painter.setPen(QPen(QColor("#4CAF50"), 3))
        painter.setBrush(QColor("#4CAF50"))

        # USB 接口形状
        painter.drawRoundedRect(20, 10, 24, 40, 5, 5)
        painter.drawRect(26, 50, 12, 8)

        painter.end()

        self.setIcon(QIcon(pixmap))
        self.setToolTip("Droidspaces USB 存储设备管理")

    def create_menu(self):
        """创建右键菜单"""
        menu = QMenu()

        # 标题
        title_action = QAction("Droidspaces USB 存储设备", menu)
        title_action.setEnabled(False)
        menu.addAction(title_action)

        menu.addSeparator()

        # 设备列表
        self.device_actions = []
        self.device_menu = menu.addMenu("检测到的设备")

        menu.addSeparator()

        # 刷新按钮
        refresh_action = QAction("刷新设备列表", menu)
        refresh_action.triggered.connect(self.scan_devices)
        menu.addAction(refresh_action)

        # 打开挂载点
        open_mount_action = QAction("打开挂载目录", menu)
        open_mount_action.triggered.connect(self.open_mount_point)
        menu.addAction(open_mount_action)

        menu.addSeparator()

        # 退出
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def scan_devices(self):
        """扫描 USB 设备"""
        self.scan_worker = ScanWorker()
        self.scan_worker.finished.connect(self.update_devices)
        self.scan_worker.start()

    def update_devices(self, devices):
        """更新设备列表"""
        self.devices = devices

        # 清空旧的设备菜单
        self.device_menu.clear()

        if not devices:
            no_device = QAction("未检测到 USB 设备", self.device_menu)
            no_device.setEnabled(False)
            self.device_menu.addAction(no_device)
            return

        for device in devices:
            # 设备主菜单
            dev_menu = self.device_menu.addMenu(
                f"{device['model']} ({device['size_gb']}GB)"
            )

            # 设备信息
            info_action = QAction(f"设备: {device['node']}", dev_menu)
            info_action.setEnabled(False)
            dev_menu.addAction(info_action)

            dev_menu.addSeparator()

            # 分区列表
            for part in device['partitions']:
                if part['mounted']:
                    part_action = QAction(
                        f"{part['name']} ({part['size_gb']}GB) [已挂载]",
                        dev_menu
                    )
                    part_action.triggered.connect(
                        lambda checked, p=part: self.open_mount_point(p['mount_point'])
                    )
                else:
                    part_action = QAction(
                        f"{part['name']} ({part['size_gb']}GB) [点击挂载]",
                        dev_menu
                    )
                    part_action.triggered.connect(
                        lambda checked, p=part: self.mount_partition(p)
                    )
                dev_menu.addAction(part_action)

    def mount_partition(self, partition):
        """挂载分区"""
        # 检查是否需要 sudo（NTFS 需要）
        fs_type = self.get_fs_type(partition['node'])

        if fs_type in ['ntfs', 'ntfs3']:
            # NTFS 需要密码
            dialog = PasswordDialog(partition['name'], None)
            if dialog.exec_() != QDialog.Accepted:
                return

            password = dialog.get_password()
            if not password:
                return

            # 使用 sudo 挂载
            self.mount_with_sudo(partition['node'], password)
        else:
            # 其他文件系统直接挂载
            self.mount_direct(partition['node'])

    def get_fs_type(self, device):
        """获取文件系统类型"""
        try:
            result = subprocess.run(
                ["blkid", "-s", "TYPE", "-o", "value", device],
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except:
            return None

    def mount_with_sudo(self, device, password):
        """使用 sudo 挂载设备"""
        mount_point = os.path.expanduser("~/USB-Storage")

        # 创建挂载点
        os.makedirs(mount_point, exist_ok=True)

        # 构建挂载命令
        cmd = f"echo '{password}' | sudo -S mount -t ntfs-3g -o rw,no_def_opts,allow_other,umask=000 {device} {mount_point}"

        try:
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                self.showMessage(
                    "挂载成功",
                    f"已将 {device} 挂载到 {mount_point}",
                    QSystemTrayIcon.Information,
                    3000
                )
                # 打开文件管理器
                self.open_mount_point(mount_point)
            else:
                QMessageBox.warning(
                    None,
                    "挂载失败",
                    f"无法挂载设备:\n{result.stderr}"
                )
        except Exception as e:
            QMessageBox.warning(
                None,
                "错误",
                f"挂载过程中出错:\n{str(e)}"
            )

    def mount_direct(self, device):
        """直接挂载（不需要 sudo）"""
        mount_point = os.path.expanduser("~/USB-Storage")

        # 创建挂载点
        os.makedirs(mount_point, exist_ok=True)

        try:
            result = subprocess.run(
                ["sudo", "-n", "mount", device, mount_point],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                self.showMessage(
                    "挂载成功",
                    f"已将 {device} 挂载到 {mount_point}",
                    QSystemTrayIcon.Information,
                    3000
                )
                self.open_mount_point(mount_point)
            else:
                QMessageBox.warning(
                    None,
                    "挂载失败",
                    f"无法挂载设备:\n{result.stderr}"
                )
        except Exception as e:
            QMessageBox.warning(
                None,
                "错误",
                f"挂载过程中出错:\n{str(e)}"
            )

    def open_mount_point(self, path=None):
        """打开挂载点目录"""
        if path is None:
            path = os.path.expanduser("~/USB-Storage")

        if os.path.exists(path):
            subprocess.Popen(["xdg-open", path])
        else:
            QMessageBox.information(
                None,
                "提示",
                f"挂载点 {path} 不存在"
            )

    def on_tray_activated(self, reason):
        """托盘图标被点击"""
        if reason == QSystemTrayIcon.Trigger:
            # 单击显示设备信息
            if self.devices:
                device_info = "检测到的 USB 设备:\n\n"
                for dev in self.devices:
                    device_info += f"{dev['model']} ({dev['size_gb']}GB)\n"
                    for part in dev['partitions']:
                        status = "已挂载" if part['mounted'] else "未挂载"
                        device_info += f"  {part['name']} ({part['size_gb']}GB) [{status}]\n"
                    device_info += "\n"

                QMessageBox.information(None, "USB 设备信息", device_info)
            else:
                QMessageBox.information(None, "USB 设备信息", "未检测到 USB 设备")


def main():
    # 检查依赖
    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        print("错误: 需要安装 PyQt5")
        print("请运行: pip install PyQt5")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 创建系统托盘
    tray = UsbTrayApp()
    tray.show()

    # 显示启动通知
    tray.showMessage(
        "USB 存储设备管理",
        "程序已启动，正在监控 USB 设备...",
        QSystemTrayIcon.Information,
        2000
    )

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
