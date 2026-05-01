# skills/human_ops.py — Non-blocking human question ticket system
import ujson
import utime
import uos
import telegram_bot


def tool_ask_human(question):
    """Generate a ticket, save to queue, send to Telegram. AI does NOT block."""
    timestamp = utime.time()
    ticket_id = f"#Q{timestamp % 10000}"
    filename = ticket_id.replace("#Q", "")
    filepath = f"data/human_queue/{filename}.json"

    try:
        uos.mkdir("data")
    except OSError:
        pass
    try:
        uos.mkdir("data/human_queue")
    except OSError:
        pass

    payload = {"id": ticket_id, "question": question, "timestamp": timestamp}
    with open(filepath, 'w') as f:
        ujson.dump(payload, f)

    telegram_bot.send_telegram_msg(f"[Action Required: {ticket_id}] {question}")
    return f"Question queued as {ticket_id}. Move on to other tasks."


def tool_check_answers():
    """Check for answered human tickets."""
    try:
        files = uos.listdir("data/human_queue")
    except OSError:
        return "No tickets."

    results = []
    for fname in files:
        if fname.endswith(".json"):
            try:
                with open(f"data/human_queue/{fname}", 'r') as f:
                    ticket = ujson.load(f)
                if "answer" in ticket:
                    results.append(f"{ticket['id']}: {ticket['answer']}")
            except:
                pass
    return "\n".join(results) if results else "No answers yet."
