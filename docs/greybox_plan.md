# Greybox Build Prompt: Local-First AI Pentesting Toolkit

(See the full document as previously drafted with you - this file is kept
here as the historical build prompt / reasoning record. The implementation
in this repo follows it directly: security-core/ reused, backend
simplified to Kali + FastAPI with no database for scan data, local Ollama
in place of Gemini, core/ as the shared tool registry and session schema,
cli/ as the new natural-language assistant, report/ for PDF generation,
and telemetry/ added as a separate, tiny, opt-in install counter per your
request for install/usage analytics without user data storage.

Sections worth re-reading if you extend this:
- Section 5 (CLI design: tool registry, never-auto-execute, scope state)
- Section 8 (macOS menu bar companion - not yet built, backend API is ready for it)
- Section 9 (visual design direction: dark theme, JetBrains Mono / IBM Plex
  Mono, severity-only accent color - apply this if/when a web dashboard or
  the menu bar popover gets built)
