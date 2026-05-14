#Requires -Version 5.1
<#
.SYNOPSIS
    Windows Utility Menu - Interactive console toolkit
.DESCRIPTION
    A self-contained PowerShell utility menu covering disk, users,
    network, processes, services, system info, gaming/GPU, battery,
    Wi-Fi, firewall, shares, scheduled tasks, temp cleanup, and more.
.NOTES
    Run with:  powershell -ExecutionPolicy Bypass -File WinUtilMenu.ps1
    Some items require an elevated (Admin) session.
#>

# -----------------------------------------------
#  Helpers
# -----------------------------------------------
function Is-Admin {
    ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Pause-Menu {
    Write-Host ""
    Write-Host "Press any key to return to menu..." -ForegroundColor DarkGray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

function Write-Header {
    param([string]$Title)
    $width = 60
    $line  = "-" * $width
    Write-Host ""
    Write-Host $line -ForegroundColor Cyan
    Write-Host ("  " + $Title.ToUpper()) -ForegroundColor White
    Write-Host $line -ForegroundColor Cyan
}

function Format-Bytes {
    param([long]$Bytes)
    switch ($Bytes) {
        { $_ -ge 1TB } { return "{0:N2} TB" -f ($_ / 1TB) }
        { $_ -ge 1GB } { return "{0:N2} GB" -f ($_ / 1GB) }
        { $_ -ge 1MB } { return "{0:N2} MB" -f ($_ / 1MB) }
        default         { return "{0:N0} KB" -f ($_ / 1KB) }
    }
}

# -----------------------------------------------
#  Original Menu Functions
# -----------------------------------------------

function Show-DiskSpace {
    Write-Header "Local Disk Space"
    Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null } | ForEach-Object {
        $total = $_.Used + $_.Free
        $pct   = if ($total -gt 0) { [math]::Round(($_.Used / $total) * 100, 1) } else { 0 }
        $bar   = ("#" * [math]::Round($pct / 5)).PadRight(20)
        $color = if ($pct -gt 85) { "Red" } elseif ($pct -gt 65) { "Yellow" } else { "Green" }
        Write-Host ("{0,-6} Total: {1,-10}  Used: {2,-10}  Free: {3,-10}  [{4}] {5}%" -f `
            ($_.Name + ":"),
            (Format-Bytes $total),
            (Format-Bytes $_.Used),
            (Format-Bytes $_.Free),
            $bar,
            $pct
        ) -ForegroundColor $color
    }
    Pause-Menu
}

function Show-LocalUsers {
    Write-Header "Local User Accounts"
    try {
        Get-LocalUser | Sort-Object Name | ForEach-Object {
            $status    = if ($_.Enabled) { "Enabled " } else { "Disabled" }
            $color     = if ($_.Enabled) { "Green"   } else { "DarkGray" }
            $lastLogin = if ($_.LastLogon) { $_.LastLogon.ToString("yyyy-MM-dd HH:mm") } else { "Never" }
            Write-Host ("{0,-22} [{1}]  Last login: {2}  PwdRequired: {3}" -f `
                $_.Name, $status, $lastLogin, $_.PasswordRequired) -ForegroundColor $color
        }
    } catch {
        Write-Host "Could not retrieve local users (may need elevation)." -ForegroundColor Yellow
    }
    Pause-Menu
}

function Show-LocalGroups {
    Write-Header "Local Groups"
    try {
        Get-LocalGroup | Sort-Object Name | ForEach-Object {
            Write-Host ("{0,-30}  {1}" -f $_.Name, $_.Description) -ForegroundColor Cyan
        }
    } catch {
        Write-Host "Could not retrieve local groups." -ForegroundColor Yellow
    }
    Pause-Menu
}

function Show-SystemInfo {
    Write-Header "System Information"
    $os   = Get-CimInstance Win32_OperatingSystem
    $cs   = Get-CimInstance Win32_ComputerSystem
    $bios = Get-CimInstance Win32_BIOS
    $cpu  = Get-CimInstance Win32_Processor | Select-Object -First 1

    $uptime    = (Get-Date) - $os.LastBootUpTime
    $uptimeStr = "{0}d {1}h {2}m" -f $uptime.Days, $uptime.Hours, $uptime.Minutes

    $info = [ordered]@{
        "Computer Name"   = $cs.Name
        "Domain / WG"     = if ($cs.PartOfDomain) { $cs.Domain } else { $cs.Workgroup + " (Workgroup)" }
        "OS"              = $os.Caption
        "Build"           = $os.BuildNumber
        "Architecture"    = $os.OSArchitecture
        "CPU"             = $cpu.Name.Trim()
        "CPU Cores"       = "$($cpu.NumberOfCores) cores / $($cpu.NumberOfLogicalProcessors) logical"
        "RAM (Total)"     = Format-Bytes ($cs.TotalPhysicalMemory)
        "RAM (Available)" = Format-Bytes ($os.FreePhysicalMemory * 1KB)
        "BIOS Version"    = $bios.SMBIOSBIOSVersion
        "Last Boot"       = $os.LastBootUpTime.ToString("yyyy-MM-dd HH:mm:ss")
        "Uptime"          = $uptimeStr
        "Current User"    = "$env:USERDOMAIN\$env:USERNAME"
        "PS Version"      = $PSVersionTable.PSVersion.ToString()
    }

    foreach ($key in $info.Keys) {
        Write-Host ("{0,-22}: " -f $key) -ForegroundColor DarkCyan -NoNewline
        Write-Host $info[$key]
    }
    Pause-Menu
}

function Show-NetworkInfo {
    Write-Header "Network Adapters and IP Info"
    Get-NetIPConfiguration | Where-Object { $_.IPv4Address } | ForEach-Object {
        Write-Host ""
        Write-Host "  Adapter : " -ForegroundColor DarkCyan -NoNewline
        Write-Host $_.InterfaceAlias
        Write-Host "  IPv4    : " -ForegroundColor DarkCyan -NoNewline
        Write-Host ($_.IPv4Address.IPAddress -join ", ")
        Write-Host "  Gateway : " -ForegroundColor DarkCyan -NoNewline
        Write-Host ($_.IPv4DefaultGateway.NextHop -join ", ")
        Write-Host "  DNS     : " -ForegroundColor DarkCyan -NoNewline
        Write-Host ($_.DNSServer.ServerAddresses -join ", ")
    }
    Write-Host ""
    Write-Host "  Public IP : " -ForegroundColor DarkCyan -NoNewline
    try {
        $pub = (Invoke-RestMethod -Uri "https://api.ipify.org?format=json" -TimeoutSec 5).ip
        Write-Host $pub
    } catch {
        Write-Host "(unavailable)"
    }
    Pause-Menu
}

function Show-OpenPorts {
    Write-Header "Active TCP Connections / Listening Ports"
    Write-Host ("{0,-14} {1,-26} {2,-26} {3}" -f "State","Local","Remote","PID") -ForegroundColor DarkYellow
    Write-Host ("-" * 72) -ForegroundColor DarkGray
    Get-NetTCPConnection | Where-Object { $_.State -in "Listen","Established" } |
        Sort-Object LocalPort | Select-Object -First 40 | ForEach-Object {
            $color = if ($_.State -eq "Listen") { "Yellow" } else { "Green" }
            Write-Host ("{0,-14} {1,-26} {2,-26} {3}" -f `
                $_.State,
                "$($_.LocalAddress):$($_.LocalPort)",
                "$($_.RemoteAddress):$($_.RemotePort)",
                $_.OwningProcess
            ) -ForegroundColor $color
        }
    Pause-Menu
}

function Show-TopProcesses {
    Write-Header "Top 20 Processes by CPU / Memory"
    Write-Host ("{0,-8} {1,-40} {2,-10} {3}" -f "PID","Name","CPU(s)","Mem (MB)") -ForegroundColor DarkYellow
    Write-Host ("-" * 72) -ForegroundColor DarkGray
    Get-Process | Sort-Object CPU -Descending | Select-Object -First 20 | ForEach-Object {
        $name = $_.Name
        if ($name.Length -gt 38) { $name = $name.Substring(0,38) + ".." }
        Write-Host ("{0,-8} {1,-40} {2,-10} {3}" -f `
            $_.Id,
            $name,
            [math]::Round($_.CPU, 1),
            [math]::Round($_.WorkingSet64 / 1MB, 1)
        )
    }
    Pause-Menu
}

