#!/bin/bash
#
# Droidspaces USB Storage Passthrough
# 在 Droidspaces Linux 容器中创建 USB 存储设备节点，使 U 盘可用
#
# 用法: ./usb-storage-passthrough.sh
#
# 首次运行会提示输入 sudo 密码配置免密码挂载，之后无需 sudo
#
# 依赖: apt install ntfs-3g exfatprogs   (NTFS/exFAT 支持)
#
# License: MIT

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SUDOERS_FILE="/etc/sudoers.d/usb-storage"
FUSE_CONF="/etc/fuse.conf"
CURRENT_USER=$(whoami)

echo -e "${CYAN}=== Droidspaces USB Storage Passthrough ===${NC}"
echo ""

# 首次运行配置 sudoers 和 FUSE
setup_permissions() {
    local need_sudo=false

    # 检查并配置 FUSE allow_other
    if [ -f "$FUSE_CONF" ] && ! grep -q "^user_allow_other" "$FUSE_CONF"; then
        echo -e "${YELLOW}[首次配置]${NC} 启用 FUSE allow_other（解决 NTFS 权限问题）"
        sudo sed -i 's/^#user_allow_other/user_allow_other/' "$FUSE_CONF" 2>/dev/null || \
        echo "user_allow_other" | sudo tee -a "$FUSE_CONF" > /dev/null
        need_sudo=true
    fi

    # 检查并配置 sudoers
    if [ ! -f "$SUDOERS_FILE" ]; then
        if [ "$need_sudo" = false ]; then
            echo -e "${YELLOW}[首次配置]${NC} 需要设置 sudo 免密码挂载"
            echo -e "  这只需要输入一次密码，之后运行将不再需要 sudo"
            echo ""
        fi

        sudo tee "$SUDOERS_FILE" > /dev/null << EOF
# USB 存储设备挂载权限配置 (由 usb-storage-passthrough.sh 自动创建)
$CURRENT_USER ALL=(root) NOPASSWD: /usr/bin/mount /dev/sd* /home/$CURRENT_USER/USB-Storage
$CURRENT_USER ALL=(root) NOPASSWD: /usr/bin/umount /home/$CURRENT_USER/USB-Storage
$CURRENT_USER ALL=(root) NOPASSWD: /usr/bin/mknod /dev/sd*
$CURRENT_USER ALL=(root) NOPASSWD: /usr/bin/chmod * /dev/sd*
$CURRENT_USER ALL=(root) NOPASSWD: /usr/bin/sed -i * /etc/fuse.conf
EOF

        sudo chmod 440 "$SUDOERS_FILE"
        need_sudo=true
    fi

    if [ "$need_sudo" = true ]; then
        echo -e "${GREEN}[完成]${NC} 权限配置已设置"
        echo ""
    fi
}

# 执行首次配置
setup_permissions

# 检查是否在 Droidspaces 容器中
if [ ! -d /sys/bus/scsi ]; then
    echo -e "${RED}[错误]${NC} /sys/bus/scsi 不存在，无法扫描 SCSI 设备"
    exit 1
fi

# 扫描 USB 存储设备（只处理通过 USB 连接的 SCSI 设备，跳过内部存储）
echo -e "${YELLOW}[1/3] 扫描 USB 存储设备...${NC}"
echo ""

DEVICES_FOUND=0
USB_PARTS=()

