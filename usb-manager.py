#!/usr/bin/env python3
"""
Droidspaces USB Storage Manager
带系统托盘和主窗口的 USB 存储设备管理工具
自动检测、挂载 USB 存储设备，支持弹出和打开目录
"""

import sys
import os
import subprocess
import fcntl
from pathlib import Path

# 强制使用 X11 后端（避免 Wayland 问题）
if os.environ.get('QT_QPA_PLATFORM') == 'wayland':
    os.environ['QT_QPA_PLATFORM'] = 'xcb'

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QStatusBar, QStyle, QSystemTrayIcon, QMenu, QAction,
    QSpinBox
)
from PyQt5.QtGui import QIcon, QColor, QFont
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal

# 单实例锁文件路径
LOCK_FILE = "/tmp/usb-manager.lock"
# 挂载点基础目录
MOUNT_BASE = os.path.expanduser("~/USB-Storage")


def get_usb_icon():
    """获取 KDE 自带的 USB 图标"""
    for theme_name in ["drive-removable-media-usb", "drive-removable-media", "generic-usb"]:
        icon = QIcon.fromTheme(theme_name)
        if not icon.isNull():
            return icon
    return QApplication.style().standardIcon(QStyle.SP_DriveFDIcon)


class ScanWorker(QThread):
    """后台扫描 USB 设备的线程"""
    finished = pyqtSignal(list, list)

    def run(self):
        storage_devices = self.scan_usb_devices()
        adb_devices = self.scan_adb_devices()
        self.finished.emit(storage_devices, adb_devices)

    def create_device_node(self, node, major, minor):
        """创建设备节点"""
        if not os.path.exists(node):
            try:
                subprocess.run(
                    ["sudo", "-n", "/usr/bin/mknod", "-m", "666", node, "b", major, minor],
                    capture_output=True
                )
                subprocess.run(
                    ["sudo", "-n", "/usr/bin/chmod", "666", node],
                    capture_output=True
                )
                return os.path.exists(node)
            except:
                return False
        return True

    def scan_adb_devices(self):
        """扫描 ADB 设备（排除 USB 存储设备）"""
        devices = []
        usb_base = Path("/sys/bus/usb/devices")

        if not usb_base.exists():
            return devices

        # 先收集所有 USB 存储设备的 USB 路径
        storage_usb_paths = set()
        scsi_base = Path("/sys/bus/scsi/devices")
        if scsi_base.exists():
            for scsi_dev in scsi_base.iterdir():
                real_path = str(scsi_dev.resolve())
                if "usb" in real_path:
                    # 提取 USB 设备路径（如 usb2/2-1）
                    parts = real_path.split('/')
                    for i, part in enumerate(parts):
                        if part.startswith('usb') and i + 1 < len(parts):
                            storage_usb_paths.add(parts[i + 1])

        for usb_dev in usb_base.iterdir():
            # 只扫描设备，跳过接口（格式：bus-port:interface）
            dev_name = usb_dev.name
            if ':' in dev_name:
                continue
            if dev_name.startswith('usb'):
                continue

            # 排除 USB 存储设备
            if dev_name in storage_usb_paths:
                continue

            # 检查是否有设备描述文件
            product_file = usb_dev / "product"
            vendor_file = usb_dev / "idVendor"
            product_id_file = usb_dev / "idProduct"

            if not vendor_file.exists() or not product_id_file.exists():
                continue

            try:
                vendor_id = vendor_file.read_text().strip()
                product_id = product_id_file.read_text().strip()
                product = product_file.read_text().strip() if product_file.exists() else "Unknown"

                devnum_file = usb_dev / "devnum"
                busnum_file = usb_dev / "busnum"

                if not devnum_file.exists() or not busnum_file.exists():
                    continue

                devnum = devnum_file.read_text().strip()
                busnum = busnum_file.read_text().strip()

                # 构建设备节点路径
                node_path = f"/dev/bus/usb/{busnum.zfill(3)}/{devnum.zfill(3)}"

                # 检查设备类
                devclass_file = usb_dev / "bDeviceClass"
                devclass = devclass_file.read_text().strip() if devclass_file.exists() else "00"

                device_info = {
                    "type": "adb",
                    "name": product,
                    "node": node_path,
                    "vendor_id": vendor_id,
                    "product_id": product_id,
                    "busnum": busnum,
                    "devnum": devnum,
                    "devclass": devclass,
                    "exists": os.path.exists(node_path)
                }

                devices.append(device_info)

            except Exception as e:
                print(f"Error reading USB device {usb_dev}: {e}")
                continue

        return devices

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

            # 检查是否是 USB 设备
            real_path = str(scsi_dev.resolve())
            if "usb" not in real_path:
                continue

            for block_dev in block_dir.iterdir():
                if not block_dev.is_dir():
                    continue

                dev_file = block_dev / "dev"
                if not dev_file.exists():
                    continue

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

                    device_info = {
                        "name": block_name,
                        "node": node_path,
                        "major": major,
                        "minor": minor,
                        "vendor": vendor,
                        "model": model,
                        "size_gb": size_gb,
                        "partitions": []
                    }

                    # 扫描分区
                    for item in block_dev.iterdir():
                        if not item.is_dir() or item == block_dev:
                            continue
                        # 检查是否是分区目录（有 dev 文件）
                        part_dev_file = item / "dev"
                        if not part_dev_file.exists():
                            continue

                        part_major_minor = part_dev_file.read_text().strip()
                        part_major, part_minor = part_major_minor.split(":")

                        part_name = item.name
                        part_node = f"/dev/{part_name}"

                        # 自动创建设备节点
                        self.create_device_node(part_node, part_major, part_minor)

                        part_size_file = item / "size"
                        part_size_sectors = int(part_size_file.read_text().strip()) if part_size_file.exists() else 0
                        part_size_gb = part_size_sectors * 512 // 1073741824

                        fs_type = self.get_fs_type(part_node)
                        mounted_at = self.get_mount_point(part_node)

                        device_info["partitions"].append({
                            "name": part_name,
                            "node": part_node,
                            "major": part_major,
                            "minor": part_minor,
                            "size_gb": part_size_gb,
                            "fs_type": fs_type,
                            "mounted": mounted_at is not None,
                            "mount_point": mounted_at
                        })

                    devices.append(device_info)

                except Exception as e:
                    print(f"Error reading device {block_dev}: {e}")
                    continue

        return devices

    def get_mount_point(self, device):
        """获取设备的挂载点"""
        try:
            result = subprocess.run(["mount"], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if device in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        return parts[2]
        except:
            pass
        return None

    def get_fs_type(self, device):
        """获取文件系统类型"""
        if not os.path.exists(device):
            return None
        try:
            result = subprocess.run(
                ["sudo", "-n", "/usr/sbin/blkid", "-s", "TYPE", "-o", "value", device],
                capture_output=True, text=True
            )
            return result.stdout.strip() or None
        except:
            return None


class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self, tray_icon=None):
        super().__init__()
        self.tray_icon = tray_icon
        self.setWindowTitle("Droidspaces USB 管理器")
        self.setMinimumSize(750, 450)
        self.setWindowIcon(get_usb_icon())

        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("USB 管理器")
        title.setFont(QFont("", 16, QFont.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()

        refresh_btn = QPushButton("刷新")
        refresh_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        refresh_btn.clicked.connect(self.resume_and_scan)
        title_layout.addWidget(refresh_btn)

        # 暂停/恢复扫描按钮
        self.pause_btn = QPushButton("暂停扫描")
        self.pause_btn.clicked.connect(self.toggle_scan)
        title_layout.addWidget(self.pause_btn)

        # 刷新时长设置
        title_layout.addWidget(QLabel("刷新间隔:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(3)
        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.valueChanged.connect(self.update_scan_interval)
        title_layout.addWidget(self.interval_spin)

        layout.addLayout(title_layout)

        # 设备树
        self.device_tree = QTreeWidget()
        self.device_tree.setHeaderLabels(["设备", "大小", "文件系统", "状态", "操作"])
        self.device_tree.setColumnWidth(0, 220)
        self.device_tree.setColumnWidth(1, 80)
        self.device_tree.setColumnWidth(2, 80)
        self.device_tree.setColumnWidth(3, 100)
        self.device_tree.setColumnWidth(4, 200)
        self.device_tree.setAlternatingRowColors(True)
        self.device_tree.setRootIsDecorated(True)
        layout.addWidget(self.device_tree)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        # 存储设备列表（用于自动挂载检测）
        self.known_devices = set()

        # 扫描状态
        self.scan_paused = False

        # 定时扫描
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.scan_devices)
        self.scan_timer.start(3000)

        # 初始扫描
        self.scan_devices()

    def scan_devices(self):
        """扫描 USB 设备"""
        if self.scan_paused:
            return
        self.scan_worker = ScanWorker()
        self.scan_worker.finished.connect(self.update_device_tree)
        self.scan_worker.start()

    def resume_and_scan(self):
        """恢复扫描并立即扫描"""
        self.scan_paused = False
        self.pause_btn.setText("暂停扫描")
        self.status_bar.showMessage("已恢复自动扫描")
        self.scan_devices()

    def toggle_scan(self):
        """切换扫描状态"""
        if self.scan_paused:
            self.resume_and_scan()
        else:
            self.scan_paused = True
            self.pause_btn.setText("恢复扫描")
            self.status_bar.showMessage("自动扫描已暂停")

    def update_scan_interval(self, value):
        """更新扫描间隔"""
        self.scan_timer.setInterval(value * 1000)

    def refresh_ui(self):
        """手动刷新界面（不触发自动扫描）"""
        # 重新扫描设备信息但不触发自动挂载
        self.refresh_worker = ScanWorker()
        self.refresh_worker.finished.connect(self.update_device_tree)
        self.refresh_worker.start()

    def update_device_tree(self, storage_devices, adb_devices):
        """更新设备树并自动挂载新设备"""
        self.device_tree.clear()

        total_storage = 0
        total_adb = 0
        mounted = 0
        current_devices = set()

        # 显示 USB 存储设备
        for device in storage_devices:
            total_storage += 1
            current_devices.add(device['node'])

            # 设备根节点
            dev_item = QTreeWidgetItem(self.device_tree)
            dev_item.setText(0, f"{device['model']} ({device['vendor']})")
            dev_item.setText(1, f"{device['size_gb']} GB")
            dev_item.setText(2, "")
            dev_item.setText(3, "已连接")
            dev_item.setIcon(0, self.style().standardIcon(QStyle.SP_ComputerIcon))
            dev_item.setExpanded(True)

            # 分区
            for part in device['partitions']:
                current_devices.add(part['node'])

                part_item = QTreeWidgetItem(dev_item)
                part_item.setText(0, part['name'])
                part_item.setText(1, f"{part['size_gb']} GB")
                part_item.setText(2, part.get('fs_type', '') or '未知')

                if part['mounted']:
                    part_item.setText(3, "已挂载")
                    part_item.setForeground(3, QColor("#4CAF50"))
                    mounted += 1

                    # 操作按钮容器
                    btn_widget = QWidget()
                    btn_layout = QHBoxLayout(btn_widget)
                    btn_layout.setContentsMargins(2, 2, 2, 2)

                    open_btn = QPushButton("打开目录")
                    open_btn.clicked.connect(lambda checked, mp=part['mount_point']: self.open_directory(mp))
                    btn_layout.addWidget(open_btn)

                    eject_btn = QPushButton("弹出")
                    eject_btn.clicked.connect(lambda checked, p=part: self.eject_device(p))
                    btn_layout.addWidget(eject_btn)

                    self.device_tree.setItemWidget(part_item, 4, btn_widget)
                else:
                    part_item.setText(3, "未挂载")
                    part_item.setForeground(3, QColor("#FF9800"))

                    # 自动挂载新设备
                    if part['node'] not in self.known_devices:
                        self.auto_mount(part)
                    else:
                        # 显示挂载按钮
                        mount_btn = QPushButton("挂载")
                        mount_btn.clicked.connect(lambda checked, p=part: self.mount_partition(p))
                        self.device_tree.setItemWidget(part_item, 4, mount_btn)

        # 显示 ADB 设备
        for device in adb_devices:
            total_adb += 1

            # 检查设备节点是否存在
            busnum = device['busnum'].zfill(3)
            devnum = device['devnum'].zfill(3)
            node_path = f"/dev/bus/usb/{busnum}/{devnum}"
            device['node'] = node_path
            device['exists'] = os.path.exists(node_path)

            # 如果节点不存在，自动运行脚本创建
            if not device['exists']:
                self.auto_connect_adb(device)
                device['exists'] = os.path.exists(node_path)

            dev_item = QTreeWidgetItem(self.device_tree)
            dev_item.setText(0, f"{device['name']} [ADB]")
            dev_item.setText(1, f"{device['vendor_id']}:{device['product_id']}")
            dev_item.setText(2, f"USB {device['devclass']}")

            if device['exists']:
                dev_item.setText(3, "已连接")
                dev_item.setForeground(3, QColor("#4CAF50"))
            else:
                dev_item.setText(3, "未连接")
                dev_item.setForeground(3, QColor("#FF9800"))

                # 连接按钮
                btn_widget = QWidget()
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(2, 2, 2, 2)

                connect_btn = QPushButton("连接")
                connect_btn.clicked.connect(lambda checked, d=device: self.connect_adb(d))
                btn_layout.addWidget(connect_btn)

                self.device_tree.setItemWidget(dev_item, 4, btn_widget)

        # 更新已知设备列表
        self.known_devices = current_devices

        # 更新状态栏
        status_parts = []
        if total_storage > 0:
            status_parts.append(f"{total_storage} 个存储设备")
        if total_adb > 0:
            status_parts.append(f"{total_adb} 个 ADB 设备")
        if mounted > 0:
            status_parts.append(f"{mounted} 个分区已挂载")

        if status_parts:
            status = "检测到 " + "，".join(status_parts)
        else:
            status = "未检测到 USB 设备"

        self.status_bar.showMessage(status)
        if self.tray_icon:
            self.tray_icon.setToolTip(f"USB 设备管理\n{status}")

    def create_device_node(self, node, major, minor):
        """创建设备节点"""
        if not os.path.exists(node):
            try:
                subprocess.run(
                    ["sudo", "-n", "/usr/bin/mknod", "-m", "666", node, "b", major, minor],
                    capture_output=True
                )
                subprocess.run(
                    ["sudo", "-n", "/usr/bin/chmod", "666", node],
                    capture_output=True
                )
                return os.path.exists(node)
            except:
                return False
        return True

    def create_adb_node(self, device):
        """创建 ADB 设备节点"""
        busnum = device['busnum'].zfill(3)
        devnum = device['devnum'].zfill(3)
        node_dir = f"/dev/bus/usb/{busnum}"
        node_path = f"/dev/bus/usb/{busnum}/{devnum}"

        try:
            # 创建目录
            subprocess.run(["sudo", "-n", "/usr/bin/mkdir", "-p", node_dir], capture_output=True)
            # 创建字符设备节点（major=188 是 USB 字符设备）
            subprocess.run(
                ["sudo", "-n", "/usr/bin/mknod", "-m", "666", node_path, "c", "188", f"{int(busnum)*128+int(devnum)}"],
                capture_output=True
            )
            subprocess.run(["sudo", "-n", "/usr/bin/chmod", "666", node_path], capture_output=True)

            self.status_bar.showMessage(f"已创建 ADB 设备节点 {node_path}")
            self.scan_devices()  # 刷新界面
        except Exception as e:
            QMessageBox.warning(self, "错误", f"创建 ADB 设备节点失败:\n{str(e)}")

    def connect_adb(self, device):
        """连接 ADB 设备（运行 usb-passthrough.sh）"""
        script_path = os.path.join(os.path.dirname(__file__), "usb-passthrough.sh")
        if not os.path.exists(script_path):
            QMessageBox.warning(self, "错误", f"找不到脚本: {script_path}")
            return

        try:
            # 运行脚本创建设备节点
            result = subprocess.run(
                ["sudo", "-n", "bash", script_path],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.status_bar.showMessage(f"ADB 设备已连接")
                self.scan_devices()  # 刷新界面
            else:
                QMessageBox.warning(self, "连接失败", f"无法连接 ADB 设备:\n{result.stderr}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"连接 ADB 设备出错:\n{str(e)}")

    def auto_connect_adb(self, device):
        """自动连接 ADB 设备（静默运行）"""
        script_path = os.path.join(os.path.dirname(__file__), "usb-passthrough.sh")
        if not os.path.exists(script_path):
            return

        try:
            # 静默运行脚本创建设备节点
            subprocess.run(
                ["sudo", "-n", "bash", script_path],
                capture_output=True, text=True
            )
        except:
            pass

    def auto_mount(self, partition):
        """自动挂载分区"""
        node = partition['node']
        major = partition['major']
        minor = partition['minor']
        fs_type = partition.get('fs_type', '')

        # 创建设备节点
        self.create_device_node(node, major, minor)

        if not os.path.exists(node):
            return

        # 创建挂载点
        mount_point = MOUNT_BASE
        os.makedirs(mount_point, exist_ok=True)

        # 根据文件系统类型选择挂载选项
        if fs_type in ['ntfs', 'ntfs3']:
            # NTFS 需要 sudo
            cmd = f"sudo -n /usr/bin/mount -t ntfs-3g -o rw,no_def_opts,allow_other,umask=000 {node} {mount_point}"
        elif fs_type == 'exfat':
            cmd = f"sudo -n /usr/bin/mount -t exfat -o rw,uid={os.getuid()},gid={os.getgid()},umask=000 {node} {mount_point}"
        elif fs_type in ['vfat', 'fat32']:
            cmd = f"sudo -n /usr/bin/mount -t vfat -o rw,uid={os.getuid()},gid={os.getgid()},umask=000 {node} {mount_point}"
        else:
            cmd = f"sudo -n /usr/bin/mount {node} {mount_point}"

        try:
            result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
            if result.returncode == 0:
                self.status_bar.showMessage(f"已自动挂载 {node} 到 {mount_point}")
                self.scan_devices()  # 刷新列表
                # 发送通知
                if self.tray_icon:
                    self.tray_icon.showMessage(
                        "USB 设备已挂载",
                        f"{partition['name']} 已挂载到 {mount_point}",
                        QSystemTrayIcon.Information,
                        3000
                    )
            else:
                # 自动挂载失败，可能是 NTFS 需要密码
                print(f"Auto mount failed: {result.stderr}")
        except Exception as e:
            print(f"Auto mount error: {e}")

    def mount_partition(self, partition):
        """手动挂载分区"""
        node = partition['node']
        major = partition['major']
        minor = partition['minor']

        # 创建设备节点
        self.create_device_node(node, major, minor)

        if not os.path.exists(node):
            QMessageBox.warning(self, "错误", f"设备节点 {node} 不存在")
            return

        mount_point = MOUNT_BASE
        os.makedirs(mount_point, exist_ok=True)

        fs_type = partition.get('fs_type', '')
        if fs_type in ['ntfs', 'ntfs3']:
            cmd = f"sudo -n /usr/bin/mount -t ntfs-3g -o rw,no_def_opts,allow_other,umask=000 {node} {mount_point}"
        else:
            cmd = f"sudo -n /usr/bin/mount {node} {mount_point}"

        try:
            result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
            if result.returncode == 0:
                # 设置挂载点权限
                subprocess.run(["sudo", "-n", "/usr/bin/chmod", "-R", "777", mount_point])
                self.status_bar.showMessage(f"已挂载 {node} 到 {mount_point}")
                # 恢复扫描并刷新界面
                self.scan_paused = False
                self.scan_devices()
            else:
                QMessageBox.warning(self, "挂载失败", f"无法挂载设备:\n{result.stderr}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"挂载过程中出错:\n{str(e)}")

    def eject_device(self, partition):
        """弹出设备"""
        node = partition['node']
        mount_point = partition.get('mount_point')

        if mount_point:
            try:
                # 先卸载
                result = subprocess.run(
                    ["sudo", "-n", "/usr/bin/umount", mount_point],
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    QMessageBox.warning(self, "弹出失败", f"无法卸载:\n{result.stderr}")
                    return
            except Exception as e:
                QMessageBox.warning(self, "错误", f"卸载出错:\n{str(e)}")
                return

        # 暂停自动扫描
        self.scan_paused = True

        # 从已知设备中移除
        self.known_devices.discard(node)

        self.status_bar.showMessage(f"已弹出 {node} - 自动扫描已暂停，点击 刷新 恢复")
        if self.tray_icon:
            self.tray_icon.showMessage(
                "USB 设备已弹出",
                f"{partition['name']} 可以安全移除\n自动扫描已暂停",
                QSystemTrayIcon.Information,
                3000
            )
        # 手动刷新界面（因为扫描已暂停）
        self.refresh_ui()

    def open_directory(self, path):
        """打开目录"""
        if os.path.exists(path):
            if os.access(path, os.R_OK):
                subprocess.Popen(["dolphin", path])
            else:
                # 使用 pkexec 并传递环境变量
                env = os.environ.copy()
                subprocess.Popen(
                    ["pkexec", "env",
                     f"DISPLAY={env.get('DISPLAY', '')}",
                     f"WAYLAND_DISPLAY={env.get('WAYLAND_DISPLAY', '')}",
                     f"XDG_RUNTIME_DIR={env.get('XDG_RUNTIME_DIR', '')}",
                     "dolphin", path],
                    env=env
                )
        else:
            QMessageBox.information(self, "提示", f"目录 {path} 不存在")


class UsbTrayIcon(QSystemTrayIcon):
    """系统托盘图标"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIcon(get_usb_icon())
        self.setToolTip("USB 存储设备管理")

        # 先创建主窗口
        self.main_window = MainWindow(self)

        # 创建菜单
        self.create_menu()

        # 连接信号
        self.activated.connect(self.on_activated)

    def create_menu(self):
        """创建右键菜单"""
        menu = QMenu()

        show_action = QAction("显示主窗口", menu)
        show_action.triggered.connect(self.show_main_window)
        menu.addAction(show_action)

        menu.addSeparator()

        refresh_action = QAction("刷新设备", menu)
        refresh_action.triggered.connect(self.main_window.scan_devices)
        menu.addAction(refresh_action)

        menu.addSeparator()

        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def show_main_window(self):
        """显示主窗口"""
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def on_activated(self, reason):
        """托盘图标被点击"""
        if reason == QSystemTrayIcon.Trigger:
            self.show_main_window()


def main():
    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        print("错误: 需要安装 PyQt5")
        print("请运行: sudo apt install python3-pyqt5")
        sys.exit(1)

    # 单实例检查（使用文件锁）
    lock_file = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
    except (IOError, OSError):
        print("USB 管理器已在运行中")
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")

    tray = UsbTrayIcon()
    tray.show()
    tray.main_window.show()

    ret = app.exec_()

    # 清理
    fcntl.flock(lock_file, fcntl.LOCK_UN)
    lock_file.close()
    try:
        os.unlink(LOCK_FILE)
    except:
        pass

    sys.exit(ret)


if __name__ == "__main__":
    main()
