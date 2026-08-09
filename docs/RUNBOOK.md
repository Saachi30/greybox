# Greybox Runbook

Everything needed to get from a fresh clone to a working local install, plus
the optional pieces (menu bar app, telemetry service, Homebrew distribution).
Written to be followed top to bottom on a clean machine.

---

## 0. Prerequisites

| Requirement | Why | Check |
|---|---|---|
| Docker + Docker Compose | Runs the Kali tools container and the backend | `docker --version` |
| Ollama | Local LLM for intent parsing and report writing | `ollama --version` |
| Python 3.10+ | The CLI and backend | `python3 --version` |
| macOS 13+, Xcode CLI tools | Only if building the menu bar app | `xcode-select --version` |

Install Docker from https://docs.docker.com/engine/install/ and Ollama from
https://ollama.com if you don't have them yet.

---

## 1. Get the code and run the installer

```bash
git clone <your-repo-url> greybox
cd greybox
./install.sh          # Linux / macOS
```

```powershell
# Windows (PowerShell)
git clone <your-repo-url> greybox
cd greybox
.\install.ps1
```

Both installers are staged into two independent steps, on purpose:

**Stage 1 - install the CLI.** No Docker check happens here. This has to
work even on a locked-down/corporate machine where Docker is blocked
entirely. It installs `greybox` onto your PATH (via `pipx` if you have it,
otherwise `pip install --user`) and writes `~/.greybox/.env` (or
`%USERPROFILE%\.greybox\.env` on Windows) from `.env.example`. At this
point `greybox config`, `greybox scope`, dry-run intent parsing, and the
two tools that need no scanning engine at all (`hunter_email`, `crtsh`)
already work.

**Stage 2 - set up the full engine (optional, separately confirmed).**
This is where the multi-GB downloads happen: the Kali container and local
LLM models. Say no at install time and run `greybox setup` whenever you're
ready - it's the same command either way. On Windows, this stage checks
firmware virtualization and WSL2 state *before* touching Docker at all,
and never triggers a surprise reboot - see Section 2.5 below.

If you say no to Stage 2, or the script exits early for any reason, the
manual steps below get you to the same place.

---

## 2. Manual setup (if you skipped the installer, or want to understand each step)

### 2.1 Configure environment

```bash
cp .env.example ~/.greybox/.env
```

Open it and fill in anything you want to use:

- `GREYBOX_LLM_BACKEND` - `local` (default) or `hosted`. Leave this as
  `local` unless you've deliberately decided to offload report-writing to
  a remote endpoint - see Section 2.6. Intent parsing (mapping your
  requests to tool calls) is always local regardless of this setting.
- `HUNTER_API_KEY` - only needed for the `hunter_email` tool. Get a free-tier
  key at https://hunter.io. Everything else works without it.
- `GREYBOX_TELEMETRY_OPT_IN` / `GREYBOX_TELEMETRY_URL` - leave blank/false
  unless you've deployed the telemetry service yourself (Section 6) and
  want to track installs.
- Ollama host/model names have sane defaults; only change them if you're
  running Ollama somewhere other than `localhost:11434` or want different
  models.

### 2.2 Build and start the Kali + backend containers

```bash
docker compose build
docker compose up -d
docker compose ps        # both services should show "healthy" within ~30s
```

The Kali image build downloads several tools (subfinder, nuclei, httpx,
gobuster, httprobe) and clones nikto from GitHub, so the first build takes
a few minutes. Subsequent builds are cached.

Or just run `greybox setup`, which does the above (and clones this repo
into `~/.greybox/engine` first if you installed the CLI standalone via
`pipx install greybox-cli` without a local checkout).

### 2.3 Set up Ollama and pull models

```bash
ollama serve &                  # if not already running as a background service
ollama pull llama3.2:3b         # CLI intent parsing - small and fast
ollama pull llama3.1:8b         # report writing - needs more RAM/VRAM
```

