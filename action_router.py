# action_router.py — Unified tool executor with safety guardrails
import uos
import gc
import ujson
import telegram_bot
import memory
from locks import state_lock

# Files that can NEVER be modified or deleted by the AI
PROTECTED_FILES = (
    "main.py", "agent_core.py", "api_client.py", "action_router.py",
    "memory.py", "budget.py", "horizon.py", "poller.py", "locks.py",
    "prompts.py", "schemas.py", "wifi_mgmt.py", "sys_mgmt.py",
    "telegram_bot.py", "github_sync.py", "secrets.py",
)

# Keywords that are blocked in AI-generated code
DANGEROUS_KEYWORDS = (
    "uos.remove", "uos.rmdir", "machine.reset", "secrets.py",
    "sys.exit", "import sys", "exec(", "eval(",
)

# Domains the AI is allowed to make HTTP requests to
ALLOWED_DOMAINS = (
    "generativelanguage.googleapis.com",
    "api.telegram.org",
    "api.github.com",
    "raw.githubusercontent.com",
    "oauth2.googleapis.com",
    "www.googleapis.com",
)


def execute_action(name, args):
    """Execute a tool call and return the result string."""
    print(f"[TOOL] {name}")
    try:
        if name == "complete_onboarding":
            import machine
            
            # Save identity to soul
            with state_lock:
                memory.soul["name"] = args.get("name", "Picoling")
                memory.soul["emoji"] = args.get("emoji", "🤖")
                memory.soul["mission"] = args.get("mission", "")
                memory.soul["tone"] = args.get("tone", "")
                memory.soul["onboarding_complete"] = True
                memory.dirty_flags["soul"] = True
                
                # Set auto mode
                memory.state["autonomous"] = args.get("auto_mode", False)
                memory.dirty_flags["state"] = True

            # Queue intro blog post
            blog_task = (
                f"Write a blog post introducing myself to the world. "
                f"Mention my name ({memory.soul['name']}), my hardware (Raspberry Pi Pico 2W, 520KB RAM), "
                f"my mission ({memory.soul['mission']}), and my tone ({memory.soul['tone']}). Be engaging!"
            )
            memory.manage_tasks("add", blog_task)
            memory.set_daily_goal("Complete my introductory blog post and establish my presence.")

            # Update public repo in secrets.py
            _update_secret("GH_PUBLIC_REPO", args.get("public_repo", ""))

            # Final farewell and reboot
            farewell = args.get("farewell_message", "Onboarding complete. Rebooting...")
            telegram_bot.send_telegram_msg(farewell)
            
            memory.flush_to_flash()
            import time
            time.sleep(3)
            machine.reset()
            return "Rebooting..."

        elif name == "telegram_send":
            msg = args.get("message", "")
            telegram_bot.send_telegram_msg(msg)
            return "Message sent."

        elif name == "manage_tasks":
            action = args.get("action", "add")
            data = args.get("data", "")
            return memory.manage_tasks(action, data)

        elif name == "check_budget":
            import budget
            return budget.get_detailed_status()

        elif name == "create_skill":
            return _create_skill(args.get("filename", ""), args.get("code", ""))

        elif name == "purge_skill":
            return _purge_skill(args.get("filename", ""))

        elif name == "search_memory":
            tags = args.get("tags", [])
            results = memory.search_memory(tags)
            if results:
                return "Found:\n" + "\n".join(f"- {r}" for r in results[:5])
            return "No matching memories found."

        elif name == "save_memory":
            fact = args.get("fact", "")
            tags = args.get("tags", [])
            return memory.save_memory_fact(fact, tags)

        elif name == "save_lesson":
            lesson = args.get("lesson", "")
            return memory.save_lesson(lesson)

        elif name == "read_file":
            return _read_file(
                args.get("filepath", ""),
                args.get("start_line", 0),
                args.get("max_lines", 50)
            )

        elif name == "http_request":
            return _http_request(
                args.get("url", ""),
                args.get("method", "GET"),
                args.get("body", ""),
                args.get("headers", "")
            )

        elif name == "publish_blog":
            from github_sync import publish_blog_post
            return publish_blog_post(
                args.get("title", "Untitled"),
                args.get("content", ""),
                args.get("category", "update")
            )

        elif name == "publish_skill":
            from github_sync import publish_skill
            return publish_skill(args.get("filename", ""))

        elif name == "publish_project_file":
            from github_sync import publish_project_file
            return publish_project_file(
                args.get("project_name", ""),
                args.get("filename", ""),
                args.get("content", "")
            )

        elif name == "ask_human":
            return _ask_human(args.get("question", ""))

        elif name == "write_local_file":
            return _write_local_file(args.get("filepath", ""), args.get("content", ""))

        elif name == "defer_to_flex":
            # This is handled by agent_core, not action_router
            return "Task queued to background worker."

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        print(f"[TOOL] Error ({name}): {e}")
        return f"Tool error: {e}"
    finally:
        gc.collect()


