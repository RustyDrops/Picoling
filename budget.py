# budget.py — Token accountant with budget zones and rollover
import ujson
import uos
import time
import gc
from locks import state_lock

STATS_FILE = "stats.json"
DAILY_BUDGET = 0.25
GROUNDING_DAILY_LIMIT = 100  # 3000/month free tier ÷ 30

# Pricing per token (USD) — derived from per-1M-token rates
PRICING = {
    "gemini-3.1-flash-lite-preview": {"in": 0.00000025, "out": 0.0000015, "think": 0.0000015},
    "gemini-3-flash-preview":        {"in": 0.0000005,  "out": 0.000003,  "think": 0.000003},
    "gemini-2.5-flash-lite":         {"in": 0.0000003,  "out": 0.0000025, "think": 0.00000125},
}

# Flex tier is 50% of standard pricing
FLEX_DISCOUNT = 0.5


def _load_stats():
    try:
        with open(STATS_FILE, "r") as f:
            return ujson.load(f)
    except OSError:
        return _default_stats()


def _default_stats():
    return {
        "date": _today_str(),
        "total_spent": 0.0,
        "carryover": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "tokens_think": 0,
        "calls_made": 0,
        "grounding_calls": 0,
        "by_model": {},
    }


def _today_str():
    t = time.localtime()
    return f"{t[0]}-{t[1]:02d}-{t[2]:02d}"


def _save_stats(stats):
    with open(STATS_FILE + ".tmp", "w") as f:
        ujson.dump(stats, f)
    uos.rename(STATS_FILE + ".tmp", STATS_FILE)


def _ensure_today(stats):
    """Roll over budget if it's a new day."""
    today = _today_str()
    if stats.get("date") != today:
        yesterday_remaining = DAILY_BUDGET + stats.get("carryover", 0) - stats.get("total_spent", 0)
        carryover = max(0, yesterday_remaining)
        new_stats = _default_stats()
        new_stats["carryover"] = round(carryover, 8)
        new_stats["date"] = today
        return new_stats
    return stats


def calculate_cost(model, tokens_in, tokens_out, tokens_think=0, tier="standard"):
    """Calculate the USD cost of an API call."""
    p = PRICING.get(model, PRICING["gemini-3.1-flash-lite-preview"])
    cost = (tokens_in * p["in"]) + (tokens_out * p["out"]) + (tokens_think * p["think"])
    if tier == "flex":
        cost *= FLEX_DISCOUNT
    return round(cost, 10)


def log_spend(model, tokens_in, tokens_out, tokens_think=0, tier="standard", is_grounding=False):
    """Record a completed API call's costs."""
    cost = calculate_cost(model, tokens_in, tokens_out, tokens_think, tier)
    with state_lock:
        stats = _load_stats()
        stats = _ensure_today(stats)
        stats["total_spent"] = round(stats.get("total_spent", 0) + cost, 10)
        stats["tokens_in"] += tokens_in
        stats["tokens_out"] += tokens_out
        stats["tokens_think"] += tokens_think
        stats["calls_made"] += 1
        if is_grounding:
            stats["grounding_calls"] += 1

        # Per-model tracking
        if model not in stats.get("by_model", {}):
            stats["by_model"][model] = {"cost": 0, "calls": 0}
        stats["by_model"][model]["cost"] = round(stats["by_model"][model].get("cost", 0) + cost, 10)
        stats["by_model"][model]["calls"] += 1

        _save_stats(stats)
    return cost


def get_remaining():
    """Get remaining budget for today."""
    with state_lock:
        stats = _load_stats()
        stats = _ensure_today(stats)
    total_avail = DAILY_BUDGET + stats.get("carryover", 0)
    return round(total_avail - stats.get("total_spent", 0), 8)


def get_budget_zone():
    """Classify budget health: healthy, cautious, emergency, critical."""
    remaining = get_remaining()
    total_avail = DAILY_BUDGET + _load_stats().get("carryover", 0)
    if total_avail <= 0:
        return "critical"
    pct = remaining / total_avail
    if pct > 0.60:
        return "healthy"
    elif pct > 0.30:
        return "cautious"
    elif pct > 0.10:
        return "emergency"
    return "critical"


def can_use_grounding():
    """Check if daily grounding limit has been reached."""
    with state_lock:
        stats = _load_stats()
        stats = _ensure_today(stats)
    return stats.get("grounding_calls", 0) < GROUNDING_DAILY_LIMIT


def get_budget_prompt_string():
    """Budget status string injected into system prompts."""
    with state_lock:
        stats = _load_stats()
        stats = _ensure_today(stats)
    remaining = round(DAILY_BUDGET + stats.get("carryover", 0) - stats.get("total_spent", 0), 6)
    total_avail = round(DAILY_BUDGET + stats.get("carryover", 0), 4)
    calls = stats.get("calls_made", 0)
    zone = get_budget_zone()

    if zone == "critical":
        return f"BUDGET CRITICAL: ${remaining:.4f} of ${total_avail} left. Chat only. No background work."
    elif zone == "emergency":
        return f"Budget LOW: ${remaining:.4f} of ${total_avail} left. Flex only, minimal thinking."
    elif zone == "cautious":
        return f"Budget moderate: ${remaining:.4f} of ${total_avail} left ({calls} calls). Be efficient."
    return f"Budget healthy: ${remaining:.4f} of ${total_avail} left ({calls} calls). Operate normally."


def get_detailed_status():
    """Full budget breakdown for ~budget command."""
    with state_lock:
        stats = _load_stats()
        stats = _ensure_today(stats)
    remaining = round(DAILY_BUDGET + stats.get("carryover", 0) - stats.get("total_spent", 0), 6)
    total_avail = round(DAILY_BUDGET + stats.get("carryover", 0), 4)
    lines = [
        f"Date: {stats.get('date')}",
        f"Budget: ${remaining:.7f} / ${total_avail:.7f}",
        f"Spent: ${stats.get('total_spent', 0):.7f}",
        f"Carryover: ${stats.get('carryover', 0):.7f}",
        f"Calls: {stats.get('calls_made', 0)}",
        f"Grounding: {stats.get('grounding_calls', 0)}/{GROUNDING_DAILY_LIMIT}",
        f"Zone: {get_budget_zone().upper()}",
    ]
    by_model = stats.get("by_model", {})
    for m, s in by_model.items():
        short = m.split("-")[-1] if "-" in m else m
        lines.append(f"  {short}: ${s.get('cost', 0):.7f} ({s.get('calls', 0)} calls)")
    gc.collect()
    return "\n".join(lines)