If you're on constrained hardware, `llama3.2:3b` alone is enough to get
started; report summaries will just fall back to a plain notice if the
report model isn't pulled (see `core/llm.py` / `report/generate.py`).

### 2.5 Windows: WSL2 and Docker Desktop

`install.ps1` checks these in order, before ever touching Docker, and
never triggers a reboot without asking first:

1. **Firmware virtualization** (Intel VT-x / AMD-V). If this is disabled,
   the script tells you plainly - "virtualization appears disabled in your
   system firmware" - rather than surfacing a generic Docker error later.
   The exact BIOS menu location varies by manufacturer.
2. **WSL2 + Virtual Machine Platform Windows features.** If either isn't
   enabled, the script asks before enabling them, since doing so requires
   a reboot. Answering no here still leaves the CLI fully usable - only
   the full engine is blocked.
3. **Docker Desktop.** If missing, the script offers `winget install
   Docker.DockerDesktop`, then tells you to complete Docker Desktop's own
   first-run setup (license terms, WSL2 integration toggle) before
   continuing.

Corporate machines with virtualization disabled by policy, or Docker
Desktop blocked by licensing terms, are real and common failure modes here
- not edge cases. In both, Stage 1 (the CLI) still works.

### 2.6 Local vs. hosted report-writing inference

Two genuinely different things, only one of which is ever a config option:

- **Scan execution (the Kali container) always runs on your own machine.**
  There is no setting that changes this. If you're evaluating whether to
  centralize anything for a team, this is the part that can't be
  centralized - see `README.md`'s "Scan execution vs. inference" section
  for why.
- **Report-writing inference** can be offloaded via:
  ```
  GREYBOX_LLM_BACKEND=hosted
  GREYBOX_HOSTED_INFERENCE_URL=https://your-endpoint/v1
  GREYBOX_HOSTED_INFERENCE_KEY=your-key-if-needed
  ```
  Any OpenAI-compatible `/chat/completions` endpoint works - your own
  self-hosted vLLM/Ollama with a public URL, or a third-party provider.
  If the URL is missing or the endpoint is unreachable, `generate_text()`
  in `core/llm.py` prints a loud warning and falls back to local Ollama
  rather than failing silently or hanging. The report itself states which
  backend actually wrote it, in its footer.

### 2.4 Install the CLI directly (without the installer script)

```bash
pipx install ./cli
# or, without pipx:
pip install --user -e ./cli
```

Confirm it's on PATH:

```bash
greybox --help
```

---

## 3. Using it

```bash
greybox scope example.com
```

Declares your authorized target for this session. Everything you ask for
afterward is checked against this scope.

```bash
greybox ask "check open ports"
greybox ask "find subdomains"
greybox ask "identify website technologies"
greybox ask "check certificate transparency logs"
greybox ask "find email addresses"
```

Each one shows the exact command (or API call) it's about to run and waits
for `y` before doing anything. Nothing auto-executes.

```bash
greybox chat
```

Same thing as a REPL, so you don't retype `greybox ask` each time.

```bash
greybox sessions
greybox report generate <session_id>
```

Lists local sessions and turns one into a PDF at `~/.greybox/reports/<id>.pdf`.

```bash
greybox config
```

Shows what's actually configured and reachable right now: whether local
Ollama is up, which report backend is active (local/hosted), whether
Docker and the Kali container are available, whether `HUNTER_API_KEY` is
set. This is the first command to run when something isn't working.

```bash
greybox setup
```

Runs Stage 2 of the install (Section 1) whenever you're ready for it -
safe to run multiple times, and works whether or not you're inside the
repo checkout (it clones one into `~/.greybox/engine` if needed).

### Full tool list