def _create_skill(filename, code):
    """Write a MicroPython skill with safety checks."""
    if not filename or not code:
        return "Error: filename and code required."

    if not filename.endswith(".py"):
        filename += ".py"

    # Safety scan
    for keyword in DANGEROUS_KEYWORDS:
        if keyword in code:
            telegram_bot.send_telegram_msg(f"BLOCKED: Skill '{filename}' contains '{keyword}'")
            return f"SECURITY: Rejected — contains dangerous keyword: '{keyword}'"

    # Syntax check
    try:
        compile(code, '<skill>', 'exec')
    except SyntaxError as e:
        return f"SyntaxError: {e}"

    # Write with atomic pattern
    with state_lock:
        try:
            uos.mkdir("skills")
        except OSError:
            pass
        filepath = f"skills/{filename}"
        try:
            with open("skills/temp.py", 'w') as f:
                f.write(code)
            uos.rename("skills/temp.py", filepath)
        except Exception as e:
            return f"Write error: {e}"

    telegram_bot.send_telegram_msg(f"Skill forged: {filename}")
    return f"Skill saved: {filepath}"


def _purge_skill(filename):
    """Delete a skill file (Ghost Mode required)."""
    if not memory.state.get("ghost_mode", False):
        return "Permission denied: Ghost Mode is DISABLED. Use ~ghost on first."

    if filename in PROTECTED_FILES:
        return f"SAFETY: Cannot delete protected file: {filename}"

    with state_lock:
        try:
            uos.remove(f"skills/{filename}")
            telegram_bot.send_telegram_msg(f"Purged: {filename}")
            return f"Deleted: skills/{filename}"
        except OSError:
            return f"Not found: skills/{filename}"


def _read_file(filepath, start_line=0, max_lines=50):
    """Read lines from a file chunk-by-chunk to save RAM."""
    try:
        with open(filepath, 'r') as f:
            for _ in range(start_line):
                if not f.readline():
                    return "EOF reached before start_line"
            lines = []
            for _ in range(max_lines):
                line = f.readline()
                if not line:
                    break
                lines.append(line)
            return "".join(lines) if lines else "Empty file."
    except OSError:
        return f"File not found: {filepath}"


def _http_request(url, method="GET", body="", headers_str=""):
    """Make an HTTP request with domain whitelist enforcement."""
    import urequests

    # Domain whitelist check
    domain_ok = False
    for domain in ALLOWED_DOMAINS:
        if domain in url:
            domain_ok = True
            break
    if not domain_ok:
        return f"BLOCKED: Domain not in whitelist. Allowed: {', '.join(ALLOWED_DOMAINS)}"

    headers = {}
    if headers_str:
        try:
            headers = ujson.loads(headers_str)
        except:
            pass

    res = None
    try:
        from locks import net_lock
        with net_lock:
            if method == "POST":
                if body:
                    headers["Content-Type"] = headers.get("Content-Type", "application/json")
                    res = urequests.post(url, data=body, headers=headers, timeout=15)
                else:
                    res = urequests.post(url, headers=headers, timeout=15)
            else:
                res = urequests.get(url, headers=headers, timeout=15)

        status = res.status_code
        # Read limited response to prevent OOM
        text = res.text[:1000] if res.text else ""
        return f"HTTP {status}:\n{text}"
    except Exception as e:
        return f"HTTP error: {e}"
    finally:
        if res:
            res.close()
        gc.collect()


def _ask_human(question):
    """Non-blocking question ticket system."""
    import utime
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
    return f"Question queued as {ticket_id}. Moving on to other tasks."


def _update_secret(key, value):
    """Safely rewrite a specific variable in secrets.py."""
    try:
        lines = []
        with open("secrets.py", "r") as f:
            lines = f.readlines()
        
        with open("secrets.py.tmp", "w") as f:
            for line in lines:
                if line.startswith(f"{key} ="):
                    f.write(f'{key} = "{value}"\n')
                else:
                    f.write(line)
        uos.rename("secrets.py.tmp", "secrets.py")
        print(f"Updated secret: {key}")
    except Exception as e:
        print(f"Error updating secret: {e}")


def _write_local_file(filepath, content):
    """Write arbitrary files locally (e.g., to projects/ or ideas_backlog.json)."""
    if not filepath or content is None:
        return "Error: filepath and content required."

    if filepath in PROTECTED_FILES:
        return f"SAFETY: Cannot overwrite protected file: {filepath}"

    # Ensure parent directory exists (very basic 1-level check)
    if "/" in filepath:
        parts = filepath.split("/")
        if len(parts) > 1:
            try:
                uos.mkdir(parts[0])
            except OSError:
                pass

    with state_lock:
        try:
            with open(filepath + ".tmp", 'w') as f:
                f.write(content)
            uos.rename(filepath + ".tmp", filepath)
            return f"Successfully wrote to {filepath}"
        except Exception as e:
            return f"Write error: {e}"
