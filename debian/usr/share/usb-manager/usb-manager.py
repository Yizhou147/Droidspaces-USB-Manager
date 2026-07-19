#!/usr/bin/env python3
"""
Droidspaces USB Manager
自动检测、挂载 USB 存储设备，支持弹出和打开目录
"""

import sys
import os
import subprocess
import fcntl
import locale
import json
from pathlib import Path

# 强制使用 X11 后端（避免 Wayland 问题）
if os.environ.get('QT_QPA_PLATFORM') == 'wayland':
    os.environ['QT_QPA_PLATFORM'] = 'xcb'

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QStatusBar, QStyle, QSystemTrayIcon, QMenu, QAction,
    QSpinBox, QComboBox, QDialog
)
from PyQt5.QtGui import QIcon, QColor, QFont
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal

# 单实例锁文件路径
LOCK_FILE = "/tmp/usb-manager.lock"
# 挂载点基础目录
MOUNT_BASE = os.path.expanduser("~/USB-Storage")
# 配置文件路径
CONFIG_FILE = os.path.expanduser("~/.config/usb-manager/config.json")

# ==================== 翻译 ====================
TRANSLATIONS = {
    "zh": {
        "window_title": "Droidspaces USB 管理器",
        "title": "USB 管理器",
        "refresh": "刷新",
        "pause_scan": "暂停扫描",
        "resume_scan": "恢复扫描",
        "interval_label": "刷新间隔:",
        "interval_suffix": " 秒",
        "col_device": "设备",
        "col_size": "大小",
        "col_fs": "文件系统",
        "col_status": "状态",
        "col_action": "操作",
        "ready": "就绪",
        "connected": "已连接",
        "disconnected": "未连接",
        "mounted": "已挂载",
        "unmounted": "未挂载",
        "unknown": "未知",
        "open_dir": "打开目录",
        "eject": "弹出",
        "mount": "挂载",
        "connect": "连接",
        "scan_resumed": "已恢复自动扫描",
        "scan_paused": "自动扫描已暂停",
        "eject_status": "已弹出 {} - 自动扫描已暂停，点击 刷新 恢复",
        "mount_status": "已挂载 {} 到 {}",
        "auto_mount_status": "已自动挂载 {} 到 {}",
        "adb_connected": "ADB 设备已连接",
        "adb_node_created": "已创建 ADB 设备节点 {}",
        "status_storage": "{} 个存储设备",
        "status_adb": "{} 个 ADB 设备",
        "status_mounted": "{} 个分区已挂载",
        "status_detected": "检测到 {}",
        "status_no_device": "未检测到 USB 设备",
        "tray_tip": "USB 设备管理",
        "tray_show": "显示主窗口",
        "tray_refresh": "刷新设备",
        "tray_quit": "退出",
        "notify_mount_title": "USB 设备已挂载",
        "notify_mount_msg": "{} 已挂载到 {}",
        "notify_eject_title": "USB 设备已弹出",
        "notify_eject_msg": "{} 可以安全移除\n自动扫描已暂停",
        "err_node_missing": "设备节点 {} 不存在",
        "err_mount_failed": "无法挂载设备:\n{}",
        "err_mount_error": "挂载过程中出错:\n{}",
        "err_eject_failed": "无法卸载:\n{}",
        "err_eject_error": "卸载出错:\n{}",
        "err_dir_missing": "目录 {} 不存在",
        "err_script_missing": "找不到脚本: {}",
        "err_adb_connect": "无法连接 ADB 设备:\n{}",
        "err_adb_error": "连接 ADB 设备出错:\n{}",
        "err_adb_node_failed": "创建 ADB 设备节点失败:\n{}",
        "err_adb_connect_title": "连接失败",
        "err_title": "错误",
        "err_eject_title": "弹出失败",
        "info_title": "提示",
        "already_running": "USB 管理器已在运行中",
        "err_pyqt5": "错误: 需要安装 PyQt5\n请运行: sudo apt install python3-pyqt5",
        "lang_label": "语言:",
        "lang_zh": "中文",
        "lang_en": "English",
        "settings_label": "设置",
        "about": "关于",
        "about_title": "关于",
        "about_version": "版本",
        "about_author": "作者",
        "about_project": "项目地址",
        "about_license": "许可证",
        "about_description": "自动检测、挂载 USB 存储设备\n支持弹出和打开目录",
    },
    "en": {
        "window_title": "Droidspaces USB Manager",
        "title": "USB Manager",
        "refresh": "Refresh",
        "pause_scan": "Pause Scan",
        "resume_scan": "Resume Scan",
        "interval_label": "Interval:",
        "interval_suffix": " s",
        "col_device": "Device",
        "col_size": "Size",
        "col_fs": "Filesystem",
        "col_status": "Status",
        "col_action": "Action",
        "ready": "Ready",
        "connected": "Connected",
        "disconnected": "Disconnected",
        "mounted": "Mounted",
        "unmounted": "Unmounted",
        "unknown": "Unknown",
        "open_dir": "Open Dir",
        "eject": "Eject",
        "mount": "Mount",
        "connect": "Connect",
        "scan_resumed": "Auto scan resumed",
        "scan_paused": "Auto scan paused",
        "eject_status": "Ejected {} - Auto scan paused, click Refresh to resume",
        "mount_status": "Mounted {} at {}",
        "auto_mount_status": "Auto mounted {} at {}",
        "adb_connected": "ADB device connected",
        "adb_node_created": "ADB device node {} created",
        "status_storage": "{} storage device(s)",
        "status_adb": "{} ADB device(s)",
        "status_mounted": "{} partition(s) mounted",
        "status_detected": "Detected {}",
        "status_no_device": "No USB device detected",
        "tray_tip": "USB Device Manager",
        "tray_show": "Show Window",
        "tray_refresh": "Refresh Devices",
        "tray_quit": "Quit",
        "notify_mount_title": "USB Device Mounted",
        "notify_mount_msg": "{} mounted at {}",
        "notify_eject_title": "USB Device Ejected",
        "notify_eject_msg": "{} can be safely removed\nAuto scan paused",
        "err_node_missing": "Device node {} does not exist",
        "err_mount_failed": "Cannot mount device:\n{}",
        "err_mount_error": "Mount error:\n{}",
        "err_eject_failed": "Cannot unmount:\n{}",
        "err_eject_error": "Unmount error:\n{}",
        "err_dir_missing": "Directory {} does not exist",
        "err_script_missing": "Script not found: {}",
        "err_adb_connect": "Cannot connect ADB device:\n{}",
        "err_adb_error": "ADB connect error:\n{}",
        "err_adb_node_failed": "Failed to create ADB device node:\n{}",
        "err_adb_connect_title": "Connect Failed",
        "err_title": "Error",
        "err_eject_title": "Eject Failed",
        "info_title": "Info",
        "already_running": "USB Manager is already running",
        "err_pyqt5": "Error: PyQt5 is required\nRun: sudo apt install python3-pyqt5",
        "lang_label": "Language:",
        "lang_zh": "中文",
        "lang_en": "English",
        "settings_label": "Settings",
        "about": "About",
        "about_title": "About",
        "about_version": "Version",
        "about_author": "Author",
        "about_project": "Project",
        "about_license": "License",
        "about_description": "Auto-detect and mount USB storage devices\nSupport eject and open directory",
    }
}

