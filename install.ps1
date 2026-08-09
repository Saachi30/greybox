# Greybox installer - Windows (PowerShell).
#
# This is a separate script from install.sh on purpose (see docs/RUNBOOK.md,
# Section 3) - Windows' path to Docker goes through WSL2, which has its own
# failure modes (BIOS virtualization disabled, corporate policy, missing
# reboot) that a bash-under-WSL port would hide rather than surface.
#
# Usage (run from the repo root, in an elevated or normal PowerShell prompt):
#   .\install.ps1

$ErrorActionPreference = "Stop"
$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "== Greybox installer (Windows) =="
Write-Host ""

# ---------------------------------------------------------------------------
# Stage 1: install the CLI. No Docker/WSL check here - this must work on a
# locked-down corporate machine where Docker/virtualization is blocked
# entirely, or before the user has decided whether they want the full engine.
# ---------------------------------------------------------------------------

function Get-PythonCommand {
    foreach ($candidate in @("python", "py")) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            return $candidate
        }
    }
    return $null
}

$python = Get-PythonCommand
if (-not $python) {
    Write-Host "[!] Python 3.10+ wasn't found. Install it from https://python.org (check " -ForegroundColor Red
    Write-Host "    'Add python.exe to PATH' during setup), then re-run this script." -ForegroundColor Red
    exit 1
}

Write-Host "[*] Installing the greybox CLI..."
$pipx = Get-Command pipx -ErrorAction SilentlyContinue
if ($pipx) {
    pipx install --force "$RepoDir\cli"
} else {
    & $python -m pip install --user "$RepoDir\cli"
}
Write-Host "[+] greybox CLI installed." -ForegroundColor Green

# Config lives at %USERPROFILE%\.greybox\.env - same canonical location the
# CLI itself looks for, matching install.sh's ~/.greybox/.env on Linux/Mac.
$GreyboxHome = "$env:USERPROFILE\.greybox"
New-Item -ItemType Directory -Force -Path $GreyboxHome | Out-Null
$EnvPath = "$GreyboxHome\.env"
if (-not (Test-Path $EnvPath)) {
    Copy-Item "$RepoDir\.env.example" $EnvPath
    Write-Host "[+] Created $EnvPath (local LLM backend, no cloud keys required by default)."
}

Write-Host ""
Write-Host "[+] CLI installed and ready. Try it now, with zero Docker footprint:"
Write-Host "      greybox config"
Write-Host ""

# ---------------------------------------------------------------------------
# Stage 2: optional, separate - the full scanning engine. On Windows this
# means WSL2 first, then Docker Desktop, then the same `greybox setup` used
# on Linux/Mac. Every check here names the actual blocker rather than
# surfacing a generic Docker failure, since that's the exact moment a
# non-technical user gives up.
# ---------------------------------------------------------------------------

$response = Read-Host "Set up the full scanning engine now? WSL2 + Docker + Kali container (~3-4GB, includes Metasploit) + local LLM models pulled separately after - may require a reboot for WSL2. [y/N]"
if ($response -notmatch '^[Yy]') {
    Write-Host ""
    Write-Host "[*] Skipped. Run 'greybox setup' whenever you're ready for the full engine."
    Write-Host "    Until then, hunter_email and crtsh (no Docker needed) and dry-run intent"
    Write-Host "    parsing already work."
    Write-Host ""
    Write-Host "== Done =="
    exit 0
}

# --- Check 1: is virtualization enabled in firmware at all? ---
# This is the check that saves a confused user from fighting WSL2 install
# errors for an hour before finding a BIOS setting.
try {
    $computerInfo = Get-ComputerInfo -Property "HyperVRequirementVirtualizationFirmwareEnabled"
    if (-not $computerInfo.HyperVRequirementVirtualizationFirmwareEnabled) {
        Write-Host ""
        Write-Host "[!] Virtualization appears disabled in your system firmware (BIOS/UEFI)." -ForegroundColor Red
        Write-Host "    WSL2 and Docker Desktop both require it. Enable 'Intel VT-x' / 'AMD-V'" -ForegroundColor Red
        Write-Host "    (the exact name varies by manufacturer) in your BIOS settings, then" -ForegroundColor Red
        Write-Host "    re-run this script. The CLI you already installed still works without this." -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[*] Couldn't confirm virtualization firmware state automatically - continuing," -ForegroundColor Yellow
    Write-Host "    but if WSL2 setup fails below, this is the first thing to check in BIOS." -ForegroundColor Yellow
}

# --- Check 2: is WSL2 (and the Virtual Machine Platform feature) enabled? ---
$wslFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
$vmPlatform = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform

if ($wslFeature.State -ne "Enabled" -or $vmPlatform.State -ne "Enabled") {
    Write-Host ""
    Write-Host "[!] WSL2 isn't fully enabled yet - Docker Desktop needs it as a backend." -ForegroundColor Yellow
    Write-Host "    Enabling it requires a reboot, so this script won't do it silently." -ForegroundColor Yellow
    $wslResponse = Read-Host "Enable WSL2 now? This will reboot your machine when done. [y/N]"
    if ($wslResponse -match '^[Yy]') {
        Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart
        Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
        Write-Host ""
        Write-Host "[+] WSL2 features enabled. Please reboot, then re-run this script to continue" -ForegroundColor Green
        Write-Host "    with Docker Desktop and the Kali/Ollama setup." -ForegroundColor Green
        exit 0
    } else {
        Write-Host ""
        Write-Host "[*] Skipped. The CLI already works without this. Run this script again"
        Write-Host "    (or 'greybox setup') once WSL2 is enabled."
        exit 0
    }
}
Write-Host "[+] WSL2 is enabled."

# --- Check 3: Docker Desktop ---
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Host ""
    Write-Host "[!] Docker Desktop isn't installed." -ForegroundColor Yellow
    $dockerResponse = Read-Host "Install it via winget now? (You'll need to complete Docker Desktop's own first-run setup afterward) [y/N]"
    if ($dockerResponse -match '^[Yy]') {
        winget install --id Docker.DockerDesktop -e
        Write-Host ""
        Write-Host "[!] Docker Desktop installed. Launch it once from the Start menu to finish" -ForegroundColor Yellow
        Write-Host "    its own setup (license terms, WSL2 integration prompt), then re-run" -ForegroundColor Yellow
        Write-Host "    'greybox setup' to continue." -ForegroundColor Yellow
        exit 0
    } else {
        Write-Host "[*] Skipped. Install Docker Desktop manually, then run 'greybox setup'."
        exit 0
    }
}
Write-Host "[+] Docker found."

# --- Hand off to the same `greybox setup` logic used on Linux/Mac ---
# (subprocess calls to docker/git/ollama are OS-agnostic, so there's one
# implementation instead of a parallel Windows-specific copy.)
greybox setup

Write-Host ""
Write-Host "== Done =="
Write-Host "Try:"
Write-Host "  greybox scan example.com"
Write-Host "  greybox scope example.com"
Write-Host "  greybox ask `"scan for open ports`""
Write-Host "  greybox config"