# horizon.py — Core 1 Background Worker (Flex tier)
# Runs on the second core via _thread. Cannot use uasyncio.
import time
import gc
import machine
import _thread
import agent_core
import memory
import budget
from locks import state_lock

# Thread configuration
STACK_SIZE = 4096  # Prevents stack overflow during JSON parsing

# Thermal protection
THERMAL_PAUSE = 50  # Pause at 50°C
THERMAL_RESUME = 40  # Resume at 40°C

# Schedule (hours in UTC, adjust for your timezone)
SCHEDULE = {
    0: "horizon",     # Midnight: daily reflection
    4: "blog",        # 4 AM: generate and publish blog post
    5: "backup",      # 5 AM: GitHub backup
    6: "morning",     # 6 AM: morning briefing
}

# Dynamic autonomous cycle timing (seconds)
AUTO_INTERVAL_NORMAL = 900      # 15 minutes
AUTO_INTERVAL_SLOW = 2700       # 45 minutes
AUTO_INTERVAL_CAUTIOUS = 3600   # 60 minutes
AUTO_CHECK_INTERVAL = 30        # Check queue every 30s


def _get_cpu_temp():
    """Read RP2350 internal temperature sensor."""
    try:
        sensor = machine.ADC(4)
        reading = sensor.read_u16()
        voltage = reading * 3.3 / 65535
        temp_c = 27 - (voltage - 0.706) / 0.001721
        return temp_c
    except:
        return 25.0  # Assume safe if can't read


def _is_overheating():
    """Check if CPU is too hot."""
    return _get_cpu_temp() >= THERMAL_PAUSE


def _wait_for_cooldown():
    """Block until temperature drops below resume threshold."""
    while _get_cpu_temp() > THERMAL_RESUME:
        print(f"[THERMAL] Cooling: {_get_cpu_temp():.1f}°C")
        time.sleep(10)


def _run_scheduled(hour):
    """Run scheduled protocol if it matches the current hour."""
    if hour in SCHEDULE:
        protocol = SCHEDULE[hour]
        if protocol == "horizon":
            agent_core.process_flex_task("horizon", "")
        elif protocol == "blog":
            agent_core.process_flex_task("blog", "")
        elif protocol == "backup":
            try:
                from github_sync import backup_to_private
                backup_to_private()
                memory.journal_append("Backup: Private repo sync complete")
            except Exception as e:
                memory.journal_append(f"Backup failed: {e}")
        elif protocol == "morning":
            agent_core.process_flex_task("morning", "")


def background_worker():
    """Main loop for Core 1. Processes Flex queue and scheduled tasks.
    This runs in a separate thread — NO uasyncio available."""
    print("[HORIZON] Core 1 worker started")
    last_auto_time = 0
    last_schedule_hour = -1
    last_auto_result = "idle"

    while True:
        try:
            gc.collect()

            if not memory.is_onboarding_complete():
                time.sleep(10)
                continue

            # --- Thermal check ---
            if _is_overheating():
                memory.set_current_task("THERMAL: Cooling down")
                _wait_for_cooldown()
                memory.set_current_task("")

            # --- Check Flex queue (highest priority) ---
            task = None
            with state_lock:
                if agent_core.flex_queue:
                    task = agent_core.flex_queue.pop(0)

            if task:
                task_type, task_data = task
                print(f"[HORIZON] Processing: {task_type}")
                agent_core.process_flex_task(task_type, task_data)
                last_auto_result = "success"
                time.sleep(2)
                continue

            # --- Scheduled protocols ---
            current_hour = time.localtime()[3]
            if current_hour != last_schedule_hour:
                last_schedule_hour = current_hour
                if current_hour in SCHEDULE:
                    print(f"[HORIZON] Schedule: {SCHEDULE[current_hour]}")
                    _run_scheduled(current_hour)
                    time.sleep(5)
                    continue

            # --- Autonomous mode ---
            is_auto = memory.state.get("autonomous", False)
            zone = budget.get_budget_zone()

            if is_auto and zone not in ("emergency", "critical"):
                # Dynamic interval based on last result and budget
                if zone == "cautious":
                    interval = AUTO_INTERVAL_CAUTIOUS
                elif last_auto_result == "error":
                    interval = AUTO_INTERVAL_SLOW
                else:
                    interval = AUTO_INTERVAL_NORMAL

                now = time.time()
                if now - last_auto_time >= interval:
                    last_auto_time = now
                    print("[HORIZON] Autonomous cycle")
                    try:
                        agent_core.process_flex_task("autonomous", "")
                        last_auto_result = "success"
                    except Exception as e:
                        print(f"[HORIZON] Auto error: {e}")
                        last_auto_result = "error"
                        memory.journal_append(f"Auto cycle error: {e}")
                    time.sleep(5)
                    continue

            # --- Idle: sleep and check again ---
            time.sleep(AUTO_CHECK_INTERVAL)

        except Exception as e:
            print(f"[HORIZON] Worker error: {e}")
            memory.journal_append(f"Horizon error: {e}")
            time.sleep(30)


def start_background_worker():
    """Launch the background worker on Core 1."""
    _thread.stack_size(STACK_SIZE)
    _thread.start_new_thread(background_worker, ())
    print("[HORIZON] Core 1 thread launched")
