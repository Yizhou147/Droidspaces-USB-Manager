using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Avalonia;
using Avalonia.Media;
using Avalonia.Threading;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Material.Icons;
using SukiUI.Dialogs;
using SukiUI.Toasts;
using UotanToolbox.Common;

namespace UotanToolbox.Features.UsbManager;

/// <summary>设备列表中的一行（存储设备/分区/USB 设备/MTP 子项）</summary>
public partial class UsbRowViewModel : ObservableObject
{
    public string Name { get; set; } = "";
    public string Info { get; set; } = "";
    public string Size { get; set; } = "";
    public string Fs { get; set; } = "";
    public string Status { get; set; } = "";
    public IBrush? StatusBrush { get; set; }
    public int Indent { get; set; }
    public bool IsBold { get; set; }
    public bool IsIndented => Indent > 0;
    public ObservableCollection<UsbButtonViewModel> Buttons { get; } = [];
}

/// <summary>行内按钮（命令闭包持有行上下文）</summary>
public class UsbButtonViewModel
{
    public string Label { get; }
    public RelayCommand Command { get; }

    public UsbButtonViewModel(string label, Action action)
    {
        Label = label;
        Command = new RelayCommand(action);
    }
}

public partial class UsbManagerViewModel : MainPageBase
{
    [ObservableProperty] private bool _autoScan = true;
    [ObservableProperty] private double _intervalSeconds = 3;
    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private bool _isScanning;

    public ObservableCollection<UsbRowViewModel> Rows { get; } = [];

    private List<UsbStorageInfo> _storageDevices = [];
    private List<UsbDeviceInfo> _otherDevices = [];
    private HashSet<string> _knownDevices = [];
    private HashSet<string> _autoMountedMtp = [];
    private bool _scanBusy;   // 防重入：上一次扫描未完成则跳过，避免线程叠加
    private bool _prepBusy;   // 防重入：后台处理慢于扫描节奏时丢弃本次结果
    private bool _ejectPause; // 弹出后暂停自动挂载/扫描，点刷新恢复
    private DispatcherTimer? _timer;

    private static string GetTranslation(string key) => FeaturesHelper.GetTranslation(key);

    private static string TypeKey(string type) => type switch
    {
        "hub" => "Usb_TypeHub",
        "hid" => "Usb_TypeHid",
        "audio" => "Usb_TypeAudio",
        "video" => "Usb_TypeVideo",
        "network" => "Usb_TypeNetwork",
        "storage" => "Usb_TypeStorage",
        "printer" => "Usb_TypePrinter",
        "adb" => "Usb_TypeAdb",
        "fastboot" => "Usb_TypeFastboot",
        "vendor" => "Usb_TypeVendor",
        "unknown" => "Usb_TypeUnknown",
        _ => "Usb_TypeUnknown",
    };

    private static IBrush? OkBrush(bool ok) => ok ? Brushes.Green : Brushes.Orange;

    public UsbManagerViewModel() : base(GetTranslation("Sidebar_UsbManager"), MaterialIconKind.Usb, -325)
    {
        StatusText = GetTranslation("Usb_Ready");
        if (UsbHardware.IsLinux)
        {
            _timer = new DispatcherTimer
            {
                Interval = TimeSpan.FromSeconds(IntervalSeconds),
            };
            _timer.Tick += (_, _) => _ = ScanLoopAsync();
            _timer.Start();
            _ = ScanLoopAsync();
        }
        else
        {
            StatusText = GetTranslation("Usb_ErrNotLinux");
        }
    }

    partial void OnAutoScanChanged(bool value) => UpdateTimer();
    partial void OnIntervalSecondsChanged(double value) => UpdateTimer();

    private void UpdateTimer()
    {
        if (_timer is null) return;
        if (AutoScan && !_ejectPause)
        {
            _timer.Interval = TimeSpan.FromSeconds(Math.Clamp(IntervalSeconds, 1, 60));
            if (!_timer.IsEnabled) _timer.Start();
        }
        else
        {
            _timer.Stop();
        }
    }

    [RelayCommand]
    private async Task RefreshAsync()
    {
        _ejectPause = false;
        UpdateTimer();
        await ScanLoopAsync();
    }

