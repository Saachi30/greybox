#!/bin/bash
# greybox httprobe Wrapper Script
# Takes a domain (or a file of hosts already on disk) and reports which
# ones respond over HTTP/HTTPS. Most useful right after subdomain_enum.sh -
# point it at that output file to filter dead subdomains out.

set -euo pipefail

INPUT="$1"
OUTPUT_DIR="${2:-/root/workdir/scans}"

if [ -z "$INPUT" ]; then
    echo "Usage: $0 <domain_or_hostlist_file> [output_dir]"
    echo "Example: $0 example.com /root/scans"
    echo "Example: $0 /root/workdir/scans/subdomains_example.com_*.txt /root/scans"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="$OUTPUT_DIR/httprobe_${TIMESTAMP}.txt"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           greybox httprobe                                 ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

if [ -f "$INPUT" ]; then
    echo "[*] Reading hosts from file: $INPUT"
    cat "$INPUT" | httprobe -c 20 -t 5000 | tee "$OUTPUT_FILE"
else
    echo "[*] Single host: $INPUT"
    echo "$INPUT" | httprobe -c 20 -t 5000 | tee "$OUTPUT_FILE"
fi

ALIVE_COUNT=$(wc -l < "$OUTPUT_FILE")
echo ""
echo "[+] $ALIVE_COUNT host(s) responded."
echo "[+] Results saved to: $OUTPUT_FILE"