#!/bin/bash
# GREYBOX Privilege Escalation Script - Linux
# Automated privilege escalation enumeration using LinPEAS and custom checks

set -euo pipefail

OUTPUT_DIR="${1:-/root/workdir/scans/privesc}"
TARGET_HOST="${2:-localhost}"

mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     GREYBOX Privilege Escalation - Linux                    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Target: $TARGET_HOST"
echo "Output: $OUTPUT_DIR"
echo ""

# Download LinPEAS if not present
if [ ! -f "/root/tools/linpeas.sh" ]; then
    echo "[*] Downloading LinPEAS..."
    wget -q https://github.com/carlospolop/PEASS-ng/releases/latest/download/linpeas.sh -O /root/tools/linpeas.sh
    chmod +x /root/tools/linpeas.sh
fi

# Run LinPEAS
echo "[*] Running LinPEAS enumeration..."
/root/tools/linpeas.sh -a 2>&1 | tee "$OUTPUT_DIR/linpeas_${TIMESTAMP}.txt"

# Custom privilege escalation checks
echo ""
echo "[*] Running custom privilege escalation checks..."

# Check SUID binaries
echo "[+] Checking SUID binaries..."
find / -perm -4000 -type f 2>/dev/null > "$OUTPUT_DIR/suid_binaries_${TIMESTAMP}.txt"

# Check sudo permissions
echo "[+] Checking sudo permissions..."
sudo -l 2>/dev/null > "$OUTPUT_DIR/sudo_permissions_${TIMESTAMP}.txt" || echo "Cannot check sudo" > "$OUTPUT_DIR/sudo_permissions_${TIMESTAMP}.txt"

# Check for writable /etc/passwd
echo "[+] Checking /etc/passwd permissions..."
ls -la /etc/passwd > "$OUTPUT_DIR/passwd_permissions_${TIMESTAMP}.txt"

# Check cron jobs
echo "[+] Checking cron jobs..."
cat /etc/crontab 2>/dev/null > "$OUTPUT_DIR/crontab_${TIMESTAMP}.txt" || echo "No access to crontab" > "$OUTPUT_DIR/crontab_${TIMESTAMP}.txt"
ls -la /etc/cron.* 2>/dev/null >> "$OUTPUT_DIR/crontab_${TIMESTAMP}.txt"

# Check kernel version for known exploits
echo "[+] Checking kernel version..."
uname -a > "$OUTPUT_DIR/kernel_version_${TIMESTAMP}.txt"

# Check for Docker/container escape
echo "[+] Checking for container environment..."
if [ -f "/.dockerenv" ]; then
    echo "Running in Docker container" > "$OUTPUT_DIR/container_info_${TIMESTAMP}.txt"
    ls -la /.dockerenv >> "$OUTPUT_DIR/container_info_${TIMESTAMP}.txt"
else
    echo "Not in Docker container" > "$OUTPUT_DIR/container_info_${TIMESTAMP}.txt"
fi

# Check capabilities
echo "[+] Checking file capabilities..."
getcap -r / 2>/dev/null > "$OUTPUT_DIR/capabilities_${TIMESTAMP}.txt"

# Generate summary report
cat > "$OUTPUT_DIR/privesc_summary_${TIMESTAMP}.txt" <<EOF
╔═══════════════════════════════════════════════════════════╗
║     Linux Privilege Escalation Summary                    ║
╚═══════════════════════════════════════════════════════════╝

Target: $TARGET_HOST
Timestamp: $TIMESTAMP

Files Generated:
- linpeas_${TIMESTAMP}.txt (Full LinPEAS output)
- suid_binaries_${TIMESTAMP}.txt (SUID binaries list)
- sudo_permissions_${TIMESTAMP}.txt (Sudo -l output)
- passwd_permissions_${TIMESTAMP}.txt (/etc/passwd permissions)
- crontab_${TIMESTAMP}.txt (Cron jobs)
- kernel_version_${TIMESTAMP}.txt (Kernel info)
- container_info_${TIMESTAMP}.txt (Container detection)
- capabilities_${TIMESTAMP}.txt (File capabilities)

Next Steps:
1. Review LinPEAS output for color-coded findings
2. Check SUID binaries against GTFOBins (https://gtfobins.github.io/)
3. Search for kernel exploits based on version
4. Attempt exploitation based on findings
5. Document successful privilege escalation path

⚠️  Remember: Always have authorization before exploiting!
EOF

echo ""
echo "[+] Privilege escalation enumeration completed!"
echo "[+] Results saved to: $OUTPUT_DIR"
echo ""
echo "Summary:"
cat "$OUTPUT_DIR/privesc_summary_${TIMESTAMP}.txt"