    /// <summary>扫描循环（防重入），后台完成扫描 + 阻塞操作后回 UI 线程渲染</summary>
    private async Task ScanLoopAsync()
    {
        if (!UsbHardware.IsLinux || _scanBusy || _prepBusy) return;
        _scanBusy = true;
        IsScanning = true;
        try
        {
            (List<UsbStorageInfo> storage, List<UsbDeviceInfo> others) =
                await Task.Run(UsbHardware.ScanAsync);

            _prepBusy = true;
            try
            {
                List<(string Name, string MountPoint)> events = await Task.Run(() => PrepareDevicesAsync(storage, others));                foreach ((string name, string mp) in events)
                {
                    ShowToast(string.Format(GetTranslation("Usb_AutoMounted"), name, mp));
                }
                await Dispatcher.UIThread.InvokeAsync(() => RenderRows(storage, others));
            }
            finally
            {
                _prepBusy = false;
            }
        }
        catch
        {
            // 扫描异常不应中断自动刷新循环
        }
        finally
        {
            _scanBusy = false;
            IsScanning = false;
        }
    }

    /// <summary>后台线程：集中执行所有阻塞操作（清理/自动挂载/ADB 节点/MTP/UVC），返回自动挂载事件</summary>
    private async Task<List<(string Name, string MountPoint)>> PrepareDevicesAsync(
        List<UsbStorageInfo> storage, List<UsbDeviceInfo> others)
    {
        List<(string, string)> events = [];
        await UsbHardware.CleanupMountPointsAsync();

        if (!_ejectPause)
        {
            // 1) 存储分区自动挂载（仅对首次出现且未挂载的分区）
            foreach (UsbStorageInfo device in storage)
            {
                foreach (UsbPartitionInfo part in device.Partitions)
                {
                    if (!part.Mounted && !_knownDevices.Contains(part.Node))
                    {
                        (bool ok, _) = UsbHardware.MountPartitionAsync(part).Result;
                        if (ok && part.MountPoint.Length > 0)
                        {
                            events.Add((part.Name, part.MountPoint));
                        }
                    }
                }
            }

            // 2) ADB/Fastboot 设备节点自动创建 + UVC 节点校正 + MTP 检测与自动挂载
            foreach (UsbDeviceInfo device in others)
            {
                if ((device.Type == "adb" || device.Type == "fastboot") && !device.NodeExists)
                {
                    device.NodeExists = UsbHardware.RunPassthroughAsync().Result;
                }
                if (device.Type == "video")
                {
                    device.V4lReadyNode = UsbHardware.EnsureVideoNodesAsync(device).Result;
                }
                if (device.HasMtp)
                {
                    device.MtpMounted = UsbHardware.IsMtpMountedAsync(device).Result;
                    if (!device.MtpMounted)
                    {
                        string mtpKey = $"{device.Busnum}:{device.Devnum}";
                        if (!_autoMountedMtp.Contains(mtpKey))
                        {
                            _autoMountedMtp.Add(mtpKey);
                            (bool ok, _) = UsbHardware.MountMtpAsync(device).Result;
                            device.MtpMounted = ok;
                        }
                    }
                }
            }
        }
        return events;
    }

