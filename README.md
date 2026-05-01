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

**Public repo structure:**
```
_posts/               # Blog posts (Jekyll/GitHub Pages)
skills/               # Curated skills Picoling wants to share
projects/             # Open-source projects Picoling builds
  └── <project-name>/
      └── ...files
```

## Quick Start

1. Copy `secrets_template.py` → `secrets.py` and fill in your API keys
2. Set up a private GitHub repo for backups
3. Set up a public GitHub repo with GitHub Pages enabled for the portfolio/blog
4. Flash all files to your Pico 2W
5. Picoling boots automatically and sends a Telegram notification

## Telegram Commands

| Command | Description |
|---|---|
| `~ping` | Health check: RAM, budget, temperature |
| `~budget` | Detailed spending breakdown |
| `~auto on/off` | Toggle autonomous mode |
| `~save` | Force RAM → Flash flush |
| `~cnew` | Clear activity journal |
| `~status` | Current tasks, goal, background activity |
| `~ghost on/off` | Toggle Ghost Mode (skill deletion) |
| `~reboot` | Soft reset |
| `~help` | List all commands |

## Budget System

- **$0.25/day** with unused budget rolling over to the next day
- **Budget zones** control behavior:
  - **Healthy** (>60%): Normal operation
  - **Cautious** (30-60%): Prefer Flex, reduce thinking
  - **Emergency** (10-30%): Flex only, minimal thinking, autonomous paused
  - **Critical** (<10%): Chat only, no background work

## Skills

Ships with 9 starter skills. Picoling can forge new ones autonomously:

| Skill | Purpose |
|---|---|
| `file_ops.py` | Read/write files with syntax checking |
| `human_ops.py` | Non-blocking question tickets |
| `web_fetch.py` | HTTP GET with size limits |
| `blog_post.py` | Publish to GitHub Pages |
| `sys_info.py` | System health report |
| `seo_research.py` | Topic research template |
| `site_builder.py` | Static site generator |
| `analytics.py` | GitHub repo stats |
| `template_engine.py` | HTML template rendering |

## File Structure

```
main.py              # Boot sequence
agent_core.py        # Orchestrator brain
api_client.py        # Gemini REST client
memory.py            # RAM-first memory system
budget.py            # Token accountant
action_router.py     # Tool executor
poller.py            # Telegram polling (Core 0)
horizon.py           # Background worker (Core 1)
prompts.py           # Prompt templates (freeze to .mpy)
schemas.py           # Tool schemas (freeze to .mpy)
locks.py             # Thread locks (freeze to .mpy)
wifi_mgmt.py         # WiFi + DNS cache
sys_mgmt.py          # CPU management
telegram_bot.py      # Telegram sender
github_sync.py       # Private backup + public portfolio
secrets.py           # API keys (never committed)
skills/              # AI-forged MicroPython tools
```

## Hardware

- Raspberry Pi Pico 2W (RP2350, dual-core ARM, 520KB RAM, 2MB Flash)
- CPU locked to 150MHz for WiFi stability


## License

MIT
