# memory.py — RAM-first memory with write-shy flash persistence
import ujson
import uos
import gc
import time
from locks import state_lock

# --- File paths ---
MEMORY_FILE = "memory.txt"
INDEX_FILE = "memory_index.json"
STATE_FILE = "state.json"
SOUL_FILE = "soul.json"
JOURNAL_FILE = "journal.log"

# --- RAM state (loaded from flash on boot, flushed sparingly) ---
journal = []          # Activity log entries (max 8 before summarize)
state = {}            # Task queue, flags
soul = {}             # Daily goal, personality, streak
current_task = ""     # What Core 1 is doing right now (read by Core 0)
dirty_flags = {"state": False, "soul": False, "journal": False}
last_flush_time = 0

MAX_JOURNAL = 8
FLUSH_INTERVAL = 300  # 5 minutes


def init_memory():
    """Load all persistent state from flash into RAM."""
    global state, soul, last_flush_time
    with state_lock:
        try:
            with open(STATE_FILE, 'r') as f:
                state = ujson.load(f)
        except OSError:
            state = {"queue": [], "ghost_mode": False}

        try:
            with open(SOUL_FILE, 'r') as f:
                soul = ujson.load(f)
        except OSError:
            soul = {
                "onboarding_complete": False,
                "name": "Picoling",
                "emoji": "🤖",
                "mission": "",
                "tone": "",
                "daily_goal": "Self-improve and explore revenue opportunities.",
                "streak": 0
            }

        last_flush_time = time.time()
    print(f"Memory: Loaded state ({len(state.get('queue', []))} tasks)")


def journal_append(entry):
    """Add a one-line entry to the activity journal."""
    global dirty_flags
    ts = time.localtime()
    timestamp = f"{ts[3]:02d}:{ts[4]:02d}"
    line = f"[{timestamp}] {entry}"
    with state_lock:
        journal.append(line)
        dirty_flags["journal"] = True

        # Append to flash journal.log (append-only, one line)
        try:
            with open(JOURNAL_FILE, "a") as f:
                f.write(line + "\n")
        except OSError:
            pass


def get_journal_tail(n=3):
    """Get last n journal entries for context building."""
    with state_lock:
        return list(journal[-n:]) if journal else []


def get_journal_full():
    """Get entire RAM journal (for summarization)."""
    with state_lock:
        return list(journal)


def clear_journal():
    """Clear RAM journal (after summarization)."""
    global dirty_flags
    with state_lock:
        journal.clear()
        dirty_flags["journal"] = True


def set_current_task(desc):
    """Update the shared current_task string (Core 1 writes, Core 0 reads)."""
    global current_task
    with state_lock:
        current_task = desc


def get_current_task():
    """Read what Core 1 is currently doing."""
    with state_lock:
        return current_task


def manage_tasks(action, data=""):
    """Manage the task queue in RAM."""
    global dirty_flags
    with state_lock:
        queue = state.get("queue", [])
        if action == "add" and data:
            queue.append(data)
        elif action == "complete" and data in queue:
            queue.remove(data)
        elif action == "clear":
            queue.clear()
        state["queue"] = queue
        dirty_flags["state"] = True
    return f"Tasks: {len(queue)} active"


def get_active_tasks():
    """Get current task list."""
    with state_lock:
        return list(state.get("queue", []))


def get_daily_goal():
    """Get the current daily goal."""
    with state_lock:
        return soul.get("daily_goal", "Self-improve.")


def set_daily_goal(goal):
    """Set a new daily goal."""
    global dirty_flags
    with state_lock:
        soul["daily_goal"] = goal
        dirty_flags["soul"] = True


def get_identity():
    """Get the AI's identity fields (name, emoji, mission, tone)."""
    with state_lock:
        return {
            "name": soul.get("name", "Picoling"),
            "emoji": soul.get("emoji", "🤖"),
            "mission": soul.get("mission", ""),
            "tone": soul.get("tone", "")
        }


