# Testing Checklist

This mirrors the deployment doc's developer-testing section. Two kinds of
entries below: things actually run and verified while building this
(marked ✅, with what was checked), and things that need a real machine
this sandbox couldn't provide (marked ⬜, with what to do).

Keeping these separate is the point: a checklist that silently claims
untested things works undermines the whole "no dark patterns, be concrete"
posture the landing page takes.

## What was actually verified in this build session

✅ **Packaging correctness.** `pip install ./cli` into a clean, isolated
venv, run from `/tmp` with no repo checkout anywhere nearby - confirmed
`core`, `report`, and `greybox_cli` all import correctly and `greybox
--help` runs. This was a real bug before (a `sys.path` hack that only
worked when run from inside the source tree) - now fixed via
`cli/pyproject.toml`'s explicit `package-dir` mapping.

✅ **Staged install, Linux, no Docker present.** Ran `install.sh` end to
end in a scratch `$HOME` with Docker genuinely absent from PATH. Confirmed
Stage 1 completes successfully, `~/.greybox/.env` is created, and `greybox
config` / `greybox scope` / `greybox ask` (keyword-fallback path) all work
immediately afterward with zero Docker footprint.

✅ **`greybox setup` failure mode without Docker.** Confirmed it exits with
a clear, specific message rather than a stack trace or generic error.

✅ **Full tool registry routing.** Every tool in `core/tools.py` (`nmap`,
`nikto`, `sqlmap`, `subdomain_enum`, `whatweb`, `httprobe`, `hunter_email`,
`crtsh`) resolves correctly through `greybox ask`'s plain-English keyword
fallback, with the right preview shown and scope enforcement applied.

✅ **`LLM_BACKEND` local/hosted toggle and fallback behavior.** Tested:
default (local, Ollama unreachable) → clean message, no crash. `hosted`
with no URL configured → warns, falls back to local. `hosted` with an
unreachable URL → warns, falls back to local. Both hosted and local
unreachable → warns twice, returns an empty summary rather than raising,
so report generation still completes.

✅ **End-to-end report generation**, including the new backend-status
footer, with no LLM backend reachable at all (worst case) - confirms a
real PDF is still produced.

✅ **HTML structural sanity** on `website/index.html` (tag balance via
Python's `html.parser`) and a placeholder-link audit across the whole repo.

## What still needs a real machine (couldn't be done in this sandbox)

⬜ **macOS: build the menu bar app.** `menubar/` was written to standard
SwiftUI/AppKit patterns but has never been compiled - this sandbox has no
macOS toolchain. First real build should happen via
`menubar/scripts/build_app_bundle.sh` on an actual Mac before relying on
it. Check especially: the AppleScript strings in `BrowserTab.swift`
against each real browser, and the Automation permission prompt flow on
an account that's never granted it.

⬜ **Windows: `install.ps1` end to end.** Written carefully against
documented `Get-WindowsOptionalFeature`/`Get-ComputerInfo` behavior, but
never executed - no Windows environment available here. Test on:
- A clean Windows VM with WSL2 *not yet enabled* (highest-value test -
  this is the path most likely to have a bug that only shows up here).
- A VM with WSL2 enabled but Docker Desktop not installed.
- A VM with virtualization disabled in firmware settings, to confirm the
  "disabled in firmware" message actually fires rather than a generic
  failure.

⬜ **macOS `install.sh` path + Homebrew tap.** The bash installer was only
exercised on Linux in this session. macOS's `pip`/`pipx` behavior and
Homebrew's `brew tap`/`brew install` flow (once a tap repo exists) should
be run on both Apple Silicon and Intel if supporting both, per the
deployment doc - model performance genuinely differs between them.

⬜ **`greybox setup`'s git-clone path.** Verified the Docker-missing exit
path and the "found compose file in cwd" path; never exercised the actual
"no local checkout, clone `GREYBOX_REPO_URL` into `~/.greybox/engine`"
path, since that requires a real published repo URL and network access
this sandbox's allowlist doesn't include.

⬜ **Full Kali image build.** `security-core/Dockerfile.kali` downloads
subfinder/nuclei/httpx/gobuster/httprobe releases and installs `whatweb`
via apt - never actually built here (no Docker in this sandbox). Build it
once before publishing and confirm each binary lands where the wrapper
scripts expect it.

⬜ **Real report quality, both backends**, against actual scan output -
this session only tested the code paths (fallback, backend selection,
footer), not the quality/usefulness of a model's actual summary. Run this
once real Ollama models are pulled, and again if you stand up a hosted
endpoint.

⬜ **Landing page rendering.** `website/index.html` was checked for tag
balance and correct links, but never opened in a real browser - view it in
one before publishing, particularly the OS-detection tab logic in
`script.js` (test by spoofing each `navigator.userAgent` or just checking
on real Windows/Mac/Linux machines) and mobile layout at narrow widths.

⬜ **Uninstall / cleanup**, all three OSes, per the deployment doc's point
that an incomplete uninstall undermines the trust claims the landing page
makes. `docs/RUNBOOK.md` Section 9 documents the intended steps; actually
run them and confirm nothing's left behind.

## Before every release (once the above baseline is solid)

1. Re-run the clean-VM matrix above per platform, not just the one you
   develop on day to day.
2. Diff the install commands shown on `website/index.html` against the
   actual `install.sh`/`install.ps1` in the repo - drift here is exactly
   the kind of thing that breaks the "view script" trust link.
3. Confirm disk-space/RAM checks (if added to the installers beyond what's
   here now) actually gate the install rather than just being
   documentation.
4. Re-check the hosted-inference opt-in path for regressions: still no
   pre-checked box, still an explicit setting rather than a default.
5. Tag the installer scripts to match the release, so a landing-page "view
   script" link always resolves to what that page deploy actually points
   at, not a moving `main` branch.
