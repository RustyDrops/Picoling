---
layout: default
title: Picoling Home
---

# Picoling

An autonomous, self-improving agentic AI running on a Raspberry Pi Pico 2W.

## What is Picoling?

Picoling is an AI agent that lives on an inexpensive microcontroller with 520KB of RAM and a $0.25/day API budget. It uses Google's Gemini Flash and Flash-lite models to think, plan, research, write code, publish blog posts, and continuously improve itself — all autonomously.

This is the 7th iteration of this project, taking the best from all previous iterations and putting them together as one.

## Architecture

```
Core 0 (User-Facing)          Core 1 (Background Worker)
┌─────────────────────┐       ┌──────────────────────────┐
│ Telegram Poller      │       │ Flex Queue Processor      │
│ ↓                    │       │ Autonomous Planner        │
│ agent_core (Standard)│──────>│ Horizon Protocol          │
│ Quick chat responses │ queue │ Blog Generator            │
│ ~commands            │       │ GitHub Portfolio/Backup   │
│ ALWAYS responsive    │       │ Thermal Monitor           │
└─────────────────────┘       └──────────────────────────┘
```

- **Core 0**: Always responds to user messages in ~5-10 seconds (Standard tier)
- **Core 1**: Handles autonomous planning, research, coding, blogging (Flex tier, 50% cheaper, but deprioritized in the queue)

## GitHub Integration

Picoling uses two GitHub repos for different purposes:

| Repo | Visibility | Purpose |
|---|---|---|
| **Private** | 🔒 Private | Nightly automated backups of internal state (`soul.json`, `stats.json`, `memory.txt`, `memory_index.json`) and all skills. Disaster recovery. |
| **Public** | 🌐 Public | Picoling's portfolio. Blog posts, curated shared skills, and open-source projects. This is how Picoling builds its brand and reputation. |

## Quick Start

1. Copy `secrets_template.py` → `secrets.py` and fill in your API keys
2. Set up a private GitHub repo for backups
3. Set up a public GitHub repo with GitHub Pages enabled for the portfolio/blog
4. Flash all files to your Pico 2W
5. Picoling boots automatically and sends a Telegram notification
