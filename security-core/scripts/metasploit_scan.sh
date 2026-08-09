#!/bin/bash
# GREYBOX Metasploit Wrapper Script
# Automated vulnerability exploitation framework

set -euo pipefail

ACTION="$1"
TARGET="$2"
PORT="${3:-}"
OUTPUT_DIR="${4:-/root/workdir/scans}"

if [ -z "$ACTION" ] || [ -z "$TARGET" ]; then
    echo "Usage: $0 <action> <target> [port] [output_dir]"
    echo ""
    echo "Actions:"
    echo "  scan        - Port scan and service enumeration"
    echo "  smb         - SMB enumeration and exploitation"
    echo "  ssh         - SSH enumeration and brute force"
    echo "  web         - Web application scanning"
    echo "  exploit     - Auto-exploit (requires port)"
    echo ""
    echo "Example: $0 scan 192.168.1.100"
    echo "Example: $0 exploit 192.168.1.100 445 /root/scans"
    exit 1
fi

if ! command -v msfconsole >/dev/null 2>&1; then
    echo "[-] msfconsole not found in this container." >&2
    echo "[-] Metasploit Framework may not have finished installing, or the image needs a rebuild." >&2
    exit 127
fi

mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="$OUTPUT_DIR/msf_${TARGET//[.\/]/_}_${TIMESTAMP}.txt"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           GREYBOX Metasploit Framework                      ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Action: $ACTION"
echo "Target: $TARGET"
echo "Port: ${PORT:-auto-detect}"
echo "Output: $OUTPUT_FILE"
echo ""

case "$ACTION" in
    scan)
        echo "[*] Running Metasploit port scan..."
        msfconsole -q -x "
            use auxiliary/scanner/portscan/tcp;
            set RHOSTS $TARGET;
            set THREADS 10;
            run;
            exit;
        " | tee "$OUTPUT_FILE"
        ;;

    smb)
        echo "[*] Running SMB enumeration..."
        msfconsole -q -x "
            use auxiliary/scanner/smb/smb_version;
            set RHOSTS $TARGET;
            run;
            use auxiliary/scanner/smb/smb_enumshares;
            set RHOSTS $TARGET;
            run;
            exit;
        " | tee "$OUTPUT_FILE"
        ;;

    ssh)
        echo "[*] Running SSH enumeration..."
        msfconsole -q -x "
            use auxiliary/scanner/ssh/ssh_version;
            set RHOSTS $TARGET;
            run;
            exit;
        " | tee "$OUTPUT_FILE"
        ;;

    web)
        echo "[*] Running web application scan..."
        msfconsole -q -x "
            use auxiliary/scanner/http/http_version;
            set RHOSTS $TARGET;
            run;
            use auxiliary/scanner/http/dir_scanner;
            set RHOSTS $TARGET;
            run;
            exit;
        " | tee "$OUTPUT_FILE"
        ;;

    exploit)
        if [ -z "$PORT" ]; then
            echo "[-] Port required for exploit action"
            exit 1
        fi
        echo "[*] WARNING: Running auto-exploit (destructive operation)"
        echo "[*] Attempting exploitation on $TARGET:$PORT"
        msfconsole -q -x "
            search type:exploit platform:windows port:$PORT;
            use exploit/multi/handler;
            set LHOST 0.0.0.0;
            set LPORT 4444;
            show options;
            exit;
        " | tee "$OUTPUT_FILE"
        ;;

    *)
        echo "[-] Unknown action: $ACTION"
        exit 1
        ;;
esac

echo ""
echo "[+] Metasploit operation completed!"
echo "[+] Results saved to: $OUTPUT_FILE"