| Tool | What it does | Needs |
|---|---|---|
| `nmap` | port scan / service detection | - |
| `nikto` | web server vulnerability scan | - |
| `sqlmap` | SQL injection testing (destructive tier) | a URL with a query string |
| `subdomain_enum` | subfinder + theHarvester | - |
| `whatweb` | website technology fingerprinting | - |
| `httprobe` | check which hosts respond over HTTP/S | run after `subdomain_enum` |
| `privesc_linux` / `privesc_windows` | privilege escalation enumeration (destructive tier) | an existing foothold |
| `metasploit` | auxiliary enumeration only, no exploitation | - |
| `hunter_email` | email discovery via hunter.io (API) | `HUNTER_API_KEY` in `.env` |
| `crtsh` | subdomain discovery via certificate transparency (API) | - |

---

## 4. Testing the backend directly

Useful for debugging, or if you're building something else against it.

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"scope": "example.com"}'
# -> {"id": "...", "scope": "example.com", ...}

curl -X POST http://localhost:8000/api/scan \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<id from above>", "tool": "nmap", "args": {"target": "example.com", "scan_type": "quick"}}'

curl -X POST http://localhost:8000/api/quickscan \
  -H "Content-Type: application/json" \
  -d '{"domain": "example.com"}'
# runs whatweb + a quick nmap, creates/reuses a session for that domain -
# this is the same endpoint the menu bar app calls

curl -X POST http://localhost:8000/api/sessions/<id>/report
# -> {"report_path": "/root/.greybox/reports/<id>.pdf"}
```

Note the backend runs `/api/scan` and `/api/quickscan` without its own
confirmation step - it trusts whatever called it (CLI, menu bar app) to
have already confirmed with the user. Don't expose port 8000 beyond
localhost/your own machine.

---

## 5. Building the macOS menu bar app

This step only works on macOS - Swift's AppKit isn't available on Linux,
so this can't be built or tested in a Linux CI runner or this container.

```bash
cd menubar
./scripts/build_app_bundle.sh
open dist/Greybox.app
```

First launch will prompt for Automation permission (needed to read the
active browser tab) - approve it via the system dialog. Grant it per
browser you use (Safari, Chrome, Brave, Edge, Arc are supported).

To keep it running after login:

```bash
cp -R dist/Greybox.app /Applications/
```

Then add it in System Settings → General → Login Items.

The app is a pure client of the backend (`localhost:8000`) - make sure
`docker compose up -d` from Section 2.2 is running first, or the popover
will show "Backend isn't running".

See `menubar/README.md` for what the app does and doesn't do.

---

## 6. Deploying the telemetry service (optional)

Skip this entirely unless you want install/usage counts across everyone
using greybox. It's a single-table SQLite service, no scan data ever
touches it.

### Option A: run it on a small VPS directly

```bash
# on the VPS
git clone <your-repo-url> greybox
cd greybox/telemetry
pip install fastapi "uvicorn[standard]"
uvicorn app:app --host 0.0.0.0 --port 9000
```

For a persistent setup, wrap it in a systemd unit:

```ini
# /etc/systemd/system/greybox-telemetry.service
[Unit]
Description=Greybox telemetry
After=network.target

