# greybox

**Security testing, made simple.**

Greybox is a local-first pentesting assistant. Describe what you want to check in plain English, review the exact command it proposes, and let it run the real security tools on your own machine — nothing leaves your machine unless you decide to share it.

[![PyPI](https://img.shields.io/pypi/v/greybox-cli)](https://pypi.org/project/greybox-cli/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

> Only test systems you own or are explicitly authorized to test. See [Legal & ethical use](#legal--ethical-use).

---

## Table of contents

- [Why greybox](#why-greybox)
- [How it works](#how-it-works)
- [Install](#install)
- [Quickstart](#quickstart)
- [Optional local AI (Ollama)](#optional-local-ai-ollama)
- [Requirements](#requirements)
- [Architecture](#architecture)
- [Security & privacy](#security--privacy)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Legal & ethical use](#legal--ethical-use)
- [License](#license)

## Why greybox

Running a real security assessment usually means knowing which of a dozen tools to reach for, remembering their flags, and stitching the output together into something readable. Greybox collapses that into a conversation:

- **Plain English in, real tool out.** Ask for "the open ports" or "what's this site running" and greybox maps it to the right scanner and flags.
- **Nothing runs blind.** Every proposed command is shown to you before execution — you approve it, or you don't.
- **Local by default.** The scanning engine, your target list, and your findings all stay on your machine unless you explicitly export them.
- **Works without an LLM.** The core CLI, recon sweep, and reporting work with zero AI dependency. Add local inference only if you want richer natural-language understanding.

## How it works

1. **Declare your target.** Define the site or system you're authorized to test. Greybox keeps every subsequent action scoped to it and refuses requests outside that scope.
2. **Ask what you want to check.** Describe the check in plain English — no need to memorize tool names or flags.
3. **Review before execution.** Greybox shows you the exact command it intends to run. Nothing executes without explicit confirmation.
4. **Run locally, collect results.** The actual scan runs inside greybox's local environment. Findings are stored locally and can be compiled into a report.

## Install

The CLI is lightweight and installs with `pip`/`pipx`. The full scanning engine runs inside a Dockerized Kali environment, set up separately with `greybox setup`.

### macOS

```bash
pipx install greybox-cli

# Requires Docker Desktop installed and running
greybox setup
```

### Windows

```powershell
py -m pip install greybox-cli

# Requires Docker Desktop with WSL2 enabled
greybox setup
```

### Linux

```bash
pipx install greybox-cli

# Requires Docker, daemon running
greybox setup
```

Ollama is optional on every platform — install it separately if you want local AI assistance (see [below](#optional-local-ai-ollama)).

## Quickstart

```bash
# Declare what you're authorized to test
greybox scope example.com

# Ask in plain English
greybox ask "check open ports"

# Or run the standard recon sweep directly
greybox scan example.com

# List past sessions to find the session id you need
greybox sessions

# Turn a session's findings into a report
greybox report generate <session-id>
```

## Optional local AI (Ollama)

Greybox works fully without an LLM — target scoping, supported checks, the standard recon sweep, and report generation all function out of the box.

Adding [Ollama](https://ollama.com) gives you:

- More flexible natural-language intent parsing for `greybox ask`
- AI-written report summaries and vulnerability explanations

```bash
# Install Ollama, then:
ollama serve

# Smaller model — intent parsing
ollama pull llama3.2:3b

# Larger model — report writing
ollama pull llama3.1:8b
```

All inference runs locally through Ollama. No prompt, target, or result is sent to a cloud LLM.

## Requirements

| Component  | Required?     | Purpose                                                        |
|------------|----------------|------------------------------------------------------------------|
| Python 3.10+ | Yes          | Runs the greybox CLI.                                           |
| Docker     | For full scans | Runs the isolated Kali security environment.                    |
| Ollama     | Optional       | Local LLM inference for NL understanding and report writing.    |
| Kali tools | Via Docker     | Perform the actual security and reconnaissance checks.          |

## Architecture

```
┌──────────────┐     plain-English request      ┌───────────────────┐
│  greybox CLI │ ───────────────────────────────▶│  intent → command  │
│              │                                  │  (rules, +Ollama)  │
└──────┬───────┘                                  └─────────┬─────────┘
       │ shows proposed command, waits for confirm           │
       ▼                                                      ▼
┌──────────────┐    docker exec    ┌───────────────────────────────┐
│  confirmation │ ─────────────────▶│  Dockerized Kali environment  │
│    prompt     │                   │  (nmap, whatweb, nikto, ...)  │
└──────────────┘                    └───────────────┬───────────────┘
                                                       │ raw results
                                                       ▼
                                            ┌────────────────────┐
                                            │  local session store │
                                            │  + report generator  │
                                            └────────────────────┘
```

## Security & privacy

Greybox is built around the idea that security testing data should stay under the tester's control:

- **Scan traffic stays local.** The security tools run on your own machine.
- **No cloud LLM required.** Ollama runs language models locally.
- **Explicit confirmation.** Every proposed command is shown before it executes.
- **Local session storage.** Findings and sessions are stored on disk, not in the cloud.
- **Scope enforcement.** Requests outside the declared target are refused.
- **No default telemetry.** Analytics are opt-in and disabled by default.

## Roadmap

- **macOS menu bar companion** *(in development)* — quickly check the site you're browsing without opening a terminal, while keeping the actual testing local.

## Contributing

Greybox is an early release. If you use it, feedback on setup, scans, reports, supported systems, and anything that feels confusing is genuinely useful.

- [Open an issue](https://github.com/Saachi30/greybox/issues)
- [View source](https://github.com/Saachi30/greybox)

## Legal & ethical use

Greybox is a tool for authorized security testing only. You are responsible for ensuring you have explicit permission to test any target you scope or scan. Unauthorized scanning of systems you do not own or have written authorization to test may violate local, state, and federal law (including, in the US, the Computer Fraud and Abuse Act) as well as equivalent laws elsewhere. The maintainers assume no liability for misuse.

## License

[MIT](LICENSE)
