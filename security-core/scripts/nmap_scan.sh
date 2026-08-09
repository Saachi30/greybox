#!/bin/bash
# GREYBOX Nmap Wrapper Script
# Automated vulnerability scanning with nmap

set -euo pipefail

TARGET="$1"
OUTPUT_DIR="${2:-/root/workdir/scans}"
SCAN_TYPE="${3:-full}"

if [ -z "$TARGET" ]; then
    echo "Usage: $0 <target> [output_dir] [scan_type]"
    echo "Scan types: quick, full, vuln, comprehensive"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="$OUTPUT_DIR/nmap_${TARGET//[.\/]/_}_${TIMESTAMP}"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           GREYBOX Nmap Scanner                              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Target: $TARGET"
echo "Scan Type: $SCAN_TYPE"
echo "Output: $OUTPUT_FILE"
echo ""

case "$SCAN_TYPE" in
    quick)
        echo "[*] Running quick scan (top 1000 ports)..."
        nmap -T4 -F --stats-every 10s "$TARGET" -oN "$OUTPUT_FILE.txt" -oX "$OUTPUT_FILE.xml"
        ;;

    full)
        echo "[*] Running full port scan with service detection..."
        nmap -sV -sC -A -T3 --stats-every 10s "$TARGET" -p- \
            -oN "$OUTPUT_FILE.txt" \
            -oX "$OUTPUT_FILE.xml" \
            -oG "$OUTPUT_FILE.gnmap"
        ;;

    vuln)
        echo "[*] Running vulnerability detection scan..."
        nmap -sV --script vuln,vulners --stats-every 10s "$TARGET" -p- -T3 \
            -oN "$OUTPUT_FILE.txt" \
            -oX "$OUTPUT_FILE.xml"
        ;;

    comprehensive)
        echo "[*] Running comprehensive scan (service detection + OS detection + scripts + vulnerabilities)..."
        nmap -sV -sC -A -O --script "vuln,vulners,exploit" --stats-every 10s "$TARGET" -p- -T3 \
            -oN "$OUTPUT_FILE.txt" \
            -oX "$OUTPUT_FILE.xml" \
            -oG "$OUTPUT_FILE.gnmap"
        ;;

    *)
        echo "[-] Unknown scan type: $SCAN_TYPE"
        echo "Available types: quick, full, vuln, comprehensive"
        exit 1
        ;;
esac

echo ""
echo "[+] Scan completed successfully!"
echo "[+] Results saved to: $OUTPUT_FILE.*"
echo ""
echo "Files created:"
ls -lh "$OUTPUT_FILE".*