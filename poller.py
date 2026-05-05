# poller.py — Telegram long-polling on Core 0 (always responsive)
import urequests
import ujson
import gc
import uasyncio as asyncio
from secrets import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from locks import net_lock
import memory
import budget
import agent_core
import telegram_bot

_POLL_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
_last_update_id = 0
_backoff = 2


# Command dispatch table
def _handle_ping():
    ram = gc.mem_free()
    zone = budget.get_budget_zone()
    remaining = budget.get_remaining()
    task = memory.get_current_task() or "Idle"
    return f"ONLINE | RAM: {ram // 1024}KB | ${remaining:.4f} | {zone} | {task}"


def _handle_budget():
    return budget.get_detailed_status()


def _handle_auto(args):
    if args == "on":
        memory.state["autonomous"] = True
        memory.dirty_flags["state"] = True
        return "Autonomous mode: ON"
    elif args == "off":
        memory.state["autonomous"] = False
        memory.dirty_flags["state"] = True
        return "Autonomous mode: OFF"
    return "Usage: ~auto on|off"


def _handle_save():
    memory.flush_to_flash()
    return "RAM flushed to flash."


def _handle_cnew():
    memory.clear_journal()
    return "Journal cleared."


def _handle_status():
    tasks = memory.get_active_tasks()
    goal = memory.get_daily_goal()
    task = memory.get_current_task() or "Idle"
    t_str = "\n".join(f"- {t}" for t in tasks[:5]) if tasks else "No tasks"
    return f"Goal: {goal[:100]}\nBackground: {task}\nTasks:\n{t_str}"


def _handle_goal():
    return f"Current Goal: {memory.get_daily_goal()}"


def _handle_tasks():
    tasks = memory.get_active_tasks()
    if not tasks:
        return "Task queue is empty."
    return "Tasks:\n" + "\n".join(f"- {t}" for t in tasks)


def _handle_ghost(args):
    if args == "on":
        memory.state["ghost_mode"] = True
        memory.dirty_flags["state"] = True
        return "Ghost Mode: ON (skill deletion enabled)"
    elif args == "off":
        memory.state["ghost_mode"] = False
        memory.dirty_flags["state"] = True
        return "Ghost Mode: OFF"
    return "Usage: ~ghost on|off"


def _handle_reboot():
    telegram_bot.send_telegram_msg("Rebooting...")
    memory.flush_to_flash()
    import machine
    machine.reset()


def _handle_help():
    return (
        "Commands:\n"
        ".ping - Health check\n"
        ".budget - Spend breakdown\n"
        ".auto on|off - Autonomous mode\n"
        ".save - Flush RAM to flash\n"
        ".cnew - Clear journal\n"
        ".status - Current state\n"
        ".ghost on|off - Toggle Ghost Mode\n"
        ".reboot - Soft reset\n"
        ".help - This list"
    )


COMMANDS = {
    ".ping": lambda _: _handle_ping(),
    ".budget": lambda _: _handle_budget(),
    ".save": lambda _: _handle_save(),
    ".cnew": lambda _: _handle_cnew(),
    ".status": lambda _: _handle_status(),
    ".help": lambda _: _handle_help(),
}


async def poll_loop(wdt):
    """Main Telegram polling loop. Runs on Core 0."""
    global _last_update_id, _backoff

    while True:
        wdt.feed()
        gc.collect()

        res = None
        try:
            url = f"{_POLL_URL}?offset={_last_update_id + 1}&timeout=5"
            with net_lock:
                res = urequests.get(url, timeout=10)

            if res.status_code != 200:
                await asyncio.sleep(_backoff)
                _backoff = min(_backoff * 2, 30)
                continue

            data = res.json()
            _backoff = 2  # Reset backoff on success

            updates = data.get("result", [])
            for update in updates:
                _last_update_id = update["update_id"]
                msg = update.get("message", {})

                # Security: only process from authorized chat
                chat_id = str(msg.get("chat", {}).get("id", ""))
                if chat_id != TELEGRAM_CHAT_ID:
                    continue

                text = msg.get("text", "").strip()
                if not text:
                    continue

                # Handle human ticket responses (#Q prefix)
                if text.startswith("#Q"):
                    _handle_ticket_response(text)
                    continue

                # --- NEW: NL Short-Circuit Router ---
                # Intercept common natural language intents to save API costs
                text_lower = text.lower()
                
                if text_lower.startswith("add task:"):
                    task_desc = text[9:].strip()
                    response = memory.manage_tasks("add", task_desc)
                    telegram_bot.send_telegram_msg(f"✅ Task Added (Local): {task_desc}")
                    continue
                
                if text_lower.startswith("set goal:"):
                    goal_desc = text[9:].strip()
                    memory.set_daily_goal(goal_desc)
                    telegram_bot.send_telegram_msg(f"🎯 Goal Set (Local): {goal_desc}")
                    continue

                if text_lower in ("what is my goal?", "status report", "pico status"):
                    telegram_bot.send_telegram_msg(_handle_status())
                    continue

                # Handle . commands
                if text.startswith("."):
                    parts = text.split(" ", 1)
                    cmd = parts[0].lower()
                    args = parts[1] if len(parts) > 1 else ""

                    if cmd == ".auto":
                        response = _handle_auto(args)
                    elif cmd == ".ghost":
                        response = _handle_ghost(args)
                    elif cmd == ".reboot":
                        _handle_reboot()
                        return  # Won't reach
                    elif cmd in COMMANDS:
                        response = COMMANDS[cmd](args)
                    else:
                        response = f"Unknown command: {cmd}. Try .help"

                    telegram_bot.send_telegram_msg(response, max_len=1000)
                    continue

                # Regular chat message — process via agent_core
                # Safety timeout: 120 seconds max
                try:
                    await asyncio.wait_for(
                        agent_core.process_user_message(text),
                        timeout=120
                    )
                except asyncio.TimeoutError:
                    telegram_bot.send_telegram_msg("Processing timed out (120s). Try a simpler request.")

        except Exception as e:
            print(f"[POLL] Error: {e}")
            await asyncio.sleep(_backoff)
            _backoff = min(_backoff * 2, 30)
        finally:
            if res:
                res.close()

        # Check if periodic flush is needed
        if memory.should_flush():
            memory.flush_to_flash()

        await asyncio.sleep(1)


def _handle_ticket_response(text):
    """Handle human response to a #Q ticket."""
    parts = text.split(" ", 1)
    ticket_id = parts[0]
    answer = parts[1] if len(parts) > 1 else ""
    filename = ticket_id.replace("#Q", "")
    filepath = f"data/human_queue/{filename}.json"

    try:
        import uos
        with open(filepath, 'r') as f:
            ticket = ujson.load(f)
        ticket["answer"] = answer
        with open(filepath, 'w') as f:
            ujson.dump(ticket, f)
        telegram_bot.send_telegram_msg(f"{ticket_id}: Answer recorded.")
        memory.journal_append(f"Human answered {ticket_id}")
    except OSError:
        telegram_bot.send_telegram_msg(f"{ticket_id}: Ticket not found.")