function Show-Services {
    Write-Header "Services - Running / Stopped"
    $svcs    = Get-Service | Sort-Object Status, DisplayName
    $running = $svcs | Where-Object { $_.Status -eq "Running" }
    $stopped = $svcs | Where-Object { $_.Status -ne "Running" }

    Write-Host "  RUNNING ($($running.Count))" -ForegroundColor Green
    $running | ForEach-Object {
        Write-Host ("    {0,-45} {1}" -f $_.DisplayName, $_.Name) -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "  STOPPED / OTHER ($($stopped.Count))" -ForegroundColor DarkGray
    $stopped | Select-Object -First 30 | ForEach-Object {
        Write-Host ("    {0,-45} {1}" -f $_.DisplayName, $_.Name) -ForegroundColor DarkGray
    }
    if ($stopped.Count -gt 30) {
        Write-Host "    ... and $($stopped.Count - 30) more." -ForegroundColor DarkGray
    }
    Pause-Menu
}

function Show-StartupItems {
    Write-Header "Startup Programs (Registry)"
    $paths = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    )
    foreach ($path in $paths) {
        Write-Host ""
        Write-Host "  $path" -ForegroundColor DarkCyan
        try {
            $props = Get-ItemProperty -Path $path -ErrorAction Stop
            $props.PSObject.Properties |
                Where-Object { $_.Name -notlike "PS*" } |
                ForEach-Object {
                    Write-Host ("    {0,-35} {1}" -f $_.Name, $_.Value)
                }
        } catch {
            Write-Host "    (empty or inaccessible)" -ForegroundColor DarkGray
        }
    }
    Pause-Menu
}

function Show-InstalledSoftware {
    Write-Header "Installed Software (top 50 by name)"
    $keys = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    $apps = Get-ItemProperty $keys -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName } |
        Select-Object DisplayName, DisplayVersion, Publisher |
        Sort-Object DisplayName -Unique |
        Select-Object -First 50

    Write-Host ("{0,-50} {1,-20} {2}" -f "Name","Version","Publisher") -ForegroundColor DarkYellow
    Write-Host ("-" * 90) -ForegroundColor DarkGray
    $apps | ForEach-Object {
        $name = $_.DisplayName
        if ($name.Length -gt 48) { $name = $name.Substring(0,48) + ".." }
        Write-Host ("{0,-50} {1,-20} {2}" -f $name, $_.DisplayVersion, $_.Publisher)
    }
    Pause-Menu
}

