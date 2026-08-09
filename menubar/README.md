# Greybox menu bar app (macOS)

A single status-bar icon. Click it, see the domain of your current browser
tab, optionally scan it. Nothing runs unless you click "Scan this site".

This is a Swift Package, not an Xcode project, so it builds from the command
line with no Xcode GUI needed - but it does need to be built **on macOS**;
this can't be compiled from Linux or in CI without a macOS runner.

## Requirements

- macOS 13+
- Xcode command line tools (`xcode-select --install`)
- The greybox backend running locally (see the main README) - this app is
  a thin client over `http://localhost:8000`, it has no scanning logic of
  its own.

## Build and run

```bash
cd menubar
./scripts/build_app_bundle.sh
open dist/Greybox.app
```

The first time it reads the active tab, macOS will prompt for Automation
permission for whichever browser is frontmost (Safari, Chrome, Brave, Edge,
Arc are supported - see `Sources/GreyboxMenuBar/BrowserTab.swift`). This is
the standard macOS permission dialog, not something greybox can skip; it's
also the mechanism that makes it obvious to the user when the app is
reading tab data, since it will never happen silently.

## Installing permanently

```bash
cp -R dist/Greybox.app /Applications/
```

To have it launch at login: System Settings → General → Login Items → add
Greybox.

## What it does and doesn't do

- Reads the frontmost browser's active tab URL **only** when you click the
  menu bar icon and then click "Scan this site" - never on a timer, never
  in the background.
- Calls `POST /api/quickscan` on the local backend, which runs a light,
  non-destructive pair of checks (whatweb + a quick nmap) - see
  `backend/app/main.py`. Anything deeper belongs in the CLI, which has the
  full tool registry and per-command confirmation.
- Can open the full PDF report for that session via "Open full report",
  which calls the same `/api/sessions/{id}/report` endpoint the CLI uses.

## Distribution (once this is stable)

The plan is a Homebrew cask sharing a tap with the CLI:

```bash
brew tap Saachi30/greybox
brew install --cask greybox-menubar
```

A starter cask definition is in `packaging/homebrew/greybox-menubar.rb` at
the repo root - fill in the URL/sha256 once you're publishing built
`.app.zip` releases on GitHub.

## Icon

`square.righthalf.filled` / `square.dashed` (SF Symbols) are used as
placeholders for the idle/scanning states, matching the grey-box mark
described in the build plan (a square split solid/outline). Swap in a
custom `AppIcon.icns` at `Resources/AppIcon.icns` before distributing -
the build script will pick it up automatically if present.