for scsi_dev_path in /sys/bus/scsi/devices/*/block/*; do
    [ -d "$scsi_dev_path" ] || continue

    block_name=$(basename "$scsi_dev_path")
    scsi_path=$(dirname "$scsi_dev_path")

    # 只处理通过 USB 连接的设备（路径包含 usb），跳过内部 UFS/eMMC 存储
    real_path=$(readlink -f "$scsi_path" 2>/dev/null)
    echo "$real_path" | grep -q "usb" || continue

    # 读取 major:minor
    dev_file="$scsi_dev_path/dev"
    [ -f "$dev_file" ] || continue
    major_minor=$(cat "$dev_file")
    major=${major_minor%:*}
    minor=${major_minor#*:}

    # 读取设备信息
    vendor=$(cat "$scsi_path/vendor" 2>/dev/null | tr -d ' ')
    model=$(cat "$scsi_path/model" 2>/dev/null | tr -d ' ')
    size_sectors=$(cat "$scsi_dev_path/size" 2>/dev/null || echo "0")
    size_gb=$((size_sectors * 512 / 1073741824))

    # 创建设备节点
    node="/dev/$block_name"
    if [ ! -e "$node" ]; then
        sudo -n mknod "$node" b "$major" "$minor"
        sudo -n chmod 666 "$node"
        status="已创建"
    else
        sudo -n chmod 666 "$node"
        status="已存在"
    fi

    echo -e "  ${GREEN}$block_name${NC} → $node ($major:$minor) [${size_gb}GB]"
    echo -e "    ${CYAN}$vendor $model${NC} [$status]"
    DEVICES_FOUND=$((DEVICES_FOUND + 1))

    # 扫描分区
    for partition in "$scsi_dev_path/${block_name}"*; do
        [ -d "$partition" ] || continue
        part_name=$(basename "$partition")
        [ "$part_name" = "$block_name" ] && continue

        part_dev_file="$partition/dev"
        [ -f "$part_dev_file" ] || continue
        part_major_minor=$(cat "$part_dev_file")
        part_major=${part_major_minor%:*}
        part_minor=${part_major_minor#*:}

        part_node="/dev/$part_name"
        if [ ! -e "$part_node" ]; then
            sudo -n mknod "$part_node" b "$part_major" "$part_minor"
            sudo -n chmod 666 "$part_node"
            part_status="已创建"
        else
            sudo -n chmod 666 "$part_node"
            part_status="已存在"
        fi

        part_size_sectors=$(cat "$partition/size" 2>/dev/null || echo "0")
        part_size_gb=$((part_size_sectors * 512 / 1073741824))

        echo -e "    └─ ${GREEN}$part_name${NC} → $part_node ($part_major:$part_minor) [${part_size_gb}GB] [$part_status]"
        USB_PARTS+=("$part_node")
    done
done

# 尝试挂载
echo ""
echo -e "${YELLOW}[2/3] 尝试挂载 USB 分区...${NC}"
echo ""

# 挂载到用户主目录下，避免 NTFS 权限问题
MOUNT_POINT="$HOME/USB-Storage"
# 删除可能存在的符号链接
if [ -L "$MOUNT_POINT" ]; then
    rm -f "$MOUNT_POINT"
fi
mkdir -p "$MOUNT_POINT"

MOUNTED=0
for partition in "${USB_PARTS[@]}"; do
    [ -b "$partition" ] || continue

    # 检查是否已挂载
    if mount | grep -q "$partition"; then
        mount_point=$(mount | grep "$partition" | awk '{print $3}')
        echo -e "  ${GREEN}$partition${NC} 已挂载到 $mount_point"
        MOUNTED=$((MOUNTED + 1))
        continue
    fi

    # 尝试挂载（支持 NTFS/exFAT/FAT/ext 等）
    echo -e "  尝试挂载 ${GREEN}$partition${NC}..."
    fs_type=$(blkid -s TYPE -o value "$partition" 2>/dev/null)

    if [ "$fs_type" = "ntfs" ] || [ "$fs_type" = "ntfs3" ]; then
        # 使用 no_def_opts 避免 NTFS ACL 覆盖 Linux 权限
        mount_opts="rw,no_def_opts,allow_other,umask=000,uid=$(id -u),gid=$(id -g)"
        sudo -n mount -t ntfs-3g -o "$mount_opts" "$partition" "$MOUNT_POINT" 2>/dev/null && mounted=true || mounted=false
    elif [ "$fs_type" = "exfat" ]; then
        mount_opts="rw,uid=$(id -u),gid=$(id -g),umask=000"
        sudo -n mount -t exfat -o "$mount_opts" "$partition" "$MOUNT_POINT" 2>/dev/null && mounted=true || mounted=false
    else
        mount_opts="rw"
        sudo -n mount -o "$mount_opts" "$partition" "$MOUNT_POINT" 2>/dev/null && mounted=true || mounted=false
    fi

    if [ "$mounted" = "true" ]; then
        echo -e "  ${GREEN}$partition${NC} → $MOUNT_POINT [成功] ($fs_type)"
        # 挂载后再次设置权限（NTFS 会覆盖之前的权限）
        sudo -n chmod 777 "$MOUNT_POINT" 2>/dev/null || true
        MOUNTED=$((MOUNTED + 1))
        break
    fi
done

# 测试可用性
echo ""
echo -e "${YELLOW}[3/3] 检查结果...${NC}"
echo ""

if [ "$DEVICES_FOUND" -gt 0 ]; then
    echo -e "${GREEN}[完成]${NC} 共发现 $DEVICES_FOUND 个 USB 存储设备"
    if [ "$MOUNTED" -gt 0 ]; then
        echo -e "${GREEN}[成功]${NC} 已挂载 $MOUNTED 个分区到 $MOUNT_POINT"
        echo -e "${GREEN}[提示]${NC} 在 Dolphin 地址栏输入 ~ 即可看到 USB-Storage"
    else
        echo -e "${YELLOW}[提示]${NC} 未能自动挂载，请手动挂载:"
        echo "  sudo mount /dev/sdX1 /mnt/usb-storage"
    fi
else
    echo -e "${YELLOW}[完成]${NC} 未发现 USB 存储设备"
    echo "请确认 U 盘已插入手机"
fi

# 显示挂载信息
echo ""
echo -e "${CYAN}挂载信息:${NC}"
mount | grep "$MOUNT_POINT" || echo "  无 USB 存储设备挂载"
