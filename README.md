# Greybox

A local-first, natural-language pentesting assistant. Dockerized Kali tools,
a local LLM (Ollama) instead of a cloud API, and a CLI you talk to in plain
English.

Nothing about a target ever leaves your machine.

## What's here

```
greybox/
  security-core/   Dockerized Kali + tool wrapper scripts
  core/            shared logic: tool registry, session schema, LLM client, OSINT API tools
  cli/             the `greybox` command - installs standalone, no Docker required
  backend/         minimal FastAPI orchestration layer (no database)
  report/          PDF report generation from a session's findings
  telemetry/       optional, opt-in, anonymous install counter (separate service)
  menubar/         macOS menu bar companion (Swift Package, builds on macOS only)
  packaging/       Homebrew formula/cask templates for distribution
  website/         static landing page (install, requirements, trust/security)
  docs/            RUNBOOK.md (run/deploy steps) + TESTING.md (pre-release checklist)
  docker-compose.yml
  install.sh       Linux/macOS installer
  install.ps1      Windows installer (its own script, not a bash port)
```

Full step-by-step instructions to run everything locally and deploy the
optional pieces are in **`docs/RUNBOOK.md`**. `docs/TESTING.md` tracks
what's actually been verified vs. what still needs a real machine
(macOS/Windows builds couldn't be tested in the environment this was
built in) - read that before assuming everything works everywhere.

## Install is staged on purpose

Installing the `greybox` CLI never requires Docker. It works standalone -
`pipx install ./cli` or `curl ... | bash` - and gives you dry-run intent
parsing plus the two tools that need no scanning engine at all
(`hunter_email`, `crtsh`). Setting up the full engine (Kali container
~3-4GB including Metasploit, plus local LLM models: llama3.2:3b ~2GB and
llama3.1:8b ~4.7GB) is a separate, later, explicitly-confirmed step:
`greybox setup`. See `docs/RUNBOOK.md` and `website/index.html` for why
this split matters, especially on Windows where Docker means WSL2.

## Scan execution vs. inference: only one of these can be hosted

Two different things get conflated in "make this lightweight," and only
one of them is safe to centralize:

- **Scan execution (the Kali container) always runs on your own machine.**
  This isn't configurable. If nmap/sqlmap traffic against a target ever
  came from infrastructure greybox operates instead of your machine, your
  target's logs would show a third party's IP, not yours - a different and
  worse liability position.
- **Report-writing inference can be local (default) or hosted**, via
  `GREYBOX_LLM_BACKEND=local|hosted` in `.env`. By the time this runs, no
  scan traffic is involved - it's NLP over findings you already collected
  locally. Intent parsing (mapping your request to a tool call) stays
  local unconditionally either way, since it's small and latency-sensitive.
  A misconfigured hosted backend fails loud (a printed warning) and falls
  back to local rather than degrading silently.

## Quick start

```bash
git clone <this repo>
cd greybox
./install.sh          # Linux/macOS - or .\install.ps1 on Windows
```

Stage 1 installs the `greybox` CLI - no Docker needed, works immediately.
Stage 2 (separate confirmation) sets up the full engine: Kali container +
local models. Skipped it, or want to do it later? `greybox setup` runs the
same step whenever you're ready. `greybox config` tells you what's
currently configured and reachable.

You'll also want [Ollama](https://ollama.com) running on the host for
intent parsing and local report writing:

```bash
ollama serve
ollama pull llama3.2:3b     # intent parsing - always local, not configurable
ollama pull llama3.1:8b     # report writing - local by default, hosted opt-in
```

## Using it

```bash
greybox scan example.com           # full non-destructive recon sweep + report, one command
greybox scope example.com          # or declare a target and go tool-by-tool instead
greybox ask "check open ports"     # plain English -> proposed command -> confirm -> run
greybox chat                       # same thing, but a REPL instead of one-shot
greybox sessions                   # list local sessions
greybox report generate <id>       # PDF from everything logged in that session
greybox config                     # what's configured and reachable right now
greybox setup                      # set up the full Kali/Docker engine (deferrable)
greybox set-key HUNTER_API_KEY <key>  # save an API key (e.g. for email discovery)
```

Every proposed command is shown before it runs. Nothing executes without an
explicit yes. Requests for a target outside your declared scope are refused.
`greybox scan` deliberately excludes sqlmap/metasploit/privesc - those need
explicit, deliberate targeting, not a default batch run.

## Design notes

- **No cloud LLM.** The old version of this project used Gemini; recon data
  for a pentest is exactly the kind of thing that shouldn't leave your
  machine. See `core/llm.py`.
- **No database for scan data.** Sessions and findings are JSON files under
  `~/.greybox/sessions/`, with a `.sha256` sidecar per session as a simple
  local integrity/audit trail - no Postgres, no Alembic, no blockchain.
- **Analytics, if you want them.** `telemetry/` is a separate, single-table
  service you can host yourself if you want to know how many people have
  installed greybox. It's off by default (`GREYBOX_TELEMETRY_OPT_IN=false`
  in `.env`) and never receives scan data - just a random instance id and a
  counter. See `core/telemetry.py`.
- **One tool registry, two consumers.** `core/tools.py` is the single
  source of truth for what greybox can run. Both the CLI and the backend's
  `/api/scan` endpoint call into it, so a wrapper script is written once.
  It now covers nmap, nikto, sqlmap, subdomain enum, whatweb, httprobe,
  Linux/Windows privesc enumeration, and Metasploit auxiliary scans
  (Kali-container tools), plus hunter.io email discovery and crt.sh
  certificate-transparency lookups (host-side API tools, see
  `core/osint.py`) - all through the same registry, preview, and
  confirm-before-run path.
- **Menu bar companion.** `menubar/` is a native macOS Swift app: click the
  icon, see the current tab's domain, optionally run a quick scan. It's a
  thin client over the backend's `/api/quickscan` endpoint - see
  `menubar/README.md` and `docs/RUNBOOK.md` to build and install it.

## What was cut from the earlier prototype

Blockchain audit trail, Celery/Redis task queue, Postgres/NeonDB, Nginx,
DNS-verification gating, and a dual-mode Next.js frontend were all part of
an earlier, SaaS-shaped version of this idea. None of that fits a tool one
person installs and runs locally, so it isn't here. The full reasoning for
what got cut and what got kept is in `docs/greybox_plan.md` if you want the
history.

## Legal

Only run this against systems you own or have explicit written authorization
to test. The scope check in `core/schema.py` is a courtesy guardrail, not a
substitute for actual authorization.