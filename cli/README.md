# greybox-cli

**A local-first pentesting assistant — describe the check you want in plain English, review the exact command before it runs, and let it execute against your own Dockerized Kali environment.**

`greybox-cli` is the command-line entry point for greybox. It handles target scoping, translating plain-English requests into the right security tool and flags, showing you the proposed command for confirmation, and turning results into a report. The heavier scanning engine runs separately inside Docker, so this package stays small.

## Install

```bash
pip install greybox-cli
```

Then, with [Docker](https://www.docker.com/) installed and running:

```bash
greybox setup
```

## Quickstart

```bash
greybox scope example.com
greybox ask "check open ports"
greybox scan example.com
greybox report generate <session-id>
```

## What it does

- **Scopes your target.** Every action stays inside the domain/system you declare; requests outside that scope are refused.
- **Turns plain English into commands.** `greybox ask "find the technologies this site is using"` maps to the right tool automatically.
- **Confirms before executing.** Nothing runs against your target without you seeing and approving the exact command first.
- **Runs locally.** Scans execute inside a local Dockerized Kali environment; results and sessions are stored on disk, not sent to a server.
- **Reports on demand.** `greybox report generate` compiles a session's findings into a readable report.

## Optional: local AI with Ollama

The CLI works fully without any LLM. If you install [Ollama](https://ollama.com) separately, greybox uses it for more flexible natural-language parsing and AI-written report summaries — all inference stays local to your machine.

```bash
ollama serve
ollama pull llama3.2:3b   # intent parsing
ollama pull llama3.1:8b   # report writing
```

## Requirements

- Python 3.10+
- Docker (required for `greybox setup` / full scans; the CLI itself installs without it)
- Ollama (optional, for local AI features)

## Legal & ethical use

This package is intended for authorized security testing only. Only scan systems you own or have explicit written permission to test. Unauthorized scanning may violate the Computer Fraud and Abuse Act and equivalent laws in other jurisdictions. Maintainers assume no liability for misuse.

## Links

- **Source / issues:** https://github.com/Saachi30/greybox
- **Documentation:** https://github.com/Saachi30/greybox#readme
- **License:** MIT

---

*Suggested `pyproject.toml` metadata:*

```toml
[project]
name = "greybox-cli"
description = "Local-first pentesting assistant: plain-English security checks, reviewed before execution, run against your own local Docker/Kali environment."
readme = "PYPI_DESCRIPTION.md"
requires-python = ">=3.10"
keywords = ["security", "pentesting", "cli", "recon", "nmap", "docker", "kali"]
classifiers = [
    "Environment :: Console",
    "Intended Audience :: Information Technology",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3.10",
    "Topic :: Security",
]
```