function Show-EventLog {
    Write-Header "Recent System / Application Errors (last 24h)"
    $since = (Get-Date).AddHours(-24)
    foreach ($log in "System","Application") {
        Write-Host ""
        Write-Host "  -- $log Log --" -ForegroundColor DarkCyan
        try {
            Get-EventLog -LogName $log -EntryType Error,Warning -After $since -Newest 15 |
                ForEach-Object {
                    $color = if ($_.EntryType -eq "Error") { "Red" } else { "Yellow" }
                    $msg   = $_.Message -replace "\s+"," "
                    if ($msg.Length -gt 80) { $msg = $msg.Substring(0,80) + ".." }
                    Write-Host ("  {0}  [{1,-8}]  {2}" -f `
                        $_.TimeGenerated.ToString("MM-dd HH:mm"), $_.EntryType, $msg
                    ) -ForegroundColor $color
                }
        } catch {
            Write-Host "  (Unable to read log)" -ForegroundColor DarkGray
        }
    }
    Pause-Menu
}

function Show-WindowsUpdates {
    Write-Header "Installed Windows Updates (last 10)"
    try {
        $sess     = New-Object -ComObject Microsoft.Update.Session
        $searcher = $sess.CreateUpdateSearcher()
        $count    = $searcher.GetTotalHistoryCount()
        $history  = $searcher.QueryHistory(0, [math]::Min($count, 10))
        foreach ($u in $history) {
            $date = $u.Date.ToString("yyyy-MM-dd")
            Write-Host ("{0}  {1}" -f $date, $u.Title) -ForegroundColor Cyan
        }
    } catch {
        Write-Host "Could not query Windows Update history." -ForegroundColor Yellow
    }
    Pause-Menu
}

function Show-EnvVars {
    Write-Header "Environment Variables"
    [System.Environment]::GetEnvironmentVariables().Keys | Sort-Object | ForEach-Object {
        $val = [System.Environment]::GetEnvironmentVariable($_)
        Write-Host ("{0,-30} " -f $_) -ForegroundColor DarkCyan -NoNewline
        Write-Host $val
    }
    Pause-Menu
}

function Flush-DNS {
    Write-Header "Flush DNS Cache"
    if (Is-Admin) {
        ipconfig /flushdns
    } else {
        Write-Host "Elevation required. Relaunching flush via RunAs..." -ForegroundColor Yellow
        Start-Process powershell -Verb RunAs -ArgumentList "-Command ipconfig /flushdns; pause" -Wait
    }
    Pause-Menu
}

function Test-Connectivity {
    Write-Header "Connectivity Check"
    $targets = @(
        @{ Host = "8.8.8.8";       Label = "Google DNS"     },
        @{ Host = "1.1.1.1";       Label = "Cloudflare DNS" },
        @{ Host = "google.com";    Label = "google.com"     },
        @{ Host = "microsoft.com"; Label = "microsoft.com"  }
    )
    foreach ($t in $targets) {
        $ok     = Test-Connection -ComputerName $t.Host -Count 2 -Quiet -ErrorAction SilentlyContinue
        $symbol = if ($ok) { "[OK]  " } else { "[FAIL]" }
        $color  = if ($ok) { "Green" } else { "Red"   }
        Write-Host ("  {0}  {1,-16} {2}" -f $symbol, $t.Host, $t.Label) -ForegroundColor $color
    }
    Pause-Menu
}

# -----------------------------------------------
#  New Menu Functions
# -----------------------------------------------

function Show-GPU {
    Write-Header "GPU / Display Info"
    $gpus = Get-CimInstance Win32_VideoController
    foreach ($g in $gpus) {
        $vram = if ($g.AdapterRAM) { Format-Bytes ([long]$g.AdapterRAM) } else { "N/A" }
        Write-Host ""
        Write-Host "  Name         : " -ForegroundColor DarkCyan -NoNewline; Write-Host $g.Name
        Write-Host "  VRAM         : " -ForegroundColor DarkCyan -NoNewline; Write-Host $vram
        Write-Host "  Driver Ver   : " -ForegroundColor DarkCyan -NoNewline; Write-Host $g.DriverVersion
        Write-Host "  Driver Date  : " -ForegroundColor DarkCyan -NoNewline; Write-Host $g.DriverDate
        Write-Host "  Resolution   : " -ForegroundColor DarkCyan -NoNewline
        Write-Host "$($g.CurrentHorizontalResolution) x $($g.CurrentVerticalResolution) @ $($g.CurrentRefreshRate) Hz"
        Write-Host "  Status       : " -ForegroundColor DarkCyan -NoNewline
        $col = if ($g.Status -eq "OK") { "Green" } else { "Red" }
        Write-Host $g.Status -ForegroundColor $col
    }

    Write-Host ""
    Write-Host "  -- Connected Monitors --" -ForegroundColor DarkCyan
    try {
        Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID | ForEach-Object {
            $mfr  = [System.Text.Encoding]::ASCII.GetString($_.ManufacturerName -ne 0)
            $prod = [System.Text.Encoding]::ASCII.GetString($_.ProductCodeID   -ne 0)
            Write-Host ("    {0} {1}" -f $mfr.Trim(), $prod.Trim())
        }
    } catch {
        Write-Host "    (Unable to query monitor info)" -ForegroundColor DarkGray
    }
    Pause-Menu
}

function Show-Battery {
    Write-Header "Battery Status"
    $bat = Get-CimInstance Win32_Battery
    if (-not $bat) {
        Write-Host "  No battery detected (desktop or battery not reporting)." -ForegroundColor Yellow
    } else {
        foreach ($b in $bat) {
            $statusMap = @{1="Discharging"; 2="AC Power (plugged in)"; 3="Fully Charged";
                           4="Low"; 5="Critical"; 6="Charging"; 7="Charging/High";
                           8="Charging/Low"; 9="Charging/Critical"; 10="Undefined"; 11="Partially Charged"}
            $statusStr = if ($statusMap.ContainsKey([int]$b.BatteryStatus)) { $statusMap[[int]$b.BatteryStatus] } else { "Unknown" }
            $pct       = $b.EstimatedChargeRemaining
            $bar       = ("#" * [math]::Round($pct / 5)).PadRight(20)
            $color     = if ($pct -lt 20) { "Red" } elseif ($pct -lt 40) { "Yellow" } else { "Green" }
            $runtime   = if ($b.EstimatedRunTime -and $b.EstimatedRunTime -lt 71582) {
                             "{0}h {1}m" -f [math]::Floor($b.EstimatedRunTime/60), ($b.EstimatedRunTime % 60)
                         } else { "N/A" }

            Write-Host ""
            Write-Host "  Charge       : " -ForegroundColor DarkCyan -NoNewline
            Write-Host ("[{0}] {1}%" -f $bar, $pct) -ForegroundColor $color
            Write-Host "  Status       : " -ForegroundColor DarkCyan -NoNewline; Write-Host $statusStr
            Write-Host "  Est. Runtime : " -ForegroundColor DarkCyan -NoNewline; Write-Host $runtime
            Write-Host "  Chemistry    : " -ForegroundColor DarkCyan -NoNewline; Write-Host $b.Chemistry
            Write-Host "  Design Cap.  : " -ForegroundColor DarkCyan -NoNewline; Write-Host "$($b.DesignCapacity) mWh"
        }
    }

    Write-Host ""
    Write-Host "  -- Power Plan --" -ForegroundColor DarkCyan
    $plan = powercfg /getactivescheme 2>$null
    Write-Host "  $plan"
    Pause-Menu
}

function Show-WiFiNetworks {
    Write-Header "Wi-Fi - Saved Profiles and Signal"
    Write-Host "  -- Saved Wi-Fi Profiles --" -ForegroundColor DarkCyan
    try {
        $profiles = netsh wlan show profiles 2>$null
        $profiles | Select-String "All User Profile" | ForEach-Object {
            $ssid = ($_ -split ":")[1].Trim()
            Write-Host ("    {0}" -f $ssid) -ForegroundColor Cyan
        }
    } catch {
        Write-Host "    (Unable to query Wi-Fi profiles)" -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  -- Current Connection --" -ForegroundColor DarkCyan
    try {
        $iface = netsh wlan show interfaces 2>$null
        $iface | Select-String "SSID|Signal|Radio|Channel|Receive rate|Transmit rate" | ForEach-Object {
            Write-Host ("    {0}" -f $_.Line.Trim())
        }
    } catch {
        Write-Host "    (Not connected or Wi-Fi unavailable)" -ForegroundColor DarkGray
    }
    Pause-Menu
}

function Show-Firewall {
    Write-Header "Windows Firewall Status"
    try {
        $profiles = Get-NetFirewallProfile
        foreach ($p in $profiles) {
            $color = if ($p.Enabled) { "Green" } else { "Red" }
            $state = if ($p.Enabled) { "ENABLED " } else { "DISABLED" }
            Write-Host ("  {0,-12} [{1}]  Inbound: {2,-12}  Outbound: {3}" -f `
                $p.Name, $state, $p.DefaultInboundAction, $p.DefaultOutboundAction
            ) -ForegroundColor $color
        }
    } catch {
        Write-Host "  Could not query firewall (needs elevation)." -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "  -- Custom Firewall Rules (enabled, non-default) --" -ForegroundColor DarkCyan
    try {
        Get-NetFirewallRule | Where-Object { $_.Enabled -eq "True" -and $_.DisplayGroup -eq "" } |
            Select-Object -First 20 | ForEach-Object {
                $dir   = if ($_.Direction -eq "Inbound") { "IN " } else { "OUT" }
                $color = if ($_.Action -eq "Allow") { "Green" } else { "Red" }
                Write-Host ("    [{0}] {1,-10} {2}" -f $dir, $_.Action, $_.DisplayName) -ForegroundColor $color
            }
    } catch {
        Write-Host "    (Unable to list rules)" -ForegroundColor DarkGray
    }
    Pause-Menu
}

function Show-SharedFolders {
    Write-Header "Shared Folders and Drives"
    Write-Host "  -- Network Shares --" -ForegroundColor DarkCyan
    try {
        Get-SmbShare | Sort-Object Name | ForEach-Object {
            $color = if ($_.Name -match "^\w+\$") { "DarkGray" } else { "Cyan" }
            Write-Host ("  {0,-20} {1,-40} {2}" -f $_.Name, $_.Path, $_.Description) -ForegroundColor $color
        }
    } catch {
        Write-Host "  (Unable to query shares)" -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  -- Mapped Network Drives --" -ForegroundColor DarkCyan
    $mapped = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.DisplayRoot -like "\\*" }
    if ($mapped) {
        $mapped | ForEach-Object {
            Write-Host ("  {0,-6} -> {1}" -f ($_.Name + ":"), $_.DisplayRoot) -ForegroundColor Cyan
        }
    } else {
        Write-Host "  (No mapped drives)" -ForegroundColor DarkGray
    }
    Pause-Menu
}

function Show-ScheduledTasks {
    Write-Header "Scheduled Tasks - Active (non-Microsoft)"
    try {
        Get-ScheduledTask | Where-Object {
            $_.TaskPath -notlike "\Microsoft\*" -and $_.State -ne "Disabled"
        } | Sort-Object TaskName | Select-Object -First 40 | ForEach-Object {
            $color = switch ($_.State) {
                "Running" { "Green"  }
                "Ready"   { "Cyan"   }
                default   { "DarkGray" }
            }
            $path = $_.TaskPath + $_.TaskName
            if ($path.Length -gt 55) { $path = $path.Substring(0,55) + ".." }
            Write-Host ("  {0,-12} {1}" -f $_.State, $path) -ForegroundColor $color
        }
    } catch {
        Write-Host "  (Unable to query scheduled tasks)" -ForegroundColor DarkGray
    }
    Pause-Menu
}

function Clear-TempFiles {
    Write-Header "Temp File Cleanup"
    $locations = @(
        $env:TEMP,
        $env:TMP,
        "C:\Windows\Temp"
    )

    $totalFreed = 0L
    foreach ($loc in $locations | Select-Object -Unique) {
        if (-not (Test-Path $loc)) { continue }
        Write-Host ""
        Write-Host "  Scanning: $loc" -ForegroundColor DarkCyan
        $files = Get-ChildItem -Path $loc -Recurse -Force -ErrorAction SilentlyContinue
        $size  = ($files | Measure-Object -Property Length -Sum).Sum
        $count = $files.Count
        Write-Host ("  Found {0} items ({1})" -f $count, (Format-Bytes ([long]$size)))

        Write-Host "  Delete these? [Y/N]: " -ForegroundColor Yellow -NoNewline
        $ans = (Read-Host).Trim().ToUpper()
        if ($ans -eq "Y") {
            $removed = 0L
            $files | ForEach-Object {
                try {
                    $removed += $_.Length
                    Remove-Item $_.FullName -Force -Recurse -ErrorAction SilentlyContinue
                } catch {}
            }
            $totalFreed += $removed
            Write-Host ("  Freed: {0}" -f (Format-Bytes ([long]$removed))) -ForegroundColor Green
        } else {
            Write-Host "  Skipped." -ForegroundColor DarkGray
        }
    }

    Write-Host ""
    Write-Host ("  Total freed this session: {0}" -f (Format-Bytes $totalFreed)) -ForegroundColor Green
    Pause-Menu
}

function Show-PingSweep {
    Write-Header "Local Network Ping Sweep"
    $localIP = (Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
        Select-Object -First 1).IPAddress

    if (-not $localIP) {
        Write-Host "  Could not determine local IP." -ForegroundColor Yellow
        Pause-Menu
        return
    }

    $subnet = ($localIP -split "\.")[0..2] -join "."
    Write-Host "  Local IP : $localIP" -ForegroundColor DarkCyan
    Write-Host "  Sweeping : $subnet.1 - $subnet.254 (this may take ~30 sec)" -ForegroundColor DarkCyan
    Write-Host ""

    $jobs = 1..254 | ForEach-Object {
        $ip = "$subnet.$_"
        Start-Job -ScriptBlock {
            param($ip)
            $ok = Test-Connection -ComputerName $ip -Count 1 -Quiet -ErrorAction SilentlyContinue
            if ($ok) { $ip }
        } -ArgumentList $ip
    }

    $results = $jobs | Wait-Job | Receive-Job
    $jobs | Remove-Job -Force

    $alive = $results | Where-Object { $_ } | Sort-Object { [version]$_ }
    if ($alive) {
        Write-Host "  Hosts responding:" -ForegroundColor Green
        foreach ($ip in $alive) {
            $hostname = try { [System.Net.Dns]::GetHostEntry($ip).HostName } catch { "unknown" }
            Write-Host ("    {0,-18} {1}" -f $ip, $hostname) -ForegroundColor Green
        }
    } else {
        Write-Host "  No hosts responded." -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host ("  {0} host(s) found on {1}.x" -f $alive.Count, $subnet) -ForegroundColor Cyan
    Pause-Menu
}

function Show-SecurityInfo {
    Write-Header "Security - TPM / Secure Boot / Defender"

    Write-Host "  -- TPM --" -ForegroundColor DarkCyan
    try {
        $tpm = Get-WmiObject -Namespace "root\cimv2\security\microsofttpm" -Class Win32_Tpm -ErrorAction Stop
        if ($tpm) {
            Write-Host ("  Present      : Yes") -ForegroundColor Green
            Write-Host ("  Spec Version : {0}" -f ($tpm.SpecVersion -split ",")[0])
            Write-Host ("  Enabled      : {0}" -f $tpm.IsEnabled_InitialValue)
            Write-Host ("  Activated    : {0}" -f $tpm.IsActivated_InitialValue)
        } else {
            Write-Host "  TPM not found." -ForegroundColor Red
        }
    } catch {
        Write-Host "  TPM not found or access denied." -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "  -- Secure Boot --" -ForegroundColor DarkCyan
    try {
        $sb = Confirm-SecureBootUEFI -ErrorAction Stop
        $color = if ($sb) { "Green" } else { "Red" }
        Write-Host ("  Secure Boot  : {0}" -f $(if ($sb) { "ENABLED" } else { "DISABLED" })) -ForegroundColor $color
    } catch {
        Write-Host "  Secure Boot  : Not supported or not UEFI" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "  -- Windows Defender --" -ForegroundColor DarkCyan
    try {
        $def = Get-MpComputerStatus -ErrorAction Stop
        $avColor  = if ($def.AntivirusEnabled)      { "Green" } else { "Red" }
        $fwColor  = if ($def.IsTamperProtected)     { "Green" } else { "Yellow" }
        $rtColor  = if ($def.RealTimeProtectionEnabled) { "Green" } else { "Red" }
        Write-Host ("  Antivirus    : {0}" -f $(if ($def.AntivirusEnabled) { "Enabled" } else { "Disabled" })) -ForegroundColor $avColor
        Write-Host ("  Real-Time    : {0}" -f $(if ($def.RealTimeProtectionEnabled) { "Enabled" } else { "Disabled" })) -ForegroundColor $rtColor
        Write-Host ("  Tamper Prot  : {0}" -f $(if ($def.IsTamperProtected) { "Enabled" } else { "Disabled" })) -ForegroundColor $fwColor
        Write-Host ("  AV Sig Date  : {0}" -f $def.AntivirusSignatureLastUpdated.ToString("yyyy-MM-dd"))
        Write-Host ("  Last Scan    : {0}" -f $def.QuickScanEndTime.ToString("yyyy-MM-dd HH:mm"))
    } catch {
        Write-Host "  Could not query Defender status." -ForegroundColor DarkGray
    }
    Pause-Menu
}

function Show-DiskHealth {
    Write-Header "Disk Health (SMART via WMI)"
    try {
        $disks = Get-WmiObject -Namespace root\wmi -Class MSStorageDriver_FailurePredictStatus -ErrorAction Stop
        foreach ($d in $disks) {
            $color  = if (-not $d.PredictFailure) { "Green" } else { "Red" }
            $status = if (-not $d.PredictFailure) { "OK - No failure predicted" } else { "WARNING - Failure predicted!" }
            Write-Host ("  {0,-50} {1}" -f $d.InstanceName, $status) -ForegroundColor $color
        }
    } catch {
        Write-Host "  SMART data unavailable via WMI." -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  -- Physical Disk Info --" -ForegroundColor DarkCyan
    Get-PhysicalDisk | ForEach-Object {
        $health = $_.HealthStatus
        $color  = if ($health -eq "Healthy") { "Green" } elseif ($health -eq "Warning") { "Yellow" } else { "Red" }
        Write-Host ("  {0,-30} {1,-12} {2,-10} {3}" -f `
            $_.FriendlyName,
            (Format-Bytes ([long]$_.Size)),
            $_.MediaType,
            $health
        ) -ForegroundColor $color
    }
    Pause-Menu
}

function Show-RecentFiles {
    Write-Header "Recently Modified Files (last 24h)"
    $since = (Get-Date).AddHours(-24)
    $paths = @($env:USERPROFILE + "\Documents", $env:USERPROFILE + "\Desktop",
               $env:USERPROFILE + "\Downloads")

    foreach ($p in $paths) {
        if (-not (Test-Path $p)) { continue }
        Write-Host ""
        Write-Host "  $p" -ForegroundColor DarkCyan
        Get-ChildItem -Path $p -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -gt $since } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 10 |
            ForEach-Object {
                Write-Host ("    {0}  {1,-12}  {2}" -f `
                    $_.LastWriteTime.ToString("MM-dd HH:mm"),
                    (Format-Bytes $_.Length),
                    $_.Name)
            }
    }
    Pause-Menu
}

function Show-USBDevices {
    Write-Header "Connected USB Devices"

    Write-Host "  -- USB Hubs and Controllers --" -ForegroundColor DarkCyan
    Get-PnpDevice | Where-Object {
        ($_.Class -eq "USB" -or $_.Class -eq "USBDevice") -and $_.Status -eq "OK"
    } | Sort-Object FriendlyName | ForEach-Object {
        Write-Host ("  [OK]        {0}" -f $_.FriendlyName) -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  -- Connected USB Devices (by class) --" -ForegroundColor DarkCyan
    $classes = @("DiskDrive","CDROM","Keyboard","Mouse","HIDClass",
                 "Image","Media","Printer","AndroidUsbDeviceClass","WPD","Bluetooth")
    Get-PnpDevice | Where-Object {
        $_.InstanceId -like "USB\*" -and $_.Status -eq "OK" -and $_.Class -in $classes
    } | Sort-Object Class, FriendlyName | ForEach-Object {
        $color = switch ($_.Class) {
            "DiskDrive"  { "Yellow" }
            "Image"      { "Cyan"   }
            "Media"      { "Cyan"   }
            "Printer"    { "Magenta"}
            "HIDClass"   { "Green"  }
            "Keyboard"   { "Green"  }
            "Mouse"      { "Green"  }
            default      { "White"  }
        }
        Write-Host ("  {0,-14} {1}" -f $_.Class, $_.FriendlyName) -ForegroundColor $color
    }

    Write-Host ""
    Write-Host "  -- All USB-connected PnP (OK status) --" -ForegroundColor DarkCyan
    Get-PnpDevice | Where-Object {
        $_.InstanceId -like "USB\*" -and $_.Status -eq "OK"
    } | Sort-Object FriendlyName | Select-Object -First 40 | ForEach-Object {
        Write-Host ("  {0,-20} {1}" -f $_.Class, $_.FriendlyName) -ForegroundColor Cyan
    }

    Write-Host ""
    Write-Host "  -- USB Mass Storage Volumes --" -ForegroundColor DarkCyan
    Get-Disk | Where-Object { $_.BusType -eq "USB" } | ForEach-Object {
        $disk = $_
        $color = if ($disk.HealthStatus -eq "Healthy") { "Green" } else { "Red" }
        Write-Host ("  Disk {0}: {1,-30} {2,-10} {3}" -f `
            $disk.Number,
            $disk.FriendlyName,
            (Format-Bytes ([long]$disk.Size)),
            $disk.HealthStatus
        ) -ForegroundColor $color
        Get-Partition -DiskNumber $disk.Number -ErrorAction SilentlyContinue |
            Where-Object { $_.DriveLetter } | ForEach-Object {
                Write-Host ("    Drive {0}:  {1}" -f $_.DriveLetter,
                    (Format-Bytes ([long]$_.Size))) -ForegroundColor Yellow
            }
    }
    Pause-Menu
}

function Show-WMPShares {
    Write-Header "Windows Media Player - Network Shares"

    Write-Host "  -- WMP Network Sharing Service --" -ForegroundColor DarkCyan
    $svc = Get-Service -Name "WMPNetworkSvc" -ErrorAction SilentlyContinue
    if ($svc) {
        $color = if ($svc.Status -eq "Running") { "Green" } else { "Red" }
        Write-Host ("  Service Status : {0}" -f $svc.Status) -ForegroundColor $color
        if ($svc.Status -ne "Running") {
            Write-Host "  (Service is not running - shares may not be visible on network)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  WMP Network Sharing Service not found." -ForegroundColor Red
        Write-Host "  WMP may not be installed or is disabled." -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  -- WMP Shared Media Library Folders --" -ForegroundColor DarkCyan
    $wmpRegPaths = @(
        "HKLM:\SOFTWARE\Microsoft\Windows Media Player\Sharing",
        "HKCU:\SOFTWARE\Microsoft\Windows Media Player\Preferences",
        "HKLM:\SOFTWARE\Microsoft\Windows Media Player NSS\3.0\Server"
    )
    $found = $false
    foreach ($p in $wmpRegPaths) {
        if (Test-Path $p) {
            $found = $true
            Write-Host "  $p" -ForegroundColor DarkGray
            try {
                $props = Get-ItemProperty -Path $p -ErrorAction Stop
                $props.PSObject.Properties | Where-Object { $_.Name -notlike "PS*" } | ForEach-Object {
                    Write-Host ("    {0,-35} {1}" -f $_.Name, $_.Value)
                }
            } catch {
                Write-Host "    (inaccessible)" -ForegroundColor DarkGray
            }
        }
    }
    if (-not $found) {
        Write-Host "  No WMP sharing registry keys found." -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  -- UPnP / DLNA Media Server Detection --" -ForegroundColor DarkCyan
    $upnpSvc = Get-Service -Name "SSDPSRV","upnphost" -ErrorAction SilentlyContinue
    foreach ($s in $upnpSvc) {
        $color = if ($s.Status -eq "Running") { "Green" } else { "DarkGray" }
        Write-Host ("  {0,-20} {1}" -f $s.DisplayName, $s.Status) -ForegroundColor $color
    }

    Write-Host ""
    Write-Host "  -- WMP Library Database Location --" -ForegroundColor DarkCyan
    $dbPath = "$env:LOCALAPPDATA\Microsoft\Media Player"
    if (Test-Path $dbPath) {
        Get-ChildItem $dbPath -ErrorAction SilentlyContinue | ForEach-Object {
            Write-Host ("  {0,-12}  {1}" -f (Format-Bytes $_.Length), $_.Name) -ForegroundColor Cyan
        }
    } else {
        Write-Host "  WMP library path not found: $dbPath" -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  -- SMB Shares visible to media apps --" -ForegroundColor DarkCyan
    try {
        Get-SmbShare | Where-Object { $_.Name -notmatch "^\w+\$$" } | ForEach-Object {
            Write-Host ("  {0,-20} {1}" -f $_.Name, $_.Path) -ForegroundColor Cyan
        }
    } catch {
        Write-Host "  (Unable to query SMB shares)" -ForegroundColor DarkGray
    }
    Pause-Menu
}

function Start-DefenderScan {
    Write-Header "Windows Defender - Quick Scan"

    # Check Defender status first
    Write-Host "  -- Checking Defender Status --" -ForegroundColor DarkCyan
    try {
        $status = Get-MpComputerStatus -ErrorAction Stop
        $avEnabled = $status.AntivirusEnabled
        $rtEnabled = $status.RealTimeProtectionEnabled
        $avColor   = if ($avEnabled) { "Green" } else { "Red" }
        $rtColor   = if ($rtEnabled) { "Green" } else { "Red" }
        Write-Host ("  Antivirus Enabled  : {0}" -f $(if ($avEnabled) { "Yes" } else { "No" })) -ForegroundColor $avColor
        Write-Host ("  Real-Time Protect  : {0}" -f $(if ($rtEnabled) { "Yes" } else { "No" })) -ForegroundColor $rtColor
        Write-Host ("  AV Sig Age (days)  : {0}" -f $status.AntivirusSignatureAge)

        if (-not $avEnabled) {
            Write-Host ""
            Write-Host "  Defender antivirus engine is DISABLED." -ForegroundColor Red
            Write-Host "  This usually means a third-party AV (e.g. Norton, McAfee," -ForegroundColor Yellow
            Write-Host "  Malwarebytes, Avast) has taken over and disabled Defender." -ForegroundColor Yellow
            Write-Host "  Scan cannot run. Use your installed AV to scan instead." -ForegroundColor Yellow
            Pause-Menu
            return
        }
    } catch {
        Write-Host "  Could not query Defender status - may not be installed." -ForegroundColor Red
        Pause-Menu
        return
    }

    $mpCmd = "$env:ProgramFiles\Windows Defender\MpCmdRun.exe"
    if (-not (Test-Path $mpCmd)) {
        $resolved = Resolve-Path "$env:ProgramData\Microsoft\Windows Defender\Platform\*\MpCmdRun.exe" `
            -ErrorAction SilentlyContinue | Select-Object -Last 1
        if ($resolved) { $mpCmd = $resolved.Path }
    }

    if (-not (Test-Path $mpCmd)) {
        Write-Host "  MpCmdRun.exe not found." -ForegroundColor Red
        Pause-Menu
        return
    }

    Write-Host ""
    Write-Host "  Scanner    : $mpCmd" -ForegroundColor DarkGray
    Write-Host "  Scan type  : Quick Scan" -ForegroundColor DarkCyan
    Write-Host "  Started    : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkCyan
    Write-Host ""

    if (-not (Is-Admin)) {
        Write-Host "  Elevation required. Relaunching as admin..." -ForegroundColor Yellow
        Start-Process powershell -Verb RunAs -ArgumentList @(
            "-NoExit",
            "-Command",
            "& '$mpCmd' -Scan -ScanType 2; Write-Host ''; Write-Host 'Scan complete.'; pause"
        )
        Pause-Menu
        return
    }

    Write-Host "  Running... (this may take several minutes)" -ForegroundColor Yellow
    Write-Host ""

    $start = Get-Date
    $proc  = Start-Process -FilePath $mpCmd `
                 -ArgumentList "-Scan -ScanType 2" `
                 -Wait -PassThru -NoNewWindow

    $elapsed = [math]::Round(((Get-Date) - $start).TotalSeconds, 1)

    Write-Host ""
    Write-Host ("  Finished   : {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -ForegroundColor DarkCyan
    Write-Host ("  Duration   : {0}s" -f $elapsed) -ForegroundColor DarkCyan
    Write-Host ("  Exit Code  : {0}" -f $proc.ExitCode) -ForegroundColor DarkCyan
    Write-Host ""

    switch ($proc.ExitCode) {
        0       { Write-Host "  Result: No threats found." -ForegroundColor Green }
        2       { Write-Host "  Result: Threats FOUND and remediated." -ForegroundColor Yellow }
        4       { Write-Host "  Result: Threats found - action REQUIRED." -ForegroundColor Red }
        5       { Write-Host "  Result: Scan failed or was blocked." -ForegroundColor Red }
        default { Write-Host ("  Result: Exit code {0} - check Defender event log." -f $proc.ExitCode) -ForegroundColor Yellow }
    }

    Write-Host ""
    Write-Host "  -- Post-Scan Stats --" -ForegroundColor DarkCyan
    try {
        $status = Get-MpComputerStatus -ErrorAction Stop
        Write-Host ("  Last Quick Scan    : {0}" -f $status.QuickScanEndTime.ToString("yyyy-MM-dd HH:mm:ss"))
        Write-Host ("  Last Full Scan     : {0}" -f $status.FullScanEndTime.ToString("yyyy-MM-dd HH:mm:ss"))
        Write-Host ("  AV Sig Version     : {0}" -f $status.AntivirusSignatureVersion)
    } catch {
        Write-Host "  (Could not retrieve scan stats)" -ForegroundColor DarkGray
    }
    Pause-Menu
}

function Show-WindowsVersion {
    Write-Header "Windows Version Details"
    $os  = Get-CimInstance Win32_OperatingSystem
    $reg = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"

    $info = [ordered]@{
        "Product Name"     = $reg.ProductName
        "Edition"          = $os.Caption
        "Version"          = $reg.DisplayVersion
        "OS Build"         = "$($reg.CurrentBuild).$($reg.UBR)"
        "Build Branch"     = $reg.BuildBranch
        "Install Date"     = $os.InstallDate.ToString("yyyy-MM-dd")
        "Registered Owner" = $reg.RegisteredOwner
        "Architecture"     = $os.OSArchitecture
        "System Root"      = $reg.SystemRoot
    }

    foreach ($key in $info.Keys) {
        Write-Host ("{0,-22}: " -f $key) -ForegroundColor DarkCyan -NoNewline
        Write-Host $info[$key]
    }

    Write-Host ""
    Write-Host "  -- Support Status --" -ForegroundColor DarkCyan
    $ver = $reg.DisplayVersion
    Write-Host ("  Current Version : {0}" -f $ver) -ForegroundColor Cyan
    Write-Host "  Check end-of-support: https://learn.microsoft.com/en-us/windows/release-health/" -ForegroundColor DarkGray
    Pause-Menu
}

function Show-Bluetooth {
    Write-Header "Bluetooth Devices and Adapters"

    Write-Host "  -- Bluetooth Adapters --" -ForegroundColor DarkCyan
    $adapters = Get-PnpDevice | Where-Object {
        $_.Class -eq "Bluetooth" -and $_.FriendlyName -notlike "*Device*" -and
        $_.FriendlyName -notlike "*HID*" -and $_.FriendlyName -notlike "*Hands*"
    }
    if ($adapters) {
        $adapters | ForEach-Object {
            $color = if ($_.Status -eq "OK") { "Green" } else { "Yellow" }
            Write-Host ("  [{0,-10}] {1}" -f $_.Status, $_.FriendlyName) -ForegroundColor $color
        }
    } else {
        Write-Host "  No Bluetooth adapters found." -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  -- Paired / Known Bluetooth Devices --" -ForegroundColor DarkCyan
    $btDevices = Get-PnpDevice | Where-Object { $_.Class -eq "Bluetooth" } | Sort-Object FriendlyName
    if ($btDevices) {
        $btDevices | ForEach-Object {
            $color = switch ($_.Status) {
                "OK"      { "Green"    }
                "Unknown" { "DarkGray" }
                default   { "Yellow"   }
            }
            Write-Host ("  [{0,-10}] {1}" -f $_.Status, $_.FriendlyName) -ForegroundColor $color
        }
    } else {
        Write-Host "  No Bluetooth devices found." -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  -- All Bluetooth-Related PnP Entries --" -ForegroundColor DarkCyan
    Get-PnpDevice | Where-Object { $_.InstanceId -like "BTHENUM*" -or $_.InstanceId -like "BTH*" } |
        Sort-Object FriendlyName | Select-Object -First 30 | ForEach-Object {
            $color = if ($_.Status -eq "OK") { "Cyan" } else { "DarkGray" }
            Write-Host ("  [{0,-10}] {1}" -f $_.Status, $_.FriendlyName) -ForegroundColor $color
        }

    Write-Host ""
    Write-Host "  -- Bluetooth Service Status --" -ForegroundColor DarkCyan
    $btSvc = Get-Service -Name "bthserv" -ErrorAction SilentlyContinue
    if ($btSvc) {
        $color = if ($btSvc.Status -eq "Running") { "Green" } else { "Red" }
        Write-Host ("  Bluetooth Support Service: {0}" -f $btSvc.Status) -ForegroundColor $color
    } else {
        Write-Host "  Bluetooth Support Service not found." -ForegroundColor DarkGray
    }
    Pause-Menu
}

function Start-Autoruns {
    Write-Header "Sysinternals Autoruns (Live)"

    Write-Host "  Autoruns shows everything configured to run at startup:" -ForegroundColor DarkGray
    Write-Host "  logon, services, drivers, scheduled tasks, browser extensions," -ForegroundColor DarkGray
    Write-Host "  and more. Loaded directly from Sysinternals Live." -ForegroundColor DarkGray
    Write-Host ""

    # Check for cached local copy first
    $localPath = "$env:TEMP\Autoruns\Autoruns.exe"
    $useLocal  = Test-Path $localPath

    if ($useLocal) {
        Write-Host "  Found cached copy: $localPath" -ForegroundColor DarkGray
    } else {
        Write-Host "  Downloading from: https://live.sysinternals.com/Autoruns.exe" -ForegroundColor DarkCyan
        try {
            $dir = "$env:TEMP\Autoruns"
            if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
            Invoke-WebRequest -Uri "https://live.sysinternals.com/Autoruns.exe" `
                -OutFile $localPath -UseBasicParsing -ErrorAction Stop
            Write-Host "  Download complete." -ForegroundColor Green
        } catch {
            Write-Host "  Download failed: $_" -ForegroundColor Red
            Write-Host "  Check your internet connection or visit:" -ForegroundColor Yellow
            Write-Host "  https://learn.microsoft.com/sysinternals/downloads/autoruns" -ForegroundColor Yellow
            Pause-Menu
            return
        }
    }

    Write-Host ""
    Write-Host "  Launching Autoruns..." -ForegroundColor Yellow
    Write-Host "  (GUI window will open separately)" -ForegroundColor DarkGray

    if (Is-Admin) {
        Start-Process -FilePath $localPath
    } else {
        Write-Host "  Tip: Run as admin to see all entries (UAC prompt may appear)" -ForegroundColor DarkGray
        Start-Process -FilePath $localPath -Verb RunAs
    }

    Pause-Menu
}


function Start-SysinternalsUtil {
    param(
        [string]$Name,
        [string]$Title,
        [string]$Description,
        [string]$Args = "",
        [bool]$ForceAdmin = $false,
        [bool]$IsConsole = $false
    )
    Write-Header "Sysinternals - $Title"
    Write-Host "  $Description" -ForegroundColor DarkGray
    Write-Host ""

    $url       = "https://live.sysinternals.com/$Name"
    $localPath = "$env:TEMP\Sysinternals\$Name"

    if (-not (Test-Path "$env:TEMP\Sysinternals")) {
        New-Item -ItemType Directory -Path "$env:TEMP\Sysinternals" | Out-Null
    }

    if (Test-Path $localPath) {
        Write-Host "  Cached: $localPath" -ForegroundColor DarkGray
    } else {
        Write-Host "  Downloading: $url" -ForegroundColor DarkCyan
        try {
            Invoke-WebRequest -Uri $url -OutFile $localPath -UseBasicParsing -ErrorAction Stop
            Write-Host "  Download complete." -ForegroundColor Green
        } catch {
            Write-Host "  Download failed: $_" -ForegroundColor Red
            Pause-Menu
            return
        }
    }

    Write-Host "  Launching $Name..." -ForegroundColor Yellow
    if ($IsConsole) {
        if ($ForceAdmin -and -not (Is-Admin)) {
            Start-Process powershell -Verb RunAs `
                -ArgumentList "-NoExit -Command `"& '$localPath' $Args`""
        } else {
            if ($Args) {
                & $localPath $Args.Split(" ")
            } else {
                & $localPath
            }
        }
    } else {
        if ($ForceAdmin -and -not (Is-Admin)) {
            Start-Process -FilePath $localPath -ArgumentList $Args -Verb RunAs
        } else {
            Start-Process -FilePath $localPath -ArgumentList $Args
        }
        Write-Host "  (GUI window opened separately)" -ForegroundColor DarkGray
    }
    Pause-Menu
}

function Start-ProcessExplorer {
    Start-SysinternalsUtil `
        -Name "procexp64.exe" `
        -Title "Process Explorer" `
        -Description "Advanced Task Manager: process trees, DLL handles, VirusTotal integration." `
        -ForceAdmin $true
}

function Start-ProcessMonitor {
    Start-SysinternalsUtil `
        -Name "Procmon64.exe" `
        -Title "Process Monitor" `
        -Description "Real-time file system, registry, and network activity per process." `
        -ForceAdmin $true
}

function Start-TCPView {
    Start-SysinternalsUtil `
        -Name "Tcpview.exe" `
        -Title "TCPView" `
        -Description "Live GUI view of all TCP/UDP connections with process names." `
        -ForceAdmin $true
}

function Start-Sigcheck {
    Write-Header "Sysinternals - Sigcheck"
    Write-Host "  Checks file signatures and optionally submits to VirusTotal." -ForegroundColor DarkGray
    Write-Host ""

    $localPath = "$env:TEMP\Sysinternals\sigcheck64.exe"
    if (-not (Test-Path "$env:TEMP\Sysinternals")) {
        New-Item -ItemType Directory -Path "$env:TEMP\Sysinternals" | Out-Null
    }
    if (-not (Test-Path $localPath)) {
        Write-Host "  Downloading sigcheck64.exe..." -ForegroundColor DarkCyan
        try {
            Invoke-WebRequest -Uri "https://live.sysinternals.com/sigcheck64.exe" `
                -OutFile $localPath -UseBasicParsing -ErrorAction Stop
            Write-Host "  Download complete." -ForegroundColor Green
        } catch {
            Write-Host "  Download failed: $_" -ForegroundColor Red
            Pause-Menu
            return
        }
    }

    Write-Host "  What to scan?" -ForegroundColor White
    Write-Host "    [1] Windows System32 unsigned files" -ForegroundColor Cyan
    Write-Host "    [2] Startup locations (unsigned)" -ForegroundColor Cyan
    Write-Host "    [3] Enter a custom path" -ForegroundColor Cyan
    Write-Host "    [Q] Cancel" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Choice: " -ForegroundColor White -NoNewline
    $sc = (Read-Host).Trim().ToUpper()

    $scanPath = switch ($sc) {
        "1" { "C:\Windows\System32" }
        "2" { "C:\Windows\System32\drivers" }
        "3" {
            Write-Host "  Enter path: " -ForegroundColor White -NoNewline
            (Read-Host).Trim()
        }
        default { $null }
    }

    if (-not $scanPath) { Pause-Menu; return }

    Write-Host ""
    Write-Host "  Scanning: $scanPath" -ForegroundColor DarkCyan
    Write-Host "  (showing unsigned files only - this may take a moment)" -ForegroundColor DarkGray
    Write-Host ""

    # -u = unsigned only, -e = check executables only, -accepteula
    & $localPath -u -e -accepteula $scanPath
    Pause-Menu
}

function Start-Handle {
    Write-Header "Sysinternals - Handle"
    Write-Host "  Shows which process holds a lock on a file or folder." -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Enter file or folder path to check (or leave blank for all handles):" -ForegroundColor White
    Write-Host "  Path: " -ForegroundColor White -NoNewline
    $target = (Read-Host).Trim()

    $localPath = "$env:TEMP\Sysinternals\handle64.exe"
    if (-not (Test-Path "$env:TEMP\Sysinternals")) {
        New-Item -ItemType Directory -Path "$env:TEMP\Sysinternals" | Out-Null
    }
    if (-not (Test-Path $localPath)) {
        Write-Host "  Downloading handle64.exe..." -ForegroundColor DarkCyan
        try {
            Invoke-WebRequest -Uri "https://live.sysinternals.com/handle64.exe" `
                -OutFile $localPath -UseBasicParsing -ErrorAction Stop
            Write-Host "  Download complete." -ForegroundColor Green
        } catch {
            Write-Host "  Download failed: $_" -ForegroundColor Red
            Pause-Menu
            return
        }
    }

    Write-Host ""
    if (-not (Is-Admin)) {
        Write-Host "  Elevation required for handle enumeration. Relaunching as admin..." -ForegroundColor Yellow
        if ($target) {
            Start-Process powershell -Verb RunAs `
                -ArgumentList "-NoExit -Command `"& '$localPath' -accepteula '$target'`""
        } else {
            Start-Process powershell -Verb RunAs `
                -ArgumentList "-NoExit -Command `"& '$localPath' -accepteula`""
        }
        Pause-Menu
        return
    }

    if ($target) {
        & $localPath -accepteula $target
    } else {
        & $localPath -accepteula | Select-Object -First 60
    }
    Pause-Menu
}

function Start-Du {
    Write-Header "Sysinternals - Du (Disk Usage)"
    Write-Host "  Shows disk usage by folder, like Linux du." -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Enter path to analyse (default: C:\Users\$env:USERNAME):" -ForegroundColor White
    Write-Host "  Path: " -ForegroundColor White -NoNewline
    $target = (Read-Host).Trim()
    if (-not $target) { $target = "C:\Users\$env:USERNAME" }

    $localPath = "$env:TEMP\Sysinternals\du64.exe"
    if (-not (Test-Path "$env:TEMP\Sysinternals")) {
        New-Item -ItemType Directory -Path "$env:TEMP\Sysinternals" | Out-Null
    }
    if (-not (Test-Path $localPath)) {
        Write-Host "  Downloading du64.exe..." -ForegroundColor DarkCyan
        try {
            Invoke-WebRequest -Uri "https://live.sysinternals.com/du64.exe" `
                -OutFile $localPath -UseBasicParsing -ErrorAction Stop
            Write-Host "  Download complete." -ForegroundColor Green
        } catch {
            Write-Host "  Download failed: $_" -ForegroundColor Red
            Pause-Menu
            return
        }
    }

    Write-Host ""
    Write-Host "  Scanning: $target" -ForegroundColor DarkCyan
    Write-Host "  (top-level folder sizes, -l 1 = one level deep)" -ForegroundColor DarkGray
    Write-Host ""
    & $localPath -accepteula -l 1 -q $target
    Pause-Menu
}

function Start-PsInfo {
    Start-SysinternalsUtil `
        -Name "PsInfo64.exe" `
        -Title "PsInfo" `
        -Description "Detailed local system info: install date, hotfixes, drives, CPU, RAM." `
        -Args "-accepteula" `
        -IsConsole $true `
        -ForceAdmin $true
}

function Start-Coreinfo {
    Start-SysinternalsUtil `
        -Name "Coreinfo64.exe" `
        -Title "Coreinfo" `
        -Description "CPU feature details: virtualization, cache topology, NUMA, instruction sets." `
        -Args "-accepteula" `
        -IsConsole $true
}

function Start-RAMMap {
    Start-SysinternalsUtil `
        -Name "RAMMap.exe" `
        -Title "RAMMap" `
        -Description "Detailed physical memory usage breakdown by type and process." `
        -ForceAdmin $true
}

function Start-Whois {
    Write-Header "Sysinternals - Whois"
    Write-Host "  Lookup domain registration info." -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Enter domain to look up: " -ForegroundColor White -NoNewline
    $domain = (Read-Host).Trim()
    if (-not $domain) { Pause-Menu; return }

    $localPath = "$env:TEMP\Sysinternals\whois64.exe"
    if (-not (Test-Path "$env:TEMP\Sysinternals")) {
        New-Item -ItemType Directory -Path "$env:TEMP\Sysinternals" | Out-Null
    }
    if (-not (Test-Path $localPath)) {
        Write-Host "  Downloading whois64.exe..." -ForegroundColor DarkCyan
        try {
            Invoke-WebRequest -Uri "https://live.sysinternals.com/whois64.exe" `
                -OutFile $localPath -UseBasicParsing -ErrorAction Stop
            Write-Host "  Download complete." -ForegroundColor Green
        } catch {
            Write-Host "  Download failed: $_" -ForegroundColor Red
            Pause-Menu
            return
        }
    }

    Write-Host ""
    Write-Host "  Querying: $domain" -ForegroundColor DarkCyan
    Write-Host ""
    & $localPath -accepteula $domain
    Pause-Menu
}

function Start-Strings {
    Write-Header "Sysinternals - Strings"
    Write-Host "  Extract printable strings from any binary/executable." -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Enter path to file: " -ForegroundColor White -NoNewline
    $target = (Read-Host).Trim()
    if (-not $target -or -not (Test-Path $target)) {
        Write-Host "  File not found: $target" -ForegroundColor Red
        Pause-Menu
        return
    }

    $localPath = "$env:TEMP\Sysinternals\strings64.exe"
    if (-not (Test-Path "$env:TEMP\Sysinternals")) {
        New-Item -ItemType Directory -Path "$env:TEMP\Sysinternals" | Out-Null
    }
    if (-not (Test-Path $localPath)) {
        Write-Host "  Downloading strings64.exe..." -ForegroundColor DarkCyan
        try {
            Invoke-WebRequest -Uri "https://live.sysinternals.com/strings64.exe" `
                -OutFile $localPath -UseBasicParsing -ErrorAction Stop
            Write-Host "  Download complete." -ForegroundColor Green
        } catch {
            Write-Host "  Download failed: $_" -ForegroundColor Red
            Pause-Menu
            return
        }
    }

    Write-Host ""
    Write-Host "  Strings in: $target" -ForegroundColor DarkCyan
    Write-Host "  (showing first 80 results)" -ForegroundColor DarkGray
    Write-Host ""
    & $localPath -accepteula $target | Select-Object -First 80
    Pause-Menu
}

function Start-AccessChk {
    Write-Header "Sysinternals - AccessChk"
    Write-Host "  Check permissions on files, registry keys, or services." -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  What to check?" -ForegroundColor White
    Write-Host "    [1] Services writable by non-admins (security check)" -ForegroundColor Cyan
    Write-Host "    [2] Permissions on a specific file or folder" -ForegroundColor Cyan
    Write-Host "    [3] Permissions on a registry key" -ForegroundColor Cyan
    Write-Host "    [Q] Cancel" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Choice: " -ForegroundColor White -NoNewline
    $ac = (Read-Host).Trim().ToUpper()

    $localPath = "$env:TEMP\Sysinternals\accesschk64.exe"
    if (-not (Test-Path "$env:TEMP\Sysinternals")) {
        New-Item -ItemType Directory -Path "$env:TEMP\Sysinternals" | Out-Null
    }
    if (-not (Test-Path $localPath)) {
        Write-Host "  Downloading accesschk64.exe..." -ForegroundColor DarkCyan
        try {
            Invoke-WebRequest -Uri "https://live.sysinternals.com/accesschk64.exe" `
                -OutFile $localPath -UseBasicParsing -ErrorAction Stop
            Write-Host "  Download complete." -ForegroundColor Green
        } catch {
            Write-Host "  Download failed: $_" -ForegroundColor Red
            Pause-Menu
            return
        }
    }

    Write-Host ""
    switch ($ac) {
        "1" {
            Write-Host "  Checking services writable by Everyone/Users..." -ForegroundColor DarkCyan
            & $localPath -accepteula -uwcqv "Everyone" *
        }
        "2" {
            Write-Host "  Enter path: " -ForegroundColor White -NoNewline
            $p = (Read-Host).Trim()
            & $localPath -accepteula -l $p
        }
        "3" {
            Write-Host "  Enter registry key (e.g. HKLM\SYSTEM): " -ForegroundColor White -NoNewline
            $p = (Read-Host).Trim()
            & $localPath -accepteula -k $p
        }
        default { Pause-Menu; return }
    }
    Pause-Menu
}

function Start-PsExec {
    Write-Header "Sysinternals - PsExec"
    Write-Host "  Run processes locally as SYSTEM, or remotely on other machines." -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  What to run?" -ForegroundColor White
    Write-Host "    [1] Open a SYSTEM-level cmd.exe (local)" -ForegroundColor Cyan
    Write-Host "    [2] Open a SYSTEM-level PowerShell (local)" -ForegroundColor Cyan
    Write-Host "    [3] Run custom command as SYSTEM" -ForegroundColor Cyan
    Write-Host "    [Q] Cancel" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Choice: " -ForegroundColor White -NoNewline
    $pe = (Read-Host).Trim().ToUpper()
    if ($pe -eq "Q") { Pause-Menu; return }

    $localPath = "$env:TEMP\Sysinternals\PsExec64.exe"
    if (-not (Test-Path "$env:TEMP\Sysinternals")) {
        New-Item -ItemType Directory -Path "$env:TEMP\Sysinternals" | Out-Null
    }
    if (-not (Test-Path $localPath)) {
        Write-Host "  Downloading PsExec64.exe..." -ForegroundColor DarkCyan
        try {
            Invoke-WebRequest -Uri "https://live.sysinternals.com/PsExec64.exe" `
                -OutFile $localPath -UseBasicParsing -ErrorAction Stop
            Write-Host "  Download complete." -ForegroundColor Green
        } catch {
            Write-Host "  Download failed: $_" -ForegroundColor Red
            Pause-Menu
            return
        }
    }

    if (-not (Is-Admin)) {
        Write-Host "  PsExec requires elevation. Relaunching as admin..." -ForegroundColor Yellow
        Start-Process powershell -Verb RunAs -ArgumentList "-NoExit -Command `"Write-Host 'PsExec admin shell ready. Run: $localPath -accepteula -s cmd.exe'`""
        Pause-Menu
        return
    }

    switch ($pe) {
        "1" { Start-Process -FilePath $localPath -ArgumentList "-accepteula -s cmd.exe" }
        "2" { Start-Process -FilePath $localPath -ArgumentList "-accepteula -s powershell.exe" }
        "3" {
            Write-Host "  Enter command to run as SYSTEM: " -ForegroundColor White -NoNewline
            $cmd = (Read-Host).Trim()
            if ($cmd) { & $localPath -accepteula -s $cmd }
        }
    }
    Pause-Menu
}

function Start-PsLoggedOn {
    Start-SysinternalsUtil `
        -Name "PsLoggedon64.exe" `
        -Title "PsLoggedOn" `
        -Description "Shows who is logged on locally and via network shares." `
        -Args "-accepteula" `
        -IsConsole $true `
        -ForceAdmin $true
}

# -----------------------------------------------
#  Main Menu Loop
# -----------------------------------------------

$menuItems = [ordered]@{
     "1"  = @{ Label = "Disk Space";                  Fn = { Show-DiskSpace         } }
     "2"  = @{ Label = "Local Users";                 Fn = { Show-LocalUsers        } }
     "3"  = @{ Label = "Local Groups";                Fn = { Show-LocalGroups       } }
     "4"  = @{ Label = "System Information";          Fn = { Show-SystemInfo        } }
     "5"  = @{ Label = "Network Adapters / IP Info";  Fn = { Show-NetworkInfo       } }
     "6"  = @{ Label = "Open Ports / Connections";    Fn = { Show-OpenPorts         } }
     "7"  = @{ Label = "Top Processes (CPU/RAM)";     Fn = { Show-TopProcesses      } }
     "8"  = @{ Label = "Services";                    Fn = { Show-Services          } }
     "9"  = @{ Label = "Startup Items";               Fn = { Show-StartupItems      } }
    "10"  = @{ Label = "Installed Software";          Fn = { Show-InstalledSoftware } }
    "11"  = @{ Label = "Recent Error Events (24h)";   Fn = { Show-EventLog          } }
    "12"  = @{ Label = "Windows Update History";      Fn = { Show-WindowsUpdates    } }
    "13"  = @{ Label = "Environment Variables";       Fn = { Show-EnvVars           } }
    "14"  = @{ Label = "Connectivity Check (Ping)";   Fn = { Test-Connectivity      } }
    "15"  = @{ Label = "Flush DNS Cache";             Fn = { Flush-DNS              } }
    "16"  = @{ Label = "GPU / Display Info";          Fn = { Show-GPU               } }
    "17"  = @{ Label = "Battery and Power Plan";      Fn = { Show-Battery           } }
    "18"  = @{ Label = "Wi-Fi Profiles and Signal";   Fn = { Show-WiFiNetworks      } }
    "19"  = @{ Label = "Firewall Status and Rules";   Fn = { Show-Firewall          } }
    "20"  = @{ Label = "Shared Folders and Drives";   Fn = { Show-SharedFolders     } }
    "21"  = @{ Label = "Scheduled Tasks (non-MS)";    Fn = { Show-ScheduledTasks    } }
    "22"  = @{ Label = "Temp File Cleanup";           Fn = { Clear-TempFiles        } }
    "23"  = @{ Label = "Local Network Ping Sweep";    Fn = { Show-PingSweep         } }
    "24"  = @{ Label = "Security (TPM/SecureBoot/AV)";Fn = { Show-SecurityInfo      } }
    "25"  = @{ Label = "Disk Health (SMART)";         Fn = { Show-DiskHealth        } }
    "26"  = @{ Label = "Recently Modified Files";     Fn = { Show-RecentFiles       } }
    "27"  = @{ Label = "Windows Version Details";     Fn = { Show-WindowsVersion    } }
    "28"  = @{ Label = "Bluetooth Devices";           Fn = { Show-Bluetooth         } }
    "29"  = @{ Label = "Connected USB Devices";       Fn = { Show-USBDevices        } }
    "30"  = @{ Label = "Windows Media Player Shares"; Fn = { Show-WMPShares         } }
    "31"  = @{ Label = "Defender Quick Scan";          Fn = { Start-DefenderScan     } }
    "32"  = @{ Label = "Sysinternals Autoruns";          Fn = { Start-Autoruns          } }
    "33"  = @{ Label = "Sysinternals Process Explorer";  Fn = { Start-ProcessExplorer   } }
    "34"  = @{ Label = "Sysinternals Process Monitor";   Fn = { Start-ProcessMonitor    } }
    "35"  = @{ Label = "Sysinternals TCPView";           Fn = { Start-TCPView           } }
    "36"  = @{ Label = "Sysinternals Sigcheck";          Fn = { Start-Sigcheck          } }
    "37"  = @{ Label = "Sysinternals Handle";            Fn = { Start-Handle            } }
    "38"  = @{ Label = "Sysinternals Du (Disk Usage)";   Fn = { Start-Du                } }
    "39"  = @{ Label = "Sysinternals PsInfo";            Fn = { Start-PsInfo            } }
    "40"  = @{ Label = "Sysinternals Coreinfo";          Fn = { Start-Coreinfo          } }
    "41"  = @{ Label = "Sysinternals RAMMap";            Fn = { Start-RAMMap            } }
    "42"  = @{ Label = "Sysinternals Whois";             Fn = { Start-Whois             } }
    "43"  = @{ Label = "Sysinternals Strings";           Fn = { Start-Strings           } }
    "44"  = @{ Label = "Sysinternals AccessChk";         Fn = { Start-AccessChk         } }
    "45"  = @{ Label = "Sysinternals PsExec";            Fn = { Start-PsExec            } }
    "46"  = @{ Label = "Sysinternals PsLoggedOn";        Fn = { Start-PsLoggedOn        } }
     "Q"  = @{ Label = "Quit";                          Fn = $null                      }
}

do {
    Clear-Host
    $adminTag = if (Is-Admin) { " [ADMIN]" } else { " [not elevated]" }
    $colWidth  = 38
    $border    = "=" * ($colWidth * 2 + 4)

    Write-Host $border -ForegroundColor DarkCyan
    $header = "  WINDOWS UTILITY MENU"
    Write-Host ($header + $adminTag.PadLeft($border.Length - $header.Length)) -ForegroundColor White
    Write-Host ("  " + (Get-Date -Format "dddd, yyyy-MM-dd  HH:mm:ss").PadRight($border.Length - 2)) -ForegroundColor DarkGray
    Write-Host $border -ForegroundColor DarkCyan
    Write-Host ""

    # Build two-column display: left col items 1-30, right col items 31+
    $allKeys  = @($menuItems.Keys | Where-Object { $_ -ne "Q" })
    $colSize  = 30
    $leftKeys = $allKeys | Select-Object -First $colSize
    $rightKeys= $allKeys | Select-Object -Skip  $colSize

    $maxRows = [math]::Max($leftKeys.Count, $rightKeys.Count)

    for ($i = 0; $i -lt $maxRows; $i++) {
        $lKey  = if ($i -lt $leftKeys.Count)  { $leftKeys[$i]  } else { $null }
        $rKey  = if ($i -lt $rightKeys.Count) { $rightKeys[$i] } else { $null }

        $lText = if ($lKey) { "[{0,-2}] {1}" -f $lKey, $menuItems[$lKey].Label } else { "" }
        $rText = if ($rKey) { "[{0,-2}] {1}" -f $rKey, $menuItems[$rKey].Label } else { "" }

        Write-Host ("  {0,-38}  " -f $lText) -ForegroundColor Cyan -NoNewline
        if ($rText) {
            Write-Host $rText -ForegroundColor Yellow
        } else {
            Write-Host ""
        }
    }

    Write-Host ""
    Write-Host "  [Q]  Quit" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host $border -ForegroundColor DarkCyan
    Write-Host "  Choice: " -ForegroundColor White -NoNewline
    $choice = (Read-Host).Trim().ToUpper()

    if ($menuItems.Contains($choice) -and $null -ne $menuItems[$choice].Fn) {
        Clear-Host
        & $menuItems[$choice].Fn
    } elseif ($choice -ne "Q") {
        Write-Host "  Invalid choice. Try again." -ForegroundColor Red
        Start-Sleep -Seconds 1
    }

} while ($choice -ne "Q")

Write-Host ""
Write-Host "  Goodbye." -ForegroundColor DarkGray
Write-Host ""