    /// <summary>UI 线程：纯渲染，重建设备列表</summary>
    private void RenderRows(List<UsbStorageInfo> storage, List<UsbDeviceInfo> others)
    {
        Rows.Clear();
        HashSet<string> current = [];

        int totalMounted = 0;
        foreach (UsbStorageInfo device in storage)
        {
            current.Add(device.Node);
            UsbRowViewModel devRow = new()
            {
                Name = $"{device.Model} ({device.Vendor})",
                Info = device.Node,
                Size = $"{device.SizeGb} GB",
                Fs = "",
                Status = GetTranslation("Usb_Connected"),
                StatusBrush = OkBrush(true),
                IsBold = true,
            };
            Rows.Add(devRow);

            foreach (UsbPartitionInfo part in device.Partitions)
            {
                current.Add(part.Node);
                UsbRowViewModel partRow = new()
                {
                    Name = part.Name,
                    Info = part.Node,
                    Size = $"{part.SizeGb} GB",
                    Fs = part.FsType.Length > 0 ? part.FsType : GetTranslation("Usb_Unknown"),
                    Status = part.Mounted ? GetTranslation("Usb_Mounted") : GetTranslation("Usb_Unmounted"),
                    StatusBrush = OkBrush(part.Mounted),
                    Indent = 1,
                };
                if (part.Mounted)
                {
                    totalMounted++;
                    partRow.Buttons.Add(new UsbButtonViewModel(GetTranslation("Usb_Open"),
                        () => _ = OpenDirectoryAsync(part.MountPoint)));
                    partRow.Buttons.Add(new UsbButtonViewModel(GetTranslation("Usb_Eject"),
                        () => _ = EjectPartitionAsync(part)));
                }
                else
                {
                    partRow.Buttons.Add(new UsbButtonViewModel(GetTranslation("Usb_Mount"),
                        () => _ = MountPartitionAsync(part)));
                }
                Rows.Add(partRow);
            }
        }

        foreach (UsbDeviceInfo device in others)
        {
            current.Add(device.Node);
            string typeText = GetTranslation(TypeKey(device.Type));
            UsbRowViewModel devRow = new()
            {
                Name = $"{device.Name} [{typeText}]",
                Info = $"{device.VendorId}:{device.ProductId}",
                Size = "",
                Fs = $"USB {device.DevClass}",
                IsBold = true,
            };

            if (device.Type == "video")
            {
                if (device.V4lReadyNode.Length > 0)
                {
                    devRow.Status = GetTranslation("Usb_Ready");
                    devRow.StatusBrush = OkBrush(true);
                    string node = device.V4lReadyNode;
                    devRow.Buttons.Add(new UsbButtonViewModel(GetTranslation("Usb_Preview"),
                        () => _ = PreviewAsync(node)));
                }
                else
                {
                    devRow.Status = GetTranslation("Usb_Disconnected");
                    devRow.StatusBrush = OkBrush(false);
                }
            }
            else if (device.NodeExists)
            {
                devRow.Status = GetTranslation("Usb_Connected");
                devRow.StatusBrush = OkBrush(true);
            }
            else
            {
                devRow.Status = GetTranslation("Usb_Disconnected");
                devRow.StatusBrush = OkBrush(false);
                devRow.Buttons.Add(new UsbButtonViewModel(GetTranslation("Usb_Connect"),
                    () => _ = ConnectAdbAsync()));
            }
            Rows.Add(devRow);

            if (device.HasMtp)
            {
                UsbRowViewModel mtpRow = new()
                {
                    Name = GetTranslation("Usb_MtpStorage"),
                    Info = "MTP",
                    Fs = "MTP",
                    Status = device.MtpMounted ? GetTranslation("Usb_Mounted") : GetTranslation("Usb_Unmounted"),
                    StatusBrush = OkBrush(device.MtpMounted),
                    Indent = 1,
                };
                if (device.MtpMounted)
                {
                    mtpRow.Buttons.Add(new UsbButtonViewModel(GetTranslation("Usb_Open"),
                        () => _ = OpenMtpAsync(device)));
                    mtpRow.Buttons.Add(new UsbButtonViewModel(GetTranslation("Usb_Eject"),
                        () => _ = UnmountMtpAsync(device)));
                }
                else
                {
                    mtpRow.Buttons.Add(new UsbButtonViewModel(GetTranslation("Usb_Mount"),
                        () => _ = MountMtpAsync(device)));
                }
                Rows.Add(mtpRow);
            }
        }

        _knownDevices = current;

        List<string> parts2 = [];
        if (storage.Count > 0) parts2.Add(string.Format(GetTranslation("Usb_StatusStorage"), storage.Count));
        if (others.Count > 0) parts2.Add(string.Format(GetTranslation("Usb_StatusOther"), others.Count));
        if (totalMounted > 0) parts2.Add(string.Format(GetTranslation("Usb_StatusMounted"), totalMounted));
        StatusText = parts2.Count > 0
            ? string.Format(GetTranslation("Usb_Detected"), string.Join(", ", parts2))
            : GetTranslation("Usb_NoDevice");
    }