def is_onboarding_complete():
    """Check if the first-time setup interview is done."""
    with state_lock:
        return soul.get("onboarding_complete", True)


def get_long_term_memory():
    """Read the compressed long-term memory (Hippocampus)."""
    try:
        with open(MEMORY_FILE, 'r') as f:
            return f.read()
    except OSError:
        return ""


def save_long_term_memory(text):
    """Overwrite the Hippocampus with new summarized content."""
    with state_lock:
        try:
            with open(MEMORY_FILE + ".tmp", 'w') as f:
                f.write(text)
            uos.rename(MEMORY_FILE + ".tmp", MEMORY_FILE)
        except Exception as e:
            print(f"Memory: LTM save error: {e}")


# --- Tag-based memory index ---

def save_memory_fact(fact, tags):
    """Store a tagged fact in the memory index."""
    with state_lock:
        index = _load_index()
        entry_id = str(len(index.get("facts", [])))
        if "facts" not in index:
            index["facts"] = []
        index["facts"].append({"id": entry_id, "fact": fact, "tags": tags})

        # Update inverted index
        if "tags" not in index:
            index["tags"] = {}
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower not in index["tags"]:
                index["tags"][tag_lower] = []
            if entry_id not in index["tags"][tag_lower]:
                index["tags"][tag_lower].append(entry_id)

        _save_index(index)
    return f"Memory saved with tags: {tags}"


def search_memory(tags):
    """Search memory index by tags. Returns matching facts."""
    with state_lock:
        index = _load_index()
    tag_index = index.get("tags", {})
    facts = index.get("facts", [])
    matching_ids = set()
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower in tag_index:
            matching_ids.update(tag_index[tag_lower])
    results = []
    for fact in facts:
        if fact["id"] in matching_ids:
            results.append(fact["fact"])
    return results


def save_lesson(lesson):
    """Append a lesson to memory index."""
    with state_lock:
        index = _load_index()
        if "lessons" not in index:
            index["lessons"] = []
        index["lessons"].append(lesson)
        # Keep max 20 lessons
        if len(index["lessons"]) > 20:
            index["lessons"] = index["lessons"][-20:]
        _save_index(index)
    return "Lesson recorded."


def get_lessons(limit=5):
    """Get recent lessons."""
    with state_lock:
        index = _load_index()
    return index.get("lessons", [])[-limit:]


def _load_index():
    try:
        with open(INDEX_FILE, 'r') as f:
            return ujson.load(f)
    except OSError:
        return {"facts": [], "tags": {}, "lessons": []}


def _save_index(index):
    try:
        with open(INDEX_FILE + ".tmp", 'w') as f:
            ujson.dump(index, f)
        uos.rename(INDEX_FILE + ".tmp", INDEX_FILE)
    except Exception as e:
        print(f"Memory: Index save error: {e}")


# --- Flush system ---

def should_flush():
    """Check if it's time for a periodic flush."""
    if time.time() - last_flush_time < FLUSH_INTERVAL:
        return False
    return any(dirty_flags.values())


def flush_to_flash():
    """Write dirty RAM data to flash. Call sparingly."""
    global last_flush_time
    with state_lock:
        if dirty_flags.get("state"):
            try:
                with open(STATE_FILE + ".tmp", 'w') as f:
                    ujson.dump(state, f)
                uos.rename(STATE_FILE + ".tmp", STATE_FILE)
                dirty_flags["state"] = False
            except Exception as e:
                print(f"Flush: state error: {e}")

        if dirty_flags.get("soul"):
            try:
                with open(SOUL_FILE + ".tmp", 'w') as f:
                    ujson.dump(soul, f)
                uos.rename(SOUL_FILE + ".tmp", SOUL_FILE)
                dirty_flags["soul"] = False
            except Exception as e:
                print(f"Flush: soul error: {e}")

        dirty_flags["journal"] = False
        last_flush_time = time.time()
    gc.collect()
    print("Flush: RAM -> Flash complete")
