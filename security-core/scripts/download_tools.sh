#!/bin/bash
# GREYBOX Tool Downloader
# Downloads latest versions of security tools not in Kali repos

set -euo pipefail

TOOLS_DIR="/root/tools"
mkdir -p "$TOOLS_DIR"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     GREYBOX Security Tools Downloader                       ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# LinPEAS
echo "[*] Downloading LinPEAS..."
wget -q https://github.com/carlospolop/PEASS-ng/releases/latest/download/linpeas.sh -O "$TOOLS_DIR/linpeas.sh"
chmod +x "$TOOLS_DIR/linpeas.sh"
echo "[+] LinPEAS downloaded"

# WinPEAS
echo "[*] Downloading WinPEAS (x64)..."
wget -q https://github.com/carlospolop/PEASS-ng/releases/latest/download/winPEASx64.exe -O "$TOOLS_DIR/winPEAS.exe"
echo "[+] WinPEAS downloaded"

# PowerUp (PowerShell privilege escalation)
echo "[*] Downloading PowerUp.ps1..."
wget -q https://raw.githubusercontent.com/PowerShellMafia/PowerSploit/master/Privesc/PowerUp.ps1 -O "$TOOLS_DIR/PowerUp.ps1"
echo "[+] PowerUp.ps1 downloaded"

# Linux Exploit Suggester
echo "[*] Downloading linux-exploit-suggester..."
wget -q https://raw.githubusercontent.com/mzet-/linux-exploit-suggester/master/linux-exploit-suggester.sh -O "$TOOLS_DIR/linux-exploit-suggester.sh"
chmod +x "$TOOLS_DIR/linux-exploit-suggester.sh"
echo "[+] linux-exploit-suggester downloaded"

# Windows Exploit Suggester
echo "[*] Downloading windows-exploit-suggester..."
wget -q https://raw.githubusercontent.com/AonCyberLabs/Windows-Exploit-Suggester/master/windows-exploit-suggester.py -O "$TOOLS_DIR/windows-exploit-suggester.py"
chmod +x "$TOOLS_DIR/windows-exploit-suggester.py"
echo "[+] windows-exploit-suggester downloaded"

# SecLists (wordlists)
if [ ! -d "$TOOLS_DIR/SecLists" ]; then
    echo "[*] Cloning SecLists (wordlists)..."
    git clone --depth 1 https://github.com/danielmiessler/SecLists.git "$TOOLS_DIR/SecLists" 2>/dev/null
    echo "[+] SecLists cloned"
else
    echo "[+] SecLists already exists"
fi

# PayloadsAllTheThings
if [ ! -d "$TOOLS_DIR/PayloadsAllTheThings" ]; then
    echo "[*] Cloning PayloadsAllTheThings..."
    git clone --depth 1 https://github.com/swisskyrepo/PayloadsAllTheThings.git "$TOOLS_DIR/PayloadsAllTheThings" 2>/dev/null
    echo "[+] PayloadsAllTheThings cloned"
else
    echo "[+] PayloadsAllTheThings already exists"
fi

echo ""
echo "[+] All tools downloaded successfully!"
echo ""
echo "Tools location: $TOOLS_DIR"
ls -lh "$TOOLS_DIR"