# 当前语言
_current_lang = "zh"


def detect_system_language():
    """检测系统语言"""
    try:
        lang = locale.getdefaultlocale()[0] or ""
        if lang.startswith("zh"):
            return "zh"
        return "en"
    except:
        return "zh"


def load_config():
    """加载配置"""
    global _current_lang
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                _current_lang = config.get("language", detect_system_language())
                return config
        except:
            pass
    _current_lang = detect_system_language()
    return {"language": _current_lang}


def save_config(config):
    """保存配置"""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except:
        pass


def t(key, *args):
    """翻译函数"""
    text = TRANSLATIONS.get(_current_lang, TRANSLATIONS["zh"]).get(key, key)
    if args:
        return text.format(*args)
    return text


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

        storage_usb_paths = set()
        scsi_base = Path("/sys/bus/scsi/devices")
        if scsi_base.exists():
            for scsi_dev in scsi_base.iterdir():
                real_path = str(scsi_dev.resolve())
                if "usb" in real_path:
                    parts = real_path.split('/')
                    for i, part in enumerate(parts):
                        if part.startswith('usb') and i + 1 < len(parts):
                            storage_usb_paths.add(parts[i + 1])

        for usb_dev in usb_base.iterdir():
            dev_name = usb_dev.name
            if ':' in dev_name:
                continue
            if dev_name.startswith('usb'):
                continue
            if dev_name in storage_usb_paths:
                continue

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

                node_path = f"/dev/bus/usb/{busnum.zfill(3)}/{devnum.zfill(3)}"

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

                    for item in block_dev.iterdir():
                        if not item.is_dir() or item == block_dev:
                            continue
                        part_dev_file = item / "dev"
                        if not part_dev_file.exists():
                            continue

                        part_major_minor = part_dev_file.read_text().strip()
                        part_major, part_minor = part_major_minor.split(":")

                        part_name = item.name
                        part_node = f"/dev/{part_name}"

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
                if line.startswith(device + " "):
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
        self.setWindowTitle(t("window_title"))
        self.setMinimumSize(1100, 600)
        self.resize(1100, 600)
        self.setWindowIcon(get_usb_icon())

        central = QWidget()
        self.setCentralWidget(central)
        self.layout = QVBoxLayout(central)

        # 标题栏
        self.title_layout = QHBoxLayout()
        self.title_label = QLabel(t("title"))
        self.title_label.setFont(QFont("", 16, QFont.Bold))
        self.title_layout.addWidget(self.title_label)
        self.title_layout.addStretch()

        # 语言切换
        self.lang_label = QLabel(t("lang_label"))
        self.title_layout.addWidget(self.lang_label)
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("中文", "zh")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.setCurrentIndex(0 if _current_lang == "zh" else 1)
        self.lang_combo.currentIndexChanged.connect(self.on_language_changed)
        self.title_layout.addWidget(self.lang_combo)

        self.refresh_btn = QPushButton(t("refresh"))
        self.refresh_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.refresh_btn.clicked.connect(self.resume_and_scan)
        self.title_layout.addWidget(self.refresh_btn)

        self.pause_btn = QPushButton(t("pause_scan"))
        self.pause_btn.clicked.connect(self.toggle_scan)
        self.title_layout.addWidget(self.pause_btn)

        self.interval_label_widget = QLabel(t("interval_label"))
        self.title_layout.addWidget(self.interval_label_widget)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(3)
        self.interval_spin.setSuffix(t("interval_suffix"))
        self.interval_spin.valueChanged.connect(self.update_scan_interval)
        self.title_layout.addWidget(self.interval_spin)

        self.layout.addLayout(self.title_layout)

        # 设备树
        self.device_tree = QTreeWidget()
        self.device_tree.setHeaderLabels([
            t("col_device"), t("col_size"), t("col_fs"), t("col_status"), t("col_action")
        ])
        self.device_tree.setColumnWidth(0, 220)
        self.device_tree.setColumnWidth(1, 80)
        self.device_tree.setColumnWidth(2, 80)
        self.device_tree.setColumnWidth(3, 100)
        self.device_tree.setColumnWidth(4, 200)
        self.device_tree.setAlternatingRowColors(True)
        self.device_tree.setRootIsDecorated(True)
        self.layout.addWidget(self.device_tree)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(t("ready"))

        # 关于按钮（右下角）
        self.about_btn = QPushButton(t("about"))
        self.about_btn.clicked.connect(self.show_about)
        self.status_bar.addPermanentWidget(self.about_btn)
        self.status_bar.setStyleSheet("QStatusBar::item { border: none; }")

        self.known_devices = set()
        self.scan_paused = False

        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.scan_devices)
        self.scan_timer.start(3000)

        self.scan_devices()

    def on_language_changed(self, index):
        """语言切换"""
        global _current_lang
        new_lang = self.lang_combo.itemData(index)
        if new_lang == _current_lang:
            return
        _current_lang = new_lang
        save_config({"language": new_lang})
        self.retranslate_ui()

    def retranslate_ui(self):
        """更新所有 UI 文本"""
        self.setWindowTitle(t("window_title"))
        self.title_label.setText(t("title"))
        self.refresh_btn.setText(t("refresh"))
        self.pause_btn.setText(t("pause_scan") if not self.scan_paused else t("resume_scan"))
        self.interval_label_widget.setText(t("interval_label"))
        self.interval_spin.setSuffix(t("interval_suffix"))
        self.lang_label.setText(t("lang_label"))
        self.about_btn.setText(t("about"))
        self.device_tree.setHeaderLabels([
            t("col_device"), t("col_size"), t("col_fs"), t("col_status"), t("col_action")
        ])
        self.status_bar.showMessage(t("ready"))
        if self.tray_icon:
            self.tray_icon.retranslate_menu()
        # 刷新设备树
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
        self.pause_btn.setText(t("pause_scan"))
        self.status_bar.showMessage(t("scan_resumed"))
        self.scan_devices()

    def toggle_scan(self):
        """切换扫描状态"""
        if self.scan_paused:
            self.resume_and_scan()
        else:
            self.scan_paused = True
            self.pause_btn.setText(t("resume_scan"))
            self.status_bar.showMessage(t("scan_paused"))

    def update_scan_interval(self, value):
        """更新扫描间隔"""
        self.scan_timer.setInterval(value * 1000)

    def refresh_ui(self):
        """手动刷新界面（不触发自动扫描）"""
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

        for device in storage_devices:
            total_storage += 1
            current_devices.add(device['node'])

            dev_item = QTreeWidgetItem(self.device_tree)
            dev_item.setText(0, f"{device['model']} ({device['vendor']})")
            dev_item.setText(1, f"{device['size_gb']} GB")
            dev_item.setText(2, "")
            dev_item.setText(3, t("connected"))
            dev_item.setIcon(0, self.style().standardIcon(QStyle.SP_ComputerIcon))
            dev_item.setExpanded(True)

            for part in device['partitions']:
                current_devices.add(part['node'])

                part_item = QTreeWidgetItem(dev_item)
                part_item.setText(0, part['name'])
                part_item.setText(1, f"{part['size_gb']} GB")
                part_item.setText(2, part.get('fs_type', '') or t("unknown"))

                if part['mounted']:
                    part_item.setText(3, t("mounted"))
                    part_item.setForeground(3, QColor("#4CAF50"))
                    mounted += 1

                    btn_widget = QWidget()
                    btn_layout = QHBoxLayout(btn_widget)
                    btn_layout.setContentsMargins(2, 2, 2, 2)

                    open_btn = QPushButton(t("open_dir"))
                    open_btn.clicked.connect(lambda checked, mp=part['mount_point']: self.open_directory(mp))
                    btn_layout.addWidget(open_btn)

                    eject_btn = QPushButton(t("eject"))
                    eject_btn.clicked.connect(lambda checked, p=part: self.eject_device(p))
                    btn_layout.addWidget(eject_btn)

                    self.device_tree.setItemWidget(part_item, 4, btn_widget)
                else:
                    part_item.setText(3, t("unmounted"))
                    part_item.setForeground(3, QColor("#FF9800"))

                    if part['node'] not in self.known_devices:
                        self.auto_mount(part)
                    else:
                        mount_btn = QPushButton(t("mount"))
                        mount_btn.clicked.connect(lambda checked, p=part: self.mount_partition(p))
                        self.device_tree.setItemWidget(part_item, 4, mount_btn)

        for device in adb_devices:
            total_adb += 1

            busnum = device['busnum'].zfill(3)
            devnum = device['devnum'].zfill(3)
            node_path = f"/dev/bus/usb/{busnum}/{devnum}"
            device['node'] = node_path
            device['exists'] = os.path.exists(node_path)

            if not device['exists']:
                self.auto_connect_adb(device)
                device['exists'] = os.path.exists(node_path)

            dev_item = QTreeWidgetItem(self.device_tree)
            dev_item.setText(0, f"{device['name']} [ADB]")
            dev_item.setText(1, f"{device['vendor_id']}:{device['product_id']}")
            dev_item.setText(2, f"USB {device['devclass']}")

            if device['exists']:
                dev_item.setText(3, t("connected"))
                dev_item.setForeground(3, QColor("#4CAF50"))
            else:
                dev_item.setText(3, t("disconnected"))
                dev_item.setForeground(3, QColor("#FF9800"))

                btn_widget = QWidget()
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(2, 2, 2, 2)

                connect_btn = QPushButton(t("connect"))
                connect_btn.clicked.connect(lambda checked, d=device: self.connect_adb(d))
                btn_layout.addWidget(connect_btn)

                self.device_tree.setItemWidget(dev_item, 4, btn_widget)

        self.known_devices = current_devices

        status_parts = []
        if total_storage > 0:
            status_parts.append(t("status_storage", total_storage))
        if total_adb > 0:
            status_parts.append(t("status_adb", total_adb))
        if mounted > 0:
            status_parts.append(t("status_mounted", mounted))

        if status_parts:
            status = t("status_detected", "，".join(status_parts))
        else:
            status = t("status_no_device")

        self.status_bar.showMessage(status)
        if self.tray_icon:
            self.tray_icon.setToolTip(f"{t('tray_tip')}\n{status}")

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
            subprocess.run(["sudo", "-n", "/usr/bin/mkdir", "-p", node_dir], capture_output=True)
            subprocess.run(
                ["sudo", "-n", "/usr/bin/mknod", "-m", "666", node_path, "c", "188", f"{int(busnum)*128+int(devnum)}"],
                capture_output=True
            )
            subprocess.run(["sudo", "-n", "/usr/bin/chmod", "666", node_path], capture_output=True)

            self.status_bar.showMessage(t("adb_node_created", node_path))
            self.scan_devices()
        except Exception as e:
            QMessageBox.warning(self, t("err_title"), t("err_adb_node_failed", str(e)))

    def connect_adb(self, device):
        """连接 ADB 设备"""
        script_path = os.path.join(os.path.dirname(__file__), "usb-passthrough.sh")
        if not os.path.exists(script_path):
            QMessageBox.warning(self, t("err_title"), t("err_script_missing", script_path))
            return

        try:
            result = subprocess.run(
                ["sudo", "-n", "bash", script_path],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.status_bar.showMessage(t("adb_connected"))
                self.scan_devices()
            else:
                QMessageBox.warning(self, t("err_adb_connect_title"), t("err_adb_connect", result.stderr))
        except Exception as e:
            QMessageBox.warning(self, t("err_title"), t("err_adb_error", str(e)))

    def auto_connect_adb(self, device):
        """自动连接 ADB 设备"""
        script_path = os.path.join(os.path.dirname(__file__), "usb-passthrough.sh")
        if not os.path.exists(script_path):
            return
        try:
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

        self.create_device_node(node, major, minor)

        if not os.path.exists(node):
            return

        mount_point = os.path.join(MOUNT_BASE, partition['name'])
        os.makedirs(mount_point, exist_ok=True)

        if fs_type in ['ntfs', 'ntfs3']:
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
                self.status_bar.showMessage(t("auto_mount_status", node, mount_point))
                if self.tray_icon:
                    self.tray_icon.showMessage(
                        t("notify_mount_title"),
                        t("notify_mount_msg", partition['name'], mount_point),
                        QSystemTrayIcon.Information,
                        3000
                    )
            else:
                print(f"Auto mount failed: {result.stderr}")
        except Exception as e:
            print(f"Auto mount error: {e}")

    def mount_partition(self, partition):
        """手动挂载分区"""
        node = partition['node']
        major = partition['major']
        minor = partition['minor']

        self.create_device_node(node, major, minor)

        if not os.path.exists(node):
            QMessageBox.warning(self, t("err_title"), t("err_node_missing", node))
            return

        mount_point = os.path.join(MOUNT_BASE, partition['name'])
        os.makedirs(mount_point, exist_ok=True)

        fs_type = partition.get('fs_type', '')
        if fs_type in ['ntfs', 'ntfs3']:
            cmd = f"sudo -n /usr/bin/mount -t ntfs-3g -o rw,no_def_opts,allow_other,umask=000 {node} {mount_point}"
        else:
            cmd = f"sudo -n /usr/bin/mount {node} {mount_point}"

        try:
            result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
            if result.returncode == 0:
                subprocess.run(["sudo", "-n", "/usr/bin/chmod", "-R", "777", mount_point])
                self.status_bar.showMessage(t("mount_status", node, mount_point))
                self.scan_paused = False
                self.scan_devices()
            else:
                QMessageBox.warning(self, t("err_mount_failed", result.stderr))
        except Exception as e:
            QMessageBox.warning(self, t("err_title"), t("err_mount_error", str(e)))

    def eject_device(self, partition):
        """弹出设备"""
        node = partition['node']
        mount_point = partition.get('mount_point')

        if mount_point:
            try:
                result = subprocess.run(
                    ["sudo", "-n", "/usr/bin/umount", mount_point],
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    QMessageBox.warning(self, t("err_eject_title"), t("err_eject_failed", result.stderr))
                    return
            except Exception as e:
                QMessageBox.warning(self, t("err_title"), t("err_eject_error", str(e)))
                return

        self.scan_paused = True
        self.known_devices.discard(node)

        self.status_bar.showMessage(t("eject_status", node))
        if self.tray_icon:
            self.tray_icon.showMessage(
                t("notify_eject_title"),
                t("notify_eject_msg", partition['name']),
                QSystemTrayIcon.Information,
                3000
            )
        self.refresh_ui()

    def open_directory(self, path):
        """打开目录"""
        if os.path.exists(path):
            if os.access(path, os.R_OK):
                subprocess.Popen(["dolphin", path])
            else:
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
            QMessageBox.information(self, t("info_title"), t("err_dir_missing", path))

    def show_about(self):
        """显示关于对话框"""
        if hasattr(self, '_about_dialog') and self._about_dialog.isVisible():
            self._about_dialog.raise_()
            self._about_dialog.activateWindow()
            return
        self._about_dialog = QDialog(self)
        self._about_dialog.setWindowTitle(t("about_title"))
        self._about_dialog.setFixedSize(450, 260)
        self._about_dialog.setWindowFlags(self._about_dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self._about_dialog)
        layout.setSpacing(8)

        name_label = QLabel("Droidspaces USB Manager")
        name_label.setFont(QFont("", 10, QFont.Bold))
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

        version_label = QLabel(f"{t('about_version')}: v1.2")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        layout.addSpacing(6)

        # 作者
        author_row = QHBoxLayout()
        author_row.addStretch()
        author_row.addWidget(QLabel(f"{t('about_author')}:"))
        author_btn = QPushButton("Yizhou147")
        author_btn.setCursor(Qt.PointingHandCursor)
        author_btn.setStyleSheet("QPushButton { border: none; color: #2196F3; }")
        author_btn.clicked.connect(lambda: subprocess.Popen(["xdg-open", "https://github.com/Yizhou147"]))
        author_row.addWidget(author_btn)
        author_row.addStretch()
        layout.addLayout(author_row)

        # 项目地址
        project_row = QHBoxLayout()
        project_row.addStretch()
        project_row.addWidget(QLabel(f"{t('about_project')}:"))
        project_btn = QPushButton("GitHub")
        project_btn.setCursor(Qt.PointingHandCursor)
        project_btn.setStyleSheet("QPushButton { border: none; color: #2196F3; }")
        project_btn.clicked.connect(lambda: subprocess.Popen(["xdg-open", "https://github.com/Yizhou147/Droidspaces-USB-Manager"]))
        project_row.addWidget(project_btn)
        project_row.addStretch()
        layout.addLayout(project_row)

        layout.addStretch()

        close_btn = QPushButton("OK")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self._about_dialog.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._about_dialog.show()


class UsbTrayIcon(QSystemTrayIcon):
    """系统托盘图标"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIcon(get_usb_icon())
        self.setToolTip(t("tray_tip"))

        self.main_window = MainWindow(self)
        self.create_menu()
        self.activated.connect(self.on_activated)

    def create_menu(self):
        """创建右键菜单"""
        self.menu = QMenu()

        self.show_action = QAction(t("tray_show"), self.menu)
        self.show_action.triggered.connect(self.show_main_window)
        self.menu.addAction(self.show_action)

        self.menu.addSeparator()

        self.refresh_action = QAction(t("tray_refresh"), self.menu)
        self.refresh_action.triggered.connect(self.main_window.scan_devices)
        self.menu.addAction(self.refresh_action)

        self.menu.addSeparator()

        self.quit_action = QAction(t("tray_quit"), self.menu)
        self.quit_action.triggered.connect(QApplication.quit)
        self.menu.addAction(self.quit_action)

        self.setContextMenu(self.menu)

    def retranslate_menu(self):
        """更新菜单文本"""
        self.show_action.setText(t("tray_show"))
        self.refresh_action.setText(t("tray_refresh"))
        self.quit_action.setText(t("tray_quit"))
        self.setToolTip(t("tray_tip"))

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
        print(t("err_pyqt5"))
        sys.exit(1)

    # 加载配置（自动检测语言）
    load_config()

    # 单实例检查
    lock_file = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
    except (IOError, OSError):
        app = QApplication(sys.argv)
        QMessageBox.warning(None, t("info_title"), t("already_running"))
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")

    tray = UsbTrayIcon()
    tray.show()
    tray.main_window.show()

    ret = app.exec_()

    fcntl.flock(lock_file, fcntl.LOCK_UN)
    lock_file.close()
    try:
        os.unlink(LOCK_FILE)
    except:
        pass

    sys.exit(ret)


if __name__ == "__main__":
    main()