    // ==================== 行操作 ====================
    private void ShowError(string text)
    {
        Global.MainDialogManager.CreateDialog()
            .WithTitle(GetTranslation("Usb_ErrTitle"))
            .OfType(Avalonia.Controls.Notifications.NotificationType.Error)
            .WithContent(text)
            .Dismiss().ByClickingBackground()
            .TryShow();
    }

    private void ShowToast(string text)
    {
        Global.MainToastManager.CreateToast()
            .WithTitle(GetTranslation("Sidebar_UsbManager"))
            .WithContent(text)
            .OfType(Avalonia.Controls.Notifications.NotificationType.Success)
            .Dismiss().ByClicking()
            .Dismiss().After(TimeSpan.FromSeconds(3))
            .Queue();
    }

    private async Task MountPartitionAsync(UsbPartitionInfo part)
    {
        IsScanning = true;
        (bool ok, string err) = await Task.Run(() => UsbHardware.MountPartitionAsync(part));
        IsScanning = false;
        if (!ok) ShowError(string.Format(GetTranslation("Usb_ErrMount"), err));
        await ScanLoopAsync();
    }

    private async Task EjectPartitionAsync(UsbPartitionInfo part)
    {
        IsScanning = true;
        (bool ok, string err) = await Task.Run(() => UsbHardware.EjectPartitionAsync(part));
        IsScanning = false;
        if (!ok)
        {
            ShowError(string.Format(GetTranslation("Usb_ErrEject"), err));
        }
        else
        {
            _ejectPause = true;
            UpdateTimer();
            ShowToast(string.Format(GetTranslation("Usb_Ejected"), part.Name));
        }
        await ScanLoopAsync();
    }

    private async Task ConnectAdbAsync()
    {
        IsScanning = true;
        bool ok = await Task.Run(UsbHardware.RunPassthroughAsync);
        IsScanning = false;
        if (!ok) ShowError(GetTranslation("Usb_ErrScriptMissing").Replace("{0}", "usb-passthrough.sh"));
        await ScanLoopAsync();
    }

    private async Task OpenDirectoryAsync(string path)
    {
        (bool ok, string err) = await Task.Run(() => UsbHardware.OpenPath(path));
        if (!ok) ShowError(string.Format(GetTranslation("Usb_ErrOpenDir"), err));
    }

    private async Task MountMtpAsync(UsbDeviceInfo device)
    {
        IsScanning = true;
        (bool ok, string err) = await Task.Run(() => UsbHardware.MountMtpAsync(device));
        IsScanning = false;
        if (!ok) ShowError(string.Format(GetTranslation("Usb_ErrMtpMount"), err));
        await ScanLoopAsync();
    }

    private async Task UnmountMtpAsync(UsbDeviceInfo device)
    {
        IsScanning = true;
        (bool ok, string err) = await Task.Run(() => UsbHardware.UnmountMtpAsync(device));
        IsScanning = false;
        if (!ok) ShowError(string.Format(GetTranslation("Usb_ErrMtpUnmount"), err));
        else ShowToast(GetTranslation("Usb_MtpUnmounted"));
        await ScanLoopAsync();
    }

    private async Task OpenMtpAsync(UsbDeviceInfo device)
    {
        await Task.Run(() => UsbHardware.EnsureGvfsFuse());
        string? localPath = await Task.Run(() => UsbHardware.GetGvfsMtpPath(device));
        if (localPath is null)
        {
            ShowError(GetTranslation("Usb_ErrMtpNotMounted"));
            return;
        }
        (bool ok, string err) = await Task.Run(() => UsbHardware.OpenPath(localPath));
        if (!ok) ShowError(string.Format(GetTranslation("Usb_ErrOpenDir"), err));
    }

    private async Task PreviewAsync(string node)
    {
        (bool probe, string probeErr) = await Task.Run(() => UsbHardware.ProbeNode(node));
        if (!probe)
        {
            ShowError(string.Format(GetTranslation("Usb_ErrPreview"), probeErr));
            await ScanLoopAsync();
            return;
        }
        (bool ok, string err) = await Task.Run(() => UsbHardware.PreviewCaptureAsync(node));
        if (!ok)
        {
            ShowError(string.Format(GetTranslation("Usb_ErrPreview"), err));
        }
    }
}
