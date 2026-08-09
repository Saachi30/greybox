# Free Deployment Guide

Everything below costs $0. The only thing that ever costs money is a
custom domain name (optional) - hosting, CI, releases, and the tap are all
free on GitHub's public-repo tier.

## 1. Push the code

```bash
cd greybox
git init   # if not already a repo
git add .
git commit -m "Initial public release"
```

Create a new **public** repository on GitHub (private repos have Actions
minute limits; public repos don't), then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/greybox.git
git branch -M main
git push -u origin main
```

**Before pushing**, replace every placeholder:
```bash
grep -rln "Saachi30" . --include="*.py" --include="*.rb" --include="*.md" --include="*.html"
```
Fix each one to your actual GitHub username/org.

## 2. Landing page - GitHub Pages (free, zero config)

1. Repo → **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main`, folder: `/website` (or move `website/`'s contents to `/docs` at repo root if GitHub Pages' folder picker in your account only offers `/docs` - both work, `/website` support varies slightly by account, check what's offered)
4. Save. Live in a minute or two at `https://YOUR_USERNAME.github.io/greybox/`

**Alternative (marginally easier custom domains): Netlify or Vercel.**
Both have a free tier with no realistic limit for a static site like this.
Connect your GitHub repo, set the publish directory to `website/`, done -
you get a free `https://greybox.netlify.app`-style URL immediately, and
either lets you attach a custom domain later for free (you'd only pay for
the domain registration itself, not the hosting).

## 3. Tag a release

```bash
git tag v1.0.0
git push --tags
```

Then on GitHub: **Releases → Draft a new release**, pick the tag, write
release notes, publish. This is also where you'll later attach:
- The menu bar app once built (`Greybox.app.zip`)
- Any pre-built binaries if you add them later

All free, no size limits worth worrying about at this scale.

## 4. Homebrew tap (free)

Create a second public repo named exactly `homebrew-greybox` (the `homebrew-`
prefix is what makes `brew tap YOUR_USERNAME/greybox` work).

```
homebrew-greybox/
  Formula/
    greybox.rb          <- from packaging/homebrew/greybox.rb
  Casks/
    greybox-menubar.rb  <- from packaging/homebrew/greybox-menubar.rb
```

Update both files' `url`/`sha256` to point at your v1.0.0 release assets:
```bash
shasum -a 256 <downloaded-release-tarball>
```

Once pushed, anyone can run:
```bash
brew tap YOUR_USERNAME/greybox
brew install greybox
```

## 5. CI - already free, just needs pushing

`.github/workflows/ci.yml` runs automatically once pushed - **no setup
step required**, GitHub Actions is enabled by default on new repos. Public
repos get unlimited Actions minutes, so this costs nothing regardless of
how often you push. This is also your free Windows/macOS testing
environment - see `greybox_test_since_yesterday.md` Section 10.

## 6. Windows distribution specifically

Windows users install differently from Linux/Mac - no Homebrew, no `curl | bash`
convention. Two things to set up:

1. **Host `install.ps1` somewhere directly downloadable.** GitHub Pages
   serves raw files fine - if `install.ps1` lives at your repo root and
   Pages is serving from `website/`, either copy `install.ps1` into
   `website/` at deploy time, or just point users at the GitHub raw URL
   directly: `https://raw.githubusercontent.com/YOUR_USERNAME/greybox/main/install.ps1`.
   The landing page's Windows tab should use whichever you pick consistently.
2. **`winget` submission is optional, not required for launch.** You can
   ship with just the PowerShell one-liner
   (`irm <url> -OutFile install.ps1; .\install.ps1`) for v1 - submitting to
   the winget-pkgs repo is a real process (PR review, manifest validation)
   worth doing later once the installer's proven, not before.
3. **Test it for real before claiming Windows support** - this is the one
   platform that was never manually tested. The free CI workflow
   (Section 5) gives you Stage 1 (CLI-only) coverage automatically, but
   Stage 2 (WSL2 + Docker + Kali) still needs a human on a real Windows
   machine at least once - GitHub-hosted Windows runners don't support the
   nested virtualization Docker Desktop needs, so CI can't fully cover this
   part. If you don't have Windows hardware, ask someone who does before
   launch, or scope Windows support as "beta" in your launch messaging
   until it's been through that.

## 7. Things to deliberately skip for a free launch

- **Telemetry service** (`telemetry/`) - entirely optional, off by default.
  Skip it for launch; every free-tier VPS option (Fly.io, Render, Railway)
  has cold-start or usage caps that add complexity for zero real benefit
  at launch. Add it later only if you actually want install counts.
- **A custom domain** - not free (typically $10-15/year), but not required
  either. `YOUR_USERNAME.github.io/greybox` or `greybox.netlify.app` is a
  completely legitimate URL to launch and share with.
- **Code signing the macOS app** - Apple's notarization has its own
  process and isn't strictly free (Developer Program is $99/year). Ship
  the menu bar app unsigned for now with clear instructions ("right-click
  → Open" to bypass Gatekeeper on first launch) rather than paying for
  signing before you know if anyone's using it.

## 8. Order of operations for launch day

1. Run through `greybox_launch_testing_checklist.md` and
   `greybox_test_since_yesterday.md` completely, on the actual build
   you're about to ship - not an earlier one.
2. Push to GitHub, confirm the CI workflow actually runs and passes (or at
   least understand why anything fails before ignoring it).
3. Tag `v1.0.0`, publish the GitHub Release.
4. Turn on GitHub Pages (or deploy to Netlify).
5. Set up the Homebrew tap.
6. Do a soft launch first - share with a small group before wide
   promotion, given the genuinely newer/less-proven areas (Windows,
   menu bar app) - this catches real-world issues while stakes are low.
7. Only after that goes fine, post it more broadly.