[Service]
WorkingDirectory=/opt/greybox/telemetry
ExecStart=/usr/bin/uvicorn app:app --host 0.0.0.0 --port 9000
Restart=always
User=nobody

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now greybox-telemetry
```

Put it behind a reverse proxy (Caddy/Nginx) with TLS if it's internet-facing,
and consider putting basic auth on `GET /count` specifically, since that's
the only endpoint that reveals anything (aggregate install counts) - `POST
/ping` can stay open since it accepts nothing but an opaque instance id.

### Option B: Docker

```dockerfile
# telemetry/Dockerfile (not included by default - add if you want this route)
FROM python:3.12-slim
WORKDIR /app
COPY telemetry/app.py /app/app.py
RUN pip install fastapi "uvicorn[standard]"
EXPOSE 9000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
```

```bash
docker build -f telemetry/Dockerfile -t greybox-telemetry .
docker run -d -p 9000:9000 -v greybox_telemetry_data:/app greybox-telemetry
```

### Enabling it from the client side

Once deployed, users (or you) opt in via `.env`:

```
GREYBOX_TELEMETRY_OPT_IN=true
GREYBOX_TELEMETRY_URL=https://your-telemetry-host
```

Check counts:

```bash
curl https://your-telemetry-host/count
# -> {"installs": 42, "total_pings": 918}
```

---

## 7. Distributing via Homebrew (once you're ready to publish)

Templates are in `packaging/homebrew/`.

1. Tag and push a release: `git tag v0.1.0 && git push --tags`, then create
   a GitHub release with that tag.
2. For the CLI formula (`greybox.rb`): update the `url` to point at the
   release tarball, compute its sha256 (`shasum -a 256 <file>`), fill it in.
3. For the menu bar cask (`greybox-menubar.rb`): build `Greybox.app`
   (Section 5), zip it (`ditto -c -k --sequesterRsrc dist/Greybox.app
   Greybox.app.zip`), attach it to the same GitHub release, update the
   cask's `url`/`sha256` accordingly.
4. Create a tap repo (`homebrew-greybox`) containing both files under
   `Formula/` and `Casks/` respectively.
5. Users then run:
   ```bash
   brew tap Saachi30/greybox
   brew install greybox
   brew install --cask greybox-menubar
   ```

---

## 8. Updating

```bash
cd greybox
git pull
docker compose build        # rebuild if security-core or backend changed
docker compose up -d
pipx upgrade greybox-cli    # or: pip install --user -e ./cli --force-reinstall
```

## 9. Uninstalling

```bash
docker compose down -v      # stops containers and removes the kali_workdir volume
pipx uninstall greybox-cli  # or: pip uninstall greybox-cli
rm -rf ~/.greybox           # sessions, reports, cached instance id
```

Remove `/Applications/Greybox.app` and its Login Item entry if you
installed the menu bar app.

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Ollama isn't reachable` in the CLI | Ollama not running | `ollama serve` |
| `docker exec greybox-kali ...` fails with "No such container" | Containers not started, or name mismatch | `docker compose up -d`; confirm `KALI_CONTAINER_NAME` in `.env` matches `container_name` in `docker-compose.yml` |
| `hunter_email` always returns the "not set" message | Missing API key | Add `HUNTER_API_KEY` to `.env`, restart the CLI (or backend container) so it reloads |
| `crtsh` returns "temporarily unavailable" | crt.sh is genuinely rate-limiting/down, or no outbound internet from wherever the call runs | Retry later; if running inside a locked-down network, confirm outbound HTTPS is allowed |
| Menu bar popover shows "Backend isn't running" | `docker compose` stack isn't up | `docker compose up -d` on the machine running the backend |
| Menu bar app can't read the active tab | Automation permission not granted | System Settings → Privacy & Security → Automation → enable Greybox for your browser |
| Report PDF is missing the AI-written summary | Report model (`llama3.1:8b`) not pulled, or Ollama down | `ollama pull llama3.1:8b`; confirm `ollama serve` is running |
| `pip install --break-system-packages` errors on Debian/Ubuntu | Externally-managed Python environment | Use `pipx` instead, or a virtualenv |
| `greybox: command not found` right after install | `~/.local/bin` (pip) or pipx's bin dir isn't on PATH | Open a new shell, or add the dir to PATH manually; the installer prints where it installed to |
| Report footer says "hosted" but you expected local | `GREYBOX_LLM_BACKEND=hosted` is set somewhere in `.env` | `greybox config` shows the active backend; set it back to `local` |
| Hosted inference silently seems to "just use local" | This is intentional - see Section 2.6. A missing/unreachable hosted endpoint fails loud (a printed warning) and falls back to local rather than erroring out the whole report | Check the warning text for the specific reason (missing URL vs. connection failure) |
| `install.ps1` stops after enabling WSL2 | Expected - a reboot is required before Docker can use WSL2 as a backend | Reboot, then re-run `.\install.ps1` or `greybox setup` |
| Windows: "virtualization appears disabled in firmware" | VT-x/AMD-V disabled in BIOS/UEFI | Enable it in your BIOS/UEFI settings (name varies by manufacturer), reboot, retry |