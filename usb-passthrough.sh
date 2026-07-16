#!/bin/bash
#
# Droidspaces USB Passthrough
# 在 Droidspaces Linux 容器中创建 USB 设备节点，使 ADB/Fastboot 可用
#
# 用法: sudo ./usb-passthrough.sh
#
# GitHub: https://github.com/USERNAME/droidspaces-usb-passthrough
# License: MIT

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 检查 root 权限
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[错误]${NC} 需要 root 权限运行此脚本"
    echo "用法: sudo $0"
    exit 1
fi

echo -e "${CYAN}=== Droidspaces USB Passthrough ===${NC}"
echo ""

# 检查是否在 Droidspaces 容器中
if [ ! -d /sys/bus/usb ]; then
    echo -e "${RED}[错误]${NC} /sys/bus/usb 不存在，请确认在 Droidspaces 容器中运行"
    echo "请在启动容器时添加: -H (启用硬件访问)"
    exit 1
fi

# 扫描 USB 设备
echo -e "${YELLOW}[1/3] 扫描 USB 设备...${NC}"
echo ""

DEVICES_FOUND=0

for devpath in /sys/bus/usb/devices/[0-9]*-[0-9]*; do
    [ -f "$devpath/dev" ] || continue

    major_minor=$(cat "$devpath/dev")
    major=${major_minor%:*}
    minor=${major_minor#*:}

    bus=$(cat "$devpath/busnum")
    devnum=$(cat "$devpath/devnum")

    product=$(cat "$devpath/product" 2>/dev/null || echo "未知设备")
    manufacturer=$(cat "$devpath/manufacturer" 2>/dev/null || echo "")
    vid=$(cat "$devpath/idVendor" 2>/dev/null || echo "????")
    pid=$(cat "$devpath/idProduct" 2>/dev/null || echo "????")

    dir="/dev/bus/usb/$(printf '%03d' "$bus")"
    node="$dir/$(printf '%03d' "$devnum")"

    mkdir -p "$dir"
    if [ ! -e "$node" ]; then
        mknod "$node" c "$major" "$minor"
        chmod 666 "$node"
        status="已创建"
    else
        chmod 666 "$node"
        status="已存在"
    fi

    echo -e "  Bus ${GREEN}$bus${NC} Device ${GREEN}$devnum${NC} → $node ($major:$minor)"
    echo -e "    ${CYAN}$manufacturer $product${NC} [${vid}:${pid}] [$status]"
    DEVICES_FOUND=$((DEVICES_FOUND + 1))
done

# 创建 root hub 节点
echo ""
echo -e "${YELLOW}[2/3] 创建 Root Hub 节点...${NC}"
echo ""

for hub in /sys/bus/usb/devices/usb[0-9]*; do
    [ -f "$hub/dev" ] || continue

    major_minor=$(cat "$hub/dev")
    major=${major_minor%:*}
    minor=${major_minor#*:}
    bus=$(cat "$hub/busnum")

    dir="/dev/bus/usb/$(printf '%03d' "$bus")"
    node="$dir/001"

    mkdir -p "$dir"
    if [ ! -e "$node" ]; then
        mknod "$node" c "$major" "$minor"
    fi
    chmod 666 "$node"

    speed=$(cat "$hub/speed" 2>/dev/null || echo "未知")
    echo -e "  Bus ${GREEN}$bus${NC} Root Hub → $node ($major:$minor) [${speed}Mbps]"
done

# 松开权限
chmod -R 777 /dev/bus/usb/ 2>/dev/null

# 测试 ADB
echo ""
echo -e "${YELLOW}[3/3] 测试 ADB...${NC}"
echo ""

if command -v adb &>/dev/null; then
    adb kill-server 2>/dev/null || true
    sleep 1
    ADB_OUTPUT=$(adb devices 2>&1)
    echo "$ADB_OUTPUT"

    if echo "$ADB_OUTPUT" | grep -q "device$"; then
        echo ""
        echo -e "${GREEN}[成功]${NC} ADB 已检测到设备！"
    elif echo "$ADB_OUTPUT" | grep -q "List of devices attached"; then
        echo ""
        echo -e "${YELLOW}[提示]${NC} ADB 正常但未检测到设备"
        echo "请确认手机已开启 USB 调试并已授权"
    fi
else
    echo -e "${YELLOW}[提示]${NC} 未安装 adb，请执行: apt install android-tools-adb"
fi

# 提示 Fastboot
if command -v fastboot &>/dev/null; then
    echo ""
    echo -e "${CYAN}Fastboot 已安装，手机进 bootloader 后可用:${NC}"
    echo "  fastboot devices"
    echo "  fastboot flash boot boot.img"
fi

echo ""
if [ "$DEVICES_FOUND" -gt 0 ]; then
    echo -e "${GREEN}[完成]${NC} 共处理 $DEVICES_FOUND 个 USB 设备"
else
    echo -e "${YELLOW}[完成]${NC} 未发现 USB 设备，请确认手机已连接"
fi
