# Droidspaces USB Passthrough

在 [Droidspaces](https://github.com/ravindu644/Droidspaces-OSS) Linux 容器中创建 USB 设备节点，使 `adb`、`fastboot` 等工具可用。

## 背景

Droidspaces 的 `-H`（硬件访问）选项会挂载 `/sys/bus/usb`（sysfs），但不会自动创建 `/dev/bus/usb/` 下的设备节点。而 `adb` 和 `fastboot` 依赖这些节点来访问 USB 设备。

本脚本自动扫描 sysfs 中的 USB 设备，读取 `major:minor` 号，并创建对应的 `/dev/bus/usb/BBB/DDD` 字符设备节点。

## 前提条件

- Droidspaces 容器，启动时添加 `-H` 参数（硬件访问）
- 容器内安装 `android-tools-adb`（或手动下载 platform-tools）

## 安装

```bash
# 下载脚本
wget https://raw.githubusercontent.com/USERNAME/droidspaces-usb-passthrough/main/usb-passthrough.sh

# 添加执行权限
chmod +x usb-passthrough.sh

# （可选）安装到系统路径
sudo cp usb-passthrough.sh /usr/local/bin/usb-passthrough.sh
```

## 使用

```bash
sudo ./usb-passthrough.sh
```

脚本会自动：
1. 扫描 `/sys/bus/usb/devices/` 中的所有 USB 设备
2. 读取每个设备的 `major:minor` 号
3. 在 `/dev/bus/usb/` 下创建对应的字符设备节点
4. 运行 `adb devices` 测试

## 桌面快捷方式

```bash
cp usb-passthrough.desktop ~/Desktop/
chmod +x ~/Desktop/usb-passthrough.desktop
# 如果桌面环境不信任该文件：
gio set ~/Desktop/usb-passthrough.desktop metadata::trusted true 2>/dev/null
```

## 工作原理

```
Android 宿主 USB 栈
    ↓ (Droidspaces -H 挂载 sysfs)
/sys/bus/usb/devices/X-Y/dev  →  "189:7"
    ↓ (本脚本读取并 mknod)
/dev/bus/usb/001/008  →  c 189 7
    ↓
adb / fastboot 可用 ✅
```

## 常见问题

### Q: 每次重启容器都要重新运行吗？
A: 是的。`/dev` 是 tmpfs，重启后设备节点会丢失。可以把脚本加到容器的启动脚本中。

### Q: 换了手机需要重新运行吗？
A: 是的。USB 设备号会变化，需要重新扫描创建。

### Q: 脚本能用于其他 USB 工具吗？
A: 可以。只要工具依赖 `/dev/bus/usb/` 设备节点，本脚本都适用。

## 致谢

- [Droidspaces](https://github.com/ravindu644/Droidspaces-OSS) by ravindu644

## License

MIT
