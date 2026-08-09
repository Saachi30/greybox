#!/bin/bash
# Greybox installer - Linux and macOS.
#
# Staged on purpose (see docs/RUNBOOK.md): installing the CLI never
# requires Docker. Setting up the full scanning engine (Kali container
# ~3-4GB + Ollama models ~2GB/~4.7GB) is a separate, explicitly confirmed
# step you can also run later via `greybox setup`.

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Greybox installer =="
echo ""

# ---------------------------------------------------------------------------
# Stage 1: install the CLI. No Docker check here - this must work on a
# locked-down/corporate machine where Docker is blocked entirely.
# ---------------------------------------------------------------------------

if ! command -v python3 &> /dev/null; then
    echo "[!] Python 3.10+ is required and wasn't found. Install it, then re-run this script."
    exit 1
fi

echo "[*] Installing the greybox CLI..."
if command -v pipx &> /dev/null; then
    pipx install --force "$REPO_DIR/cli"
elif command -v pip3 &> /dev/null; then
    pip3 install --user --break-system-packages "$REPO_DIR/cli" 2>/dev/null \
        || pip3 install --user "$REPO_DIR/cli"
else
    echo "[!] Neither pipx nor pip3 was found. Install Python's pip, then re-run this script."
    exit 1
fi
echo "[+] greybox CLI installed."

# Config lives at ~/.greybox/.env - the canonical location for an installed
# (not necessarily repo-checked-out) CLI. See cli/greybox_cli/cli.py for
# the full .env search order.
mkdir -p "$HOME/.greybox"
if [ ! -f "$HOME/.greybox/.env" ]; then
    cp "$REPO_DIR/.env.example" "$HOME/.greybox/.env"
    echo "[+] Created ~/.greybox/.env (local LLM backend, no cloud keys required by default)."
fi

echo ""
echo "[+] CLI installed and ready. Try it now, with zero Docker footprint:"
echo "      greybox config"
echo ""

# ---------------------------------------------------------------------------
# Stage 2: optional, separate - the full scanning engine (Docker + Kali +
# Ollama). This is where multi-GB downloads happen, so it's opt-in and
# clearly labeled as such, never bundled into "installing greybox."
# ---------------------------------------------------------------------------

read -r -p "Set up the full scanning engine now? Docker + Kali container (~3-4GB, includes Metasploit) + local LLM models pulled separately after. [y/N] " CONFIRM
if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
    # `greybox setup` handles Docker checks, fetching the engine repo if
    # this script wasn't run from inside a checkout, building, and
    # optionally pulling Ollama models - same logic either way.
    greybox setup
else
    echo ""
    echo "[*] Skipped. Run 'greybox setup' whenever you're ready for the full engine."
    echo "    Until then, hunter_email and crtsh (no Docker needed) and dry-run intent"
    echo "    parsing already work."
fi

echo ""
echo "== Done =="
echo "Try:"
echo "  greybox scan example.com"
echo "  greybox scope example.com"
echo "  greybox ask \"scan for open ports\""
echo "  greybox config"