using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace UotanToolbox.Features.UsbManager;

/// <summary>USB 存储分区</summary>
public class UsbPartitionInfo
{
    public string Name = "";
    public string Node = "";
    public int Major;
    public int Minor;
    public long SizeGb;
    public string FsType = "";
    public bool Mounted;
    public string MountPoint = "";
}

/// <summary>USB 存储设备（块设备 + 分区）</summary>
public class UsbStorageInfo
{
    public string Node = "";
    public string Model = "";
    public string Vendor = "";
    public long SizeGb;
    public List<UsbPartitionInfo> Partitions { get; } = [];
}

/// <summary>UVC 设备的 video4linux 节点</summary>
public class UsbV4lNode
{
    public string Name = "";
    public string Node = "";
    public int Major;
    public int Minor;
}

/// <summary>非存储 USB 设备（ADB/Hub/HID/视频等）</summary>
public class UsbDeviceInfo
{
    public string Type = "unknown";
    public string Name = "";
    public string Node = "";
    public string VendorId = "";
    public string ProductId = "";
    public string Busnum = "";
    public string Devnum = "";
    public string DevClass = "";
    public bool HasMtp;
    public bool MtpMounted;
    public bool NodeExists;
    public string V4lReadyNode = "";
    public List<UsbV4lNode> V4lNodes { get; } = [];

    public string NodePath => $"/dev/bus/usb/{Busnum.PadLeft(3, '0')}/{Devnum.PadLeft(3, '0')}";
}

/// <summary>
/// Droidspaces USB 硬件层：sysfs 扫描、设备分类、节点创建、挂载与 MTP/UVC 支持。
/// 从 Droidspaces-USB-Manager (PyQt5) 移植，所有阻塞操作均为 async，供后台任务调用。
/// </summary>
public static class UsbHardware
{
    private static readonly string MountBase = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "USB-Storage");

    public static bool IsLinux => RuntimeInformation.IsOSPlatform(OSPlatform.Linux);

    // ==================== USB class 码分类 ====================
    // 参考 USB 规范 https://www.usb.org/defined-class-codes
    private static readonly Dictionary<string, string> ClassTypes = new()
    {
        ["01"] = "audio", ["02"] = "network", ["03"] = "hid", ["05"] = "physical",
        ["06"] = "image", ["07"] = "printer", ["08"] = "storage", ["09"] = "hub",
        ["0a"] = "network", ["0b"] = "smartcard", ["0d"] = "security", ["0e"] = "video",
        ["0f"] = "health", ["10"] = "av", ["dc"] = "diagnostic", ["e0"] = "wireless",
        ["fe"] = "app_specific", ["ff"] = "vendor",
    };

    // 多接口设备主类型优先级（越靠前越"主要"，如摄像头+麦克风选视频）
    private static readonly string[] TypePriority =
    [
        "storage", "video", "audio", "network", "hid", "printer", "smartcard",
        "image", "wireless", "health", "physical", "av", "security", "diagnostic",
        "app_specific", "vendor",
    ];

    // V4L2 capability 位（linux/videodev2.h）：区分视频采集节点与 metadata 节点
    private const uint V4l2CapVideoCapture = 0x00000001;
    private const uint VidioCQuerycap = 0x80685600; // _IOR('V', 0, struct v4l2_capability)

    private static string? FindBlkid()
    {
        foreach (string p in new[] { "/usr/bin/blkid", "/usr/sbin/blkid", "/sbin/blkid" })
        {
            if (File.Exists(p)) return p;
        }
        return Which("blkid") ?? "/usr/sbin/blkid";
    }

    public static string? Which(string name)
    {
        string pathEnv = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (string dir in pathEnv.Split(':', StringSplitOptions.RemoveEmptyEntries))
        {
            string candidate = Path.Combine(dir, name);
            try
            {
                if (File.Exists(candidate)) return candidate;
            }
            catch { /* ignore */ }
        }
        return null;
    }

    private static string? ReadSysfs(string path)
    {
        try
        {
            return File.ReadAllText(path).Trim();
        }
        catch
        {
            return null;
        }
    }

    // ==================== libc 互操作（open/ioctl/stat，用于 UVC 节点校验） ====================
    [DllImport("libc", SetLastError = true)] private static extern int open(string path, int flags);
    [DllImport("libc", SetLastError = true)] private static extern int close(int fd);
    [DllImport("libc", SetLastError = true)] private static extern int ioctl(int fd, uint request, byte[] buf);
    [DllImport("libc", SetLastError = true)] private static extern int stat(string path, byte[] buf);

    private const int O_RDONLY_NONBLOCK = 0x800; // O_RDONLY(0) | O_NONBLOCK on Linux

    /// <summary>通过 VIDIOC_QUERYCAP 读取节点 device_caps，失败返回 0</summary>
    private static uint V4lDeviceCaps(string node)
    {
        int fd = open(node, O_RDONLY_NONBLOCK);
        if (fd < 0) return 0;
        try
        {
            byte[] cap = new byte[104];
            if (ioctl(fd, VidioCQuerycap, cap) != 0) return 0;
            // device_caps 位于 struct v4l2_capability 偏移 88
            return BitConverter.ToUInt32(cap, 88);
        }
        finally
        {
            _ = close(fd);
        }
    }

    // glibc makedev：major/minor → dev_t（Linux 新式编码）
    private static ulong MakeDev(int major, int minor) =>
        ((ulong)(major & 0xfff) << 8) | ((ulong)(major & ~0xfff) << 32)
        | ((ulong)(minor & 0xff) << 0) | ((ulong)(minor & ~0xff) << 12);

    /// <summary>
    /// 节点存在且设备号与 sysfs 一致才算有效。stale 节点（文件在但设备号已因拔插漂移）
    /// open 会 ENXIO/黑屏，仅存在性检查无法识别，必须比对设备号。
    /// aarch64 glibc struct stat：st_rdev 位于偏移 40（__pad0 在 32）。
    /// </summary>
    private static bool VideoNodeMatches(string node, int major, int minor)
    {
        try
        {
            byte[] buf = new byte[256];
            if (stat(node, buf) != 0) return false;
            ulong rdev = BitConverter.ToUInt64(buf, 40);
            return rdev == MakeDev(major, minor);
        }
        catch
        {
            return false;
        }
    }

    // ==================== Shell ====================
    public sealed class ShellResult
    {
        public int ExitCode;
        public string StdOut = "";
        public string StdErr = "";
        public bool Success => ExitCode == 0;
    }

    public static async Task<ShellResult> RunAsync(string file, string args, int timeoutMs = 10000)
    {
        ShellResult result = new();
        try
        {
            using Process proc = new()
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = file,
                    Arguments = args,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                },
            };
            proc.Start();
            Task<string> outTask = proc.StandardOutput.ReadToEndAsync();
            Task<string> errTask = proc.StandardError.ReadToEndAsync();
            Task done = proc.WaitForExitAsync();
            Task finished = await Task.WhenAny(done, Task.Delay(timeoutMs));
            if (finished != done)
            {
                try { proc.Kill(true); } catch { /* already dead */ }
                result.ExitCode = -1;
                result.StdErr = "timeout";
                return result;
            }
            result.ExitCode = proc.ExitCode;
            result.StdOut = await outTask;
            result.StdErr = await errTask;
        }
        catch (Exception e)
        {
            result.ExitCode = -1;
            result.StdErr = e.Message;
        }
        return result;
    }

    private static uint GetUid()
    {
        try { return getuid(); } catch { return 1000; }
    }

    private static uint GetGid()
    {
        try { return getgid(); } catch { return 1000; }
    }

    [DllImport("libc")] private static extern uint getuid();
    [DllImport("libc")] private static extern uint getgid();

    // ==================== 设备节点 ====================
    /// <summary>创建块设备节点（devtmpfs 静态容器不自动建节点）</summary>
    public static async Task<bool> CreateDeviceNodeAsync(string node, int major, int minor)
    {
        if (File.Exists(node)) return true;
        await RunAsync("sudo", $"-n /usr/bin/mknod -m 666 {node} b {major} {minor}");
        await RunAsync("sudo", $"-n /usr/bin/chmod 666 {node}");
        return File.Exists(node);
    }

    /// <summary>执行 usb-passthrough.sh 创建 ADB/Fastboot/所有 USB 设备节点</summary>
    public static async Task<bool> RunPassthroughAsync()
    {
        string script = Path.Combine(AppContext.BaseDirectory, "Assets", "USB", "usb-passthrough.sh");
        if (!File.Exists(script)) return false;
        ShellResult r = await RunAsync("sudo", $"-n bash \"{script}\"", 30000);
        return r.Success;
    }

    // ==================== 分类 ====================
    /// <summary>
    /// 根据 bDeviceClass 与接口 bInterfaceClass 判定 USB 设备类型。
    /// 设备级 09 → hub；00/ef（Misc/多接口）按接口判定（(ff,42,01)=ADB、(ff,42,03)=Fastboot，
    /// 其余取优先级最高的接口类码）；其余设备级类码直接映射。
    /// </summary>
    private static string ClassifyUsbDevice(string devPath)
    {
        string devclass = ReadSysfs(Path.Combine(devPath, "bDeviceClass")) ?? "00";
        if (devclass == "09") return "hub";

        if (devclass is "00" or "ef")
        {
            List<string> ifaceTypes = [];
            try
            {
                foreach (string iface in Directory.GetDirectories(devPath))
                {
                    if (!Path.GetFileName(iface).Contains(':')) continue;
                    string iclass = ReadSysfs(Path.Combine(iface, "bInterfaceClass")) ?? "";
                    string isub = ReadSysfs(Path.Combine(iface, "bInterfaceSubClass")) ?? "";
                    string iprot = ReadSysfs(Path.Combine(iface, "bInterfaceProtocol")) ?? "";
                    if (iclass == "ff" && isub == "42")
                    {
                        if (iprot == "01") return "adb";
                        if (iprot == "03") return "fastboot";
                    }
                    if (iclass.Length > 0 && ClassTypes.TryGetValue(iclass, out string? dtype))
                    {
                        ifaceTypes.Add(dtype);
                    }
                }
            }
            catch { /* unreadable sysfs */ }
            foreach (string t in TypePriority)
            {
                if (ifaceTypes.Contains(t)) return t;
            }
            return ifaceTypes.Count > 0 ? ifaceTypes[0] : "unknown";
        }

        return ClassTypes.TryGetValue(devclass, out string? mapped) ? mapped : "unknown";
    }

    /// <summary>检测设备是否含 MTP/PTP 接口（class=06，或厂商类 ff 且非 Android 调试接口）</summary>
    private static bool HasMtpInterface(string devPath)
    {
        try
        {
            foreach (string iface in Directory.GetDirectories(devPath))
            {
                if (!Path.GetFileName(iface).Contains(':')) continue;
                string iclass = ReadSysfs(Path.Combine(iface, "bInterfaceClass")) ?? "";
                string isub = ReadSysfs(Path.Combine(iface, "bInterfaceSubClass")) ?? "";
                if (iclass == "06") return true;
                if (iclass == "ff" && isub != "42") return true;
            }
        }
        catch { /* ignore */ }
        return false;
    }

    /// <summary>反查该 USB 设备对应的 /dev/video* 节点清单（video4linux sysfs 匹配）</summary>
    private static void CollectV4lNodes(string devPath, UsbDeviceInfo device)
    {
        string prefix;
        try
        {
            // /sys/bus/usb/devices/* 是符号链接，必须解析成真实路径才能与
            // video4linux 的 device 链接（解析后同在 /sys/devices/...）匹配
            prefix = ResolveFinal(devPath);
        }
        catch
        {
            return;
        }
        const string v4lBase = "/sys/class/video4linux";
        if (!Directory.Exists(v4lBase)) return;
        foreach (string vp in Directory.GetDirectories(v4lBase))
        {
            string name = Path.GetFileName(vp);
            if (!name.StartsWith("video")) continue;
            string devReal;
            try
            {
                devReal = ResolveFinal(Path.Combine(vp, "device"));
            }
            catch
            {
                continue;
            }
            if (devReal != prefix && !devReal.StartsWith(prefix + "/")) continue;
            string devMap = ReadSysfs(Path.Combine(vp, "dev")) ?? "";
            if (!devMap.Contains(':')) continue;
            string[] mm = devMap.Split(':', 2);
            device.V4lNodes.Add(new UsbV4lNode
            {
                Name = name,
                Node = $"/dev/{name}",
                Major = int.TryParse(mm[0], out int mj) ? mj : 0,
                Minor = int.TryParse(mm[1], out int mn) ? mn : 0,
            });
        }
    }

    private static string ResolveFinal(string path)
    {
        FileSystemInfo? link = Directory.Exists(path)
            ? (FileSystemInfo)new DirectoryInfo(path)
            : new FileInfo(path);
        FileSystemInfo? final = link.ResolveLinkTarget(true);
        return final?.FullName ?? path;
    }

    // ==================== 扫描 ====================
    /// <summary>解析 /proc/mounts，返回 设备节点 → 挂载点（含八进制转义还原）</summary>
    private static Dictionary<string, string> ReadMounts()
    {
        Dictionary<string, string> mounts = new();
        try
        {
            foreach (string line in File.ReadAllLines("/proc/mounts"))
            {
                string[] parts = line.Split(' ');
                if (parts.Length < 3) continue;
                string dev = parts[0].Replace("\\040", " ").Replace("\\011", "\t");
                string mp = parts[1].Replace("\\040", " ").Replace("\\011", "\t");
                mounts[dev] = mp;
            }
        }
        catch { /* no /proc/mounts */ }
        return mounts;
    }

    private static async Task<string> GetFsTypeAsync(string device)
    {
        if (!File.Exists(device)) return "";
        string blkid = FindBlkid();
        ShellResult r = await RunAsync("sudo", $"-n {blkid} -s TYPE -o value {device}");
        return r.StdOut.Trim();
    }

    /// <summary>扫描 USB 存储设备（/sys/bus/scsi 中路径含 usb 的块设备及其分区）</summary>
    private static async Task<List<UsbStorageInfo>> ScanStorageAsync()
    {
        List<UsbStorageInfo> devices = [];
        const string scsiBase = "/sys/bus/scsi/devices";
        if (!Directory.Exists(scsiBase)) return devices;
        Dictionary<string, string> mounts = ReadMounts();

        foreach (string scsiDev in Directory.GetFileSystemEntries(scsiBase))
        {
            string blockDir = Path.Combine(scsiDev, "block");
            if (!Directory.Exists(blockDir)) continue;
            string realPath;
            try
            {
                realPath = ResolveFinal(scsiDev);
            }
            catch
            {
                continue;
            }
            if (!realPath.Contains("usb")) continue;

            foreach (string blockDev in Directory.GetDirectories(blockDir))
            {
                string devMap = ReadSysfs(Path.Combine(blockDev, "dev"));
                if (devMap is null || !devMap.Contains(':')) continue;
                try
                {
                    string[] mm = devMap.Split(':', 2);
                    string name = Path.GetFileName(blockDev);
                    UsbStorageInfo info = new()
                    {
                        Node = $"/dev/{name}",
                        Model = (ReadSysfs(Path.Combine(scsiDev, "model")) ?? "Unknown").Trim(),
                        Vendor = (ReadSysfs(Path.Combine(scsiDev, "vendor")) ?? "Unknown").Trim(),
                        SizeGb = long.TryParse(ReadSysfs(Path.Combine(blockDev, "size")), out long sectors)
                            ? sectors * 512 / 1073741824 : 0,
                    };

                    foreach (string partDir in Directory.GetDirectories(blockDev))
                    {
                        string partMap = ReadSysfs(Path.Combine(partDir, "dev"));
                        if (partMap is null || !partMap.Contains(':')) continue;
                        string[] pmm = partMap.Split(':', 2);
                        string partName = Path.GetFileName(partDir);
                        string partNode = $"/dev/{partName}";

                        await CreateDeviceNodeAsync(partNode, int.Parse(pmm[0]), int.Parse(pmm[1]));
                        string fsType = await GetFsTypeAsync(partNode);
                        mounts.TryGetValue(partNode, out string? mountPoint);

                        info.Partitions.Add(new UsbPartitionInfo
                        {
                            Name = partName,
                            Node = partNode,
                            Major = int.Parse(pmm[0]),
                            Minor = int.Parse(pmm[1]),
                            SizeGb = long.TryParse(ReadSysfs(Path.Combine(partDir, "size")), out long psectors)
                                ? psectors * 512 / 1073741824 : 0,
                            FsType = fsType,
                            Mounted = mountPoint is not null,
                            MountPoint = mountPoint ?? "",
                        });
                    }
                    devices.Add(info);
                }
                catch { /* skip unreadable device */ }
            }
        }
        return devices;
    }

    /// <summary>扫描非存储 USB 设备并按 class 码分类</summary>
    private static List<UsbDeviceInfo> ScanOtherUsbDevices()
    {
        List<UsbDeviceInfo> devices = [];
        const string usbBase = "/sys/bus/usb/devices";
        if (!Directory.Exists(usbBase)) return devices;

        HashSet<string> storageUsbPaths = [];
        const string scsiBase = "/sys/bus/scsi/devices";
        if (Directory.Exists(scsiBase))
        {
            foreach (string scsiDev in Directory.GetFileSystemEntries(scsiBase))
            {
                try
                {
                    string realPath = ResolveFinal(scsiDev);
                    if (!realPath.Contains("usb")) continue;
                    string[] parts = realPath.Split('/');
                    for (int i = 0; i < parts.Length - 1; i++)
                    {
                        if (parts[i].StartsWith("usb") && parts[i + 1].Length > 0)
                        {
                            // usb 控制器目录后的端口目录（如 usb3/3-1 → 3-1）
                            if (!parts[i + 1].StartsWith("usb"))
                            {
                                storageUsbPaths.Add(parts[i + 1]);
                            }
                            break;
                        }
                    }
                }
                catch { /* ignore */ }
            }
        }

        foreach (string devPath in Directory.GetFileSystemEntries(usbBase))
        {
            string devName = Path.GetFileName(devPath);
            if (devName.Contains(':') || devName.StartsWith("usb")) continue;
            if (storageUsbPaths.Contains(devName)) continue;

            string vid = ReadSysfs(Path.Combine(devPath, "idVendor"));
            string pid = ReadSysfs(Path.Combine(devPath, "idProduct"));
            if (vid is null || pid is null) continue;

            string busnum = ReadSysfs(Path.Combine(devPath, "busnum"));
            string devnum = ReadSysfs(Path.Combine(devPath, "devnum"));
            if (busnum is null || devnum is null) continue;

            UsbDeviceInfo info = new()
            {
                Type = ClassifyUsbDevice(devPath),
                Name = (ReadSysfs(Path.Combine(devPath, "product")) ?? "Unknown"),
                VendorId = vid,
                ProductId = pid,
                Busnum = busnum.Trim(),
                Devnum = devnum.Trim(),
                DevClass = ReadSysfs(Path.Combine(devPath, "bDeviceClass")) ?? "00",
            };
            info.Node = info.NodePath;
            info.HasMtp = info.Type != "storage" && HasMtpInterface(devPath);
            CollectV4lNodes(devPath, info);
            info.NodeExists = File.Exists(info.Node);
            devices.Add(info);
        }
        return devices;
    }

    /// <summary>校正 UVC 采集卡 /dev/video* 节点：缺失→创建；号不符→重建。返回就绪的采集节点。</summary>
    public static async Task<string> EnsureVideoNodesAsync(UsbDeviceInfo device)
    {
        foreach (UsbV4lNode n in device.V4lNodes)
        {
            if (VideoNodeMatches(n.Node, n.Major, n.Minor)) continue;
            // stale 节点（设备号漂移）先删除再重建，mknod 无法覆盖已存在节点
            await RunAsync("sudo", $"-n /usr/bin/rm -f {n.Node}");
            await RunAsync("sudo", $"-n /usr/bin/mknod -m 666 {n.Node} c {n.Major} {n.Minor}");
            await RunAsync("sudo", $"-n /usr/bin/chmod 666 {n.Node}");
        }

        string ready = device.V4lNodes.FirstOrDefault(n =>
            VideoNodeMatches(n.Node, n.Major, n.Minor)
            && (V4lDeviceCaps(n.Node) & V4l2CapVideoCapture) != 0)?.Node ?? "";
        if (ready.Length == 0)
        {
            // 能力探测失败（如无权限）时退回任一设备号匹配的节点
            ready = device.V4lNodes.FirstOrDefault(n => VideoNodeMatches(n.Node, n.Major, n.Minor))?.Node ?? "";
        }
        return ready;
    }

    // ==================== 挂载 ====================
    /// <summary>清理 USB-Storage 下的失效挂载与残留目录（空目录、内核块设备已消失的幽灵挂载）</summary>
    public static async Task CleanupMountPointsAsync()
    {
        if (!Directory.Exists(MountBase)) return;
        Dictionary<string, string> mounts = ReadMounts();
        foreach (string dir in Directory.GetDirectories(MountBase))
        {
            try
            {
                Directory.Delete(dir, false);
                continue; // 空目录直接删除
            }
            catch { /* not empty or in use */ }

            foreach ((_, string mp) in mounts.Where(kvp => kvp.Value == dir).ToList())
            {
                string devName = Path.GetFileName(mp);
                if (!Directory.Exists($"/sys/class/block/{devName}"))
                {
                    await RunAsync("sudo", $"-n /usr/bin/umount \"{mp}\"");
                    try { Directory.Delete(dir, false); } catch { /* ignore */ }
                }
            }
        }
    }

    private static (string Args, string MountPoint) BuildMountCommand(UsbPartitionInfo part)
    {
        string mountPoint = Path.Combine(MountBase, part.Name);
        string uid = GetUid().ToString();
        string gid = GetGid().ToString();
        string args = part.FsType switch
        {
            "ntfs" or "ntfs3" =>
                $"-n /usr/bin/mount -t ntfs-3g -o rw,no_def_opts,allow_other,uid={uid},gid={gid},umask=000 {part.Node} \"{mountPoint}\"",
            "exfat" =>
                $"-n /usr/bin/mount -t exfat -o rw,uid={uid},gid={gid},umask=000 {part.Node} \"{mountPoint}\"",
            "vfat" or "fat32" =>
                $"-n /usr/bin/mount -t vfat -o rw,uid={uid},gid={gid},umask=000 {part.Node} \"{mountPoint}\"",
            _ => $"-n /usr/bin/mount {part.Node} \"{mountPoint}\"",
        };
        return (args, mountPoint);
    }

    /// <summary>挂载分区（自动/手动共用）；返回 (是否成功, 错误信息)</summary>
    public static async Task<(bool Ok, string Error)> MountPartitionAsync(UsbPartitionInfo part)
    {
        await CreateDeviceNodeAsync(part.Node, part.Major, part.Minor);
        if (!File.Exists(part.Node))
        {
            return (false, $"Device node {part.Node} does not exist");
        }
        (string args, string mountPoint) = BuildMountCommand(part);
        ShellResult r = await RunAsync("sudo", args, 20000);
        if (r.Success)
        {
            part.Mounted = true;
            part.MountPoint = mountPoint;
            return (true, "");
        }
        return (false, r.StdErr.Length > 0 ? r.StdErr : r.StdOut);
    }

    /// <summary>弹出分区（umount 挂载点）</summary>
    public static async Task<(bool Ok, string Error)> EjectPartitionAsync(UsbPartitionInfo part)
    {
        if (part.Mounted && part.MountPoint.Length > 0)
        {
            ShellResult r = await RunAsync("sudo", $"-n /usr/bin/umount \"{part.MountPoint}\"", 15000);
            if (!r.Success)
            {
                return (false, r.StdErr.Length > 0 ? r.StdErr : r.StdOut);
            }
        }
        part.Mounted = false;
        part.MountPoint = "";
        return (true, "");
    }

    // ==================== MTP ====================
    private static string MtpUri(UsbDeviceInfo device) =>
        $"mtp://[usb:{device.Busnum.PadLeft(3, '0')},{device.Devnum.PadLeft(3, '0')}]";

    public static async Task<bool> IsMtpMountedAsync(UsbDeviceInfo device)
    {
        ShellResult r = await RunAsync("gio", "mount -l");
        return r.Success && r.StdOut.Contains(MtpUri(device));
    }

    public static async Task<(bool Ok, string Error)> MountMtpAsync(UsbDeviceInfo device)
    {
        ShellResult r = await RunAsync("gio", $"mount \"{MtpUri(device)}\"", 15000);
        return r.Success ? (true, "") : (false, r.StdErr.Length > 0 ? r.StdErr.Trim() : "gio mount failed");
    }

    public static async Task<(bool Ok, string Error)> UnmountMtpAsync(UsbDeviceInfo device)
    {
        ShellResult r = await RunAsync("gio", $"mount -u \"{MtpUri(device)}\"", 15000);
        return r.Success ? (true, "") : (false, r.StdErr.Length > 0 ? r.StdErr.Trim() : "gio mount -u failed");
    }

    /// <summary>确保 gvfsd-fuse 运行（KDE 会话不自动启动它，MTP 需要它以本地目录形式挂载）</summary>
    public static void EnsureGvfsFuse()
    {
        string xdgRuntime = Environment.GetEnvironmentVariable("XDG_RUNTIME_DIR") ?? "";
        if (xdgRuntime.Length == 0) return;
        string gvfsDir = Path.Combine(xdgRuntime, "gvfs");
        if (!Directory.Exists(gvfsDir)) return;
        ShellResult r = RunAsync("pgrep", "-x gvfsd-fuse", 5000).GetAwaiter().GetResult();
        if (r.Success) return;
        string gvfsdFuse = File.Exists("/usr/libexec/gvfsd-fuse") ? "/usr/libexec/gvfsd-fuse"
            : File.Exists("/usr/lib/gvfs/gvfsd-fuse") ? "/usr/lib/gvfs/gvfsd-fuse" : "";
        if (gvfsdFuse.Length == 0) return;
        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = gvfsdFuse,
                Arguments = $"\"{gvfsDir}\"",
                UseShellExecute = false,
            });
            Thread.Sleep(300);
        }
        catch { /* ignore */ }
    }

    /// <summary>查找当前设备对应的 gvfs MTP 本地目录（目录名 URL 编码，需精确匹配避免幽灵挂载）</summary>
    public static string? GetGvfsMtpPath(UsbDeviceInfo device)
    {
        string target = $"usb:{device.Busnum.PadLeft(3, '0')},{device.Devnum.PadLeft(3, '0')}";
        string xdgRuntime = Environment.GetEnvironmentVariable("XDG_RUNTIME_DIR") ?? "";
        string gvfsDir = Path.Combine(xdgRuntime, "gvfs");
        if (!Directory.Exists(gvfsDir)) return null;
        try
        {
            foreach (string entry in Directory.GetFileSystemEntries(gvfsDir))
            {
                string name = Path.GetFileName(entry);
                if (name.StartsWith("mtp:host=")
                    && Uri.UnescapeDataString(name).Contains(target))
                {
                    return entry;
                }
            }
        }
        catch { /* ignore */ }
        return null;
    }

    // ==================== 打开目录 / 预览 ====================
    private static string? GetFileManager()
    {
        foreach (string fm in new[] { "dolphin", "nautilus", "nemo", "thunar", "pcmanfm", "konqueror" })
        {
            if (Which(fm) is not null) return fm;
        }
        return null;
    }

    /// <summary>用文件管理器打开目录（dolphin→nautilus→…→xdg-open）</summary>
    public static (bool Ok, string Error) OpenPath(string path)
    {
        try
        {
            if (!Directory.Exists(path) && !File.Exists(path))
            {
                return (false, $"Directory {path} does not exist");
            }
            string? fm = GetFileManager();
            string file = fm ?? Which("xdg-open") ?? "";
            if (file.Length == 0) return (false, "No file manager found");
            Process.Start(new ProcessStartInfo
            {
                FileName = file,
                Arguments = $"\"{path}\"",
                UseShellExecute = false,
            });
            return (true, "");
        }
        catch (Exception e)
        {
            return (false, e.Message);
        }
    }

    /// <summary>实时探测节点有效性（点击预览时调用，open 即 ENXIO 则节点已失效）</summary>
    public static (bool Ok, string Error) ProbeNode(string node)
    {
        int fd = open(node, O_RDONLY_NONBLOCK);
        if (fd < 0)
        {
            return (false, $"errno {Marshal.GetLastWin32Error()}");
        }
        _ = close(fd);
        return (true, "");
    }

    /// <summary>启动 UVC 预览（ffplay/mpv 独立进程，不阻塞）。返回 (是否启动成功, 错误或退出码描述)</summary>
    public static async Task<(bool Ok, string Error)> PreviewCaptureAsync(string node)
    {
        string? viewer = Which("ffplay") ?? Which("mpv");
        if (viewer is null)
        {
            return (false, "ffplay/mpv not found");
        }
        Process? proc = null;
        try
        {
            proc = Process.Start(new ProcessStartInfo
            {
                FileName = viewer,
                Arguments = $"-f v4l2 -i \"{node}\"",
                UseShellExecute = false,
            });
        }
        catch (Exception e)
        {
            return (false, e.Message);
        }
        // 短暂观察：查看器秒退（节点失效/设备忙/无显示后端）时给出提示
        await Task.Delay(1500);
        try
        {
            if (proc is { HasExited: true } && proc.ExitCode != 0)
            {
                return (false, $"viewer exited with code {proc.ExitCode}");
            }
        }
        catch { /* process object gone */ }
        return (true, "");
    }

    // ==================== 总扫描 ====================
    public static async Task<(List<UsbStorageInfo> Storage, List<UsbDeviceInfo> Others)> ScanAsync()
    {
        List<UsbStorageInfo> storage = await ScanStorageAsync();
        List<UsbDeviceInfo> others = ScanOtherUsbDevices();
        return (storage, others);
    }
}
