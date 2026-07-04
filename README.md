# PACER

A token-pacing and budget dashboard for Claude Code — the fuel gauge I built because I kept hitting rate limits mid-project and couldn't see my own consumption.

Single-file frontend (vanilla JS, no build step) served alongside a Python backend on one process. No framework, no bundler.

## What it does

- **Live** — real-time session burn tracking against your 5-hour and weekly limits
- **Optimize** — pattern detection + concrete recommendations to stretch a budget
- **Yield / Simulator / Compare** — model usage forecasting and profile comparison
- **Codex** — a routing matrix that decides which task goes to Claude vs. Codex (7 task types × primary/pair/skip labels)
- **Broker** — cross-service budget allocation with lock/rebalance
- CSV export throughout; bilingual EN/ES interface

## Run it

```bash
python3 server.py
# open http://localhost:8765
```

Add `ANTHROPIC_API_KEY=sk-ant-...` to a local `.env` for live usage features (git-ignored; never commit it).

## Stack

Vanilla JS · Python (stdlib HTTP) · Anthropic API · PWA (installable, service worker) · single-process architecture on `:8765`.

Built with Claude Code.
