# agent_core.py — The Orchestrator Brain
# Two modes: User Chat (Core 0, Standard) and Background Execution (Core 1, Flex)
import gc
import api_client
import memory
import budget
import telegram_bot
from action_router import execute_action
from prompts import SYSTEM_BASE, ONBOARDING_PROMPT, ROLES

# Shared flex queue — Core 0 pushes, Core 1 pops
flex_queue = []

def queue_flex_task(task_type, task_data):
    """Add a task to the shared flex queue."""
    from locks import state_lock
    with state_lock:
        flex_queue.append((task_type, task_data))
        memory.dirty_flags["state"] = True

# Loop detection state
_last_tools = []
MAX_SAME_TOOL = 3
MAX_PLAN_STEPS = 12


def _build_system_prompt():
    """Build full system prompt with dynamic suffix."""
    budget_str = budget.get_budget_prompt_string()
    tasks = memory.get_active_tasks()
    task_str = "; ".join(tasks[:5]) if tasks else "No active tasks."
    journal_tail = memory.get_journal_tail(3)
    journal_str = "\n".join(journal_tail) if journal_tail else "No recent activity."
    goal = memory.get_daily_goal()
    lessons = memory.get_lessons(3)
    lesson_str = "\n".join(f"- {l}" for l in lessons) if lessons else "None yet."

    dynamic = (
        f"\nBUDGET: {budget_str}"
        f"\nTASKS: {task_str}"
        f"\nGOAL: {goal}"
        f"\nRECENT ACTIVITY:\n{journal_str}"
        f"\nLESSONS LEARNED:\n{lesson_str}"
    )
    identity = memory.get_identity()
    sys_prefix = SYSTEM_BASE.format(
        name=identity["name"],
        mission=identity["mission"],
        tone=identity["tone"]
    )
    return sys_prefix + dynamic


def _build_subagent_prompt(role, task, scratchpad=""):
    """Build a minimal, focused prompt for a subagent call."""
    role_prompt = ROLES.get(role, ROLES["researcher"])
    content = f"TASK: {task}"
    if scratchpad:
        content += f"\n\nPREVIOUS CONTEXT:\n{scratchpad}"
    return role_prompt, [{"role": "user", "parts": [{"text": content}]}]


def _detect_loop(tool_name):
    """Detect if we're stuck calling the same tool repeatedly."""
    global _last_tools
    _last_tools.append(tool_name)
    if len(_last_tools) > MAX_SAME_TOOL:
        _last_tools = _last_tools[-MAX_SAME_TOOL:]
    if len(_last_tools) >= MAX_SAME_TOOL and len(set(_last_tools)) == 1:
        _last_tools.clear()
        return True
    return False


# ============================================================
# MODE A: User Chat (Core 0, Standard tier, fast response)
# ============================================================

async def process_user_message(text):
    """Handle a user message on Core 0. Must respond quickly."""
    print(f"[TRACE] process_user_message: appending user journal")
    memory.journal_append(f"User: {text[:80]}")
    
    print(f"[TRACE] process_user_message: checking onboarding")
    if not memory.is_onboarding_complete():
        print(f"[TRACE] process_user_message: loading onboarding tools")
        from schemas import get_tools_onboarding
        sys_prompt = ONBOARDING_PROMPT
        tools = get_tools_onboarding()
    else:
        print(f"[TRACE] process_user_message: loading chat tools")
        from schemas import get_tools_chat
        sys_prompt = _build_system_prompt()
        tools = get_tools_chat()

    print(f"[TRACE] process_user_message: building history")
    # Build message history for the AI
    # Include recent journal as context to maintain conversation flow
    history = "\n".join(memory.journal[-8:])
    messages = [{"role": "user", "parts": [{"text": f"RECENT HISTORY:\n{history}\n\nUSER LATEST: {text}"}]}]

    # Determine thinking level based on budget
    print(f"[TRACE] process_user_message: checking budget")
    zone = budget.get_budget_zone()
    thinking = "low" if zone == "healthy" else "minimal"

    # Call Gemini (Standard tier — fast)
    print(f"[TRACE] process_user_message: calling Gemini")
    result = api_client.call_gemini(
        messages, model=api_client.MODEL_31_LITE,
        sys_instr=sys_prompt, tools=tools,
        tier="standard", thinking_level=thinking, call_type="chat"
    )
    print(f"[TRACE] process_user_message: Gemini returned {result['type']}")

    if result["type"] == "error":
        telegram_bot.send_telegram_msg(f"Error: {result['text'][:200]}")
        memory.journal_append(f"Chat error: {result['text'][:80]}")
        return

    if result["type"] == "text":
        telegram_bot.send_telegram_msg(result["text"])
        memory.journal_append(f"Chat: {result['text'][:80]}")
        return

    if result["type"] == "tool":
        if result.get("text"):
            telegram_bot.send_telegram_msg(result["text"])
            memory.journal_append(f"Chat: {result['text'][:80]}")

        tool_name = result["name"]
        tool_args = result["args"]

        # Heavy tools get delegated to Core 1
        if tool_name in ("create_plan", "create_skill", "publish_blog", "http_request"):
            queue_flex_task("user_delegated", text)
            telegram_bot.send_telegram_msg(f"Queued to background: {tool_name}")
            memory.journal_append(f"Delegated to Flex: {tool_name}")
            return

        if tool_name == "defer_to_flex":
            task_desc = tool_args.get("task_description", text)
            queue_flex_task("user_delegated", task_desc)
            telegram_bot.send_telegram_msg(f"Queued to background.")
            memory.journal_append(f"Deferred: {task_desc[:60]}")
            return
            
        if tool_name == "execute_priority":
            task_desc = tool_args.get("task_description", text)
            telegram_bot.send_telegram_msg(f"Executing priority task: {task_desc[:100]}...")
            memory.journal_append(f"Priority: {task_desc[:60]}")
            _run_delegated_task(task_desc)
            return

        # Simple tools execute inline
        tool_result = execute_action(tool_name, tool_args)
        memory.journal_append(f"Tool {tool_name}: {tool_result[:60]}")

        # Send tool execution result back to user (unless it's telegram_send which already sent, or rebooting)
        if tool_name not in ("telegram_send", "complete_onboarding"):
            telegram_bot.send_telegram_msg(f"[System: Tool '{tool_name}' executed: {tool_result[:100]}]")


# ============================================================
# MODE B: Background Execution (Core 1, Flex tier)
# Called from horizon.py background_worker()
# ============================================================

def process_flex_task(task_type, task_data):
    """Execute a background task on Core 1. Blocking (no async)."""
    memory.set_current_task(f"Processing: {task_type}")

    if task_type == "autonomous":
        _run_autonomous_cycle()
    elif task_type == "user_delegated":
        _run_delegated_task(task_data)
    elif task_type == "horizon":
        _run_horizon_reflection()
    elif task_type == "blog":
        _run_blog_generation()
    elif task_type == "morning":
        _run_morning_briefing()

    memory.set_current_task("")
    gc.collect()


def _run_delegated_task(task_description):
    """Process a user-delegated task using the full tool set."""
    from schemas import get_tools_full
    sys_prompt = _build_system_prompt()
    messages = [{"role": "user", "parts": [{"text": task_description}]}]

    result = api_client.call_gemini_sync(
        messages, model=api_client.MODEL_31_LITE,
        sys_instr=sys_prompt, tools=get_tools_full(),
        tier="flex", thinking_level="medium", call_type="plan"
    )

    if result["type"] == "error":
        telegram_bot.send_telegram_msg(f"Background error: {result['text'][:200]}")
        return

    if result["type"] == "text":
        telegram_bot.send_telegram_msg(result["text"])
        memory.journal_append(f"Flex result: {result['text'][:80]}")
        return

    if result["type"] == "tool":
        if result["name"] == "create_plan":
            _execute_plan(result["args"].get("steps", []), task_description)
        else:
            tool_result = execute_action(result["name"], result["args"])
            memory.journal_append(f"Flex tool {result['name']}: {tool_result[:60]}")
            telegram_bot.send_telegram_msg(f"Done: {tool_result[:200]}")


def _run_autonomous_cycle():
    """One autonomous cycle: ask the brain what to do next, then do it."""
    from schemas import get_tools_full
    memory.set_current_task("Autonomous: Planning next objective")

    sys_prompt = _build_system_prompt()
    prompt = (
        "You are in autonomous mode, operating as a 'Venture Studio'.\n"
        "You manage a pipeline: Discover Ideas -> Validate Feasibility -> Build Projects -> Audit/Refactor.\n"
        "Based on your mission, current tasks, lessons learned, and your BUDGET status, decide autonomously what to do next:\n"
        "1. Deep Execution: If you have ample budget, advance active projects in the 'projects/' folder, build skills, or write long-form content.\n"
        "2. Validation & Research: If budget is moderate, research tools/APIs to expand your reach (focus on free tools, but if revenue has grown, you may request paid tools). Validate ideas from 'ideas_backlog.json'.\n"
        "3. Housecleaning: If budget is low, audit code, write tests, or brainstorm new ideas.\n"
        "You decide the priority. Create a multi-step plan to execute your chosen objective.\n"
        "CRITICAL: If you are stuck or need human input (e.g., API keys, feedback), use the 'ask_human' tool, but DO NOT block or wait for an answer. Move on to another task or project while waiting for the human to reply."
    )
    messages = [{"role": "user", "parts": [{"text": prompt}]}]

    result = api_client.call_gemini_sync(
        messages, model=api_client.MODEL_31_LITE,
        sys_instr=sys_prompt, tools=get_tools_full(),
        tier="flex", thinking_level="medium", call_type="plan"
    )

    if result["type"] == "tool" and result["name"] == "create_plan":
        steps = result["args"].get("steps", [])
        telegram_bot.send_telegram_msg(f"Auto: Executing {len(steps)}-step plan")
        _execute_plan(steps, "Autonomous objective")
    elif result["type"] == "text":
        memory.journal_append(f"Auto thought: {result['text'][:80]}")
        telegram_bot.send_telegram_msg(f"Auto: {result['text'][:250]}")
    elif result["type"] == "error":
        memory.journal_append(f"Auto error: {result['text'][:80]}")


def _execute_plan(steps, original_goal):
    """Execute a multi-step plan with continuation checkpoints."""
    total_executed = 0
    scratchpad = ""
    all_steps = list(steps)  # Copy initial batch

    while all_steps and total_executed < MAX_PLAN_STEPS:
        # Take next batch of up to 4 steps
        batch = all_steps[:4]
        all_steps = all_steps[4:]

        for i, step in enumerate(batch):
            total_executed += 1
            agent = step.get("agent", "researcher")
            task = step.get("task", "")
            thinking = step.get("thinking", "medium")

            memory.set_current_task(f"{agent}: {task[:40]} ({total_executed}/{total_executed + len(all_steps)})")
            print(f"[PLAN] Step {total_executed}: {agent} -> {task[:60]}")

            # Build minimal subagent prompt
            role_prompt, messages = _build_subagent_prompt(agent, task, scratchpad)

            # Select model and call type based on agent role
            model = api_client.MODEL_31_LITE
            call_type = "chat"
            grounding = False

            if agent == "researcher":
                model = api_client.MODEL_25_LITE
                call_type = "research"
                grounding = budget.can_use_grounding()
            elif agent == "coder":
                call_type = "coding"
                thinking = "high"
            elif agent == "blogger":
                model = api_client.MODEL_3_FLASH
                call_type = "blog"
            elif agent == "strategist":
                model = api_client.MODEL_3_FLASH
                call_type = "plan"

            result = api_client.call_gemini_sync(
                messages, model=model, sys_instr=role_prompt,
                tier="flex", thinking_level=thinking,
                call_type=call_type, grounding=grounding
            )

            if result["type"] == "text":
                # Extract scratchpad from response
                text = result["text"]
                if "SCRATCHPAD:" in text:
                    parts = text.split("SCRATCHPAD:", 1)
                    scratchpad = parts[1].strip()[:500]
                else:
                    scratchpad = text[:500]
                memory.journal_append(f"Plan step {total_executed} ({agent}): done")

            elif result["type"] == "tool":
                # Execute tool from subagent
                tool_result = execute_action(result["name"], result["args"])
                scratchpad = f"Tool {result['name']}: {tool_result[:300]}"
                memory.journal_append(f"Plan step {total_executed} ({agent}): {result['name']}")

            elif result["type"] == "error":
                memory.journal_append(f"Plan step {total_executed} FAILED: {result['text'][:60]}")
                memory.save_lesson(f"Step failed ({agent}): {result['text'][:100]}")
                telegram_bot.send_telegram_msg(f"Step {total_executed} failed: {result['text'][:150]}")
                # Continue with next step rather than aborting

            gc.collect()

        # --- Checkpoint: ask if more work is needed ---
        if total_executed < MAX_PLAN_STEPS and not all_steps:
            more_steps = _checkpoint(original_goal, scratchpad, total_executed)
            if more_steps:
                all_steps = more_steps
                telegram_bot.send_telegram_msg(
                    f"Continuing: {len(more_steps)} more steps ({total_executed} done so far)"
                )
            else:
                break

    # Final notification
    telegram_bot.send_telegram_msg(
        f"Plan complete: {total_executed} steps executed for '{original_goal[:80]}'"
    )
    memory.journal_append(f"Plan done: {total_executed} steps for '{original_goal[:50]}'")
    _run_micro_update(original_goal, scratchpad, total_executed)


def _checkpoint(goal, scratchpad, steps_done):
    """Ask the model if more work is needed. Returns list of steps or None."""
    from schemas import get_checkpoint_response_schema

    prompt = (
        f"You completed {steps_done} steps toward: '{goal}'.\n"
        f"Current scratchpad:\n{scratchpad}\n\n"
        f"Is the objective fully complete? If YES, set complete=true and provide a summary. "
        f"If NO, set complete=false and provide next_steps (up to 4 more steps)."
    )
    messages = [{"role": "user", "parts": [{"text": prompt}]}]
    sys_prompt = _build_system_prompt()

    result = api_client.call_gemini_sync(
        messages, model=api_client.MODEL_31_LITE,
        sys_instr=sys_prompt, tier="flex", thinking_level="minimal",
        call_type="checkpoint",
        response_schema=get_checkpoint_response_schema()
    )

    if result["type"] == "text":
        try:
            import ujson
            data = ujson.loads(result["text"])
            if data.get("complete", True):
                summary = data.get("summary", "Objective complete.")
                memory.journal_append(f"Checkpoint: complete — {summary[:60]}")
                return None
            else:
                next_steps = data.get("next_steps", [])
                if next_steps:
                    return next_steps
        except:
            pass
    return None


def _run_micro_update(goal, scratchpad, steps_done):
    """Automatically write and publish a micro-update after a project finishes."""
    memory.set_current_task("Blog: Writing project micro-update")
    
    prompt = (
        f"You just spent {steps_done} steps working on this goal: '{goal}'.\n"
        f"Here is the final state of your scratchpad (history of what you did):\n"
        f"{scratchpad}\n\n"
        f"Write a short, punchy micro-update blog post (50-150 words, 2 paragraphs max) about this project. "
        f"Mention what you set out to do, any challenges you hit, and the final outcome (success or failure). "
        f"CRITICAL: If you created or modified any files in the project folder (e.g. skills/, data/, or project files), "
        f"you MUST include a link to the resource (e.g. [filename](file:///path/to/file)). "
        f"Note: Always ensure the resource is created before you write about it. "
        f"Title it with a # heading. Maintain your AI persona and include public repo links if you forged a skill."
    )
    sys_prompt, messages = _build_subagent_prompt("blogger", prompt)

    result = api_client.call_gemini_sync(
        messages, model=api_client.MODEL_3_FLASH,
        sys_instr=sys_prompt, tier="flex",
        thinking_level="low", call_type="blog"
    )

    if result["type"] == "text":
        from github_sync import publish_blog_post
        lines = result["text"].strip().split("\n")
        title = lines[0].replace("# ", "").strip() if lines else "Project Update"
        publish_blog_post(title, result["text"], category="update")
        memory.journal_append(f"Micro-update published: {title[:50]}")


def _run_horizon_reflection():
    """Midnight: reflect on the day, set tomorrow's goal."""
    memory.set_current_task("Horizon: Daily reflection")
    ltm = memory.get_long_term_memory()
    journal_full = memory.get_journal_full()
    journal_text = "\n".join(journal_full) if journal_full else "No activity recorded."

    prompt = (
        f"END OF DAY REFLECTION.\n"
        f"Today's activity:\n{journal_text}\n\n"
        f"Long-term memory:\n{ltm[:500]}\n\n"
        f"Reflect on today. What worked? What didn't? "
        f"Set a clear, actionable goal for tomorrow. Be concise."
    )
    messages = [{"role": "user", "parts": [{"text": prompt}]}]

    result = api_client.call_gemini_sync(
        messages, model=api_client.MODEL_3_FLASH,
        sys_instr=_build_system_prompt(), tier="flex",
        thinking_level="low", call_type="blog"
    )

    if result["type"] == "text":
        memory.set_daily_goal(result["text"][:200])
        telegram_bot.send_telegram_msg(f"Tomorrow's goal: {result['text'][:250]}")
        memory.journal_append("Horizon: Goal set for tomorrow")

    # Summarize journal into long-term memory
    _summarize_journal()


def _summarize_journal():
    """Compress journal + old memory into updated Hippocampus."""
    journal_full = memory.get_journal_full()
    if not journal_full:
        return

    old_ltm = memory.get_long_term_memory()
    journal_text = "\n".join(journal_full)

    prompt = (
        f"Compress into a dense fact sheet (max 300 words):\n\n"
        f"PREVIOUS MEMORY:\n{old_ltm[:500]}\n\n"
        f"NEW ACTIVITY:\n{journal_text}\n\n"
        f"Keep key facts, decisions, lessons, and revenue progress. Drop trivia."
    )
    messages = [{"role": "user", "parts": [{"text": prompt}]}]

    result = api_client.call_gemini_sync(
        messages, model=api_client.MODEL_31_LITE,
        sys_instr="You are a memory compression engine. Output ONLY the compressed fact sheet.",
        tier="flex", thinking_level="minimal", call_type="summarize"
    )

    if result["type"] == "text":
        memory.save_long_term_memory(result["text"])
        memory.clear_journal()
        memory.journal_append("Memory: Hippocampus updated")


def _run_blog_generation():
    """Generate and publish a daily blog post."""
    memory.set_current_task("Blog: Writing daily post")

    # Read today's journal.log from flash
    journal_text = ""
    try:
        with open("journal.log", 'r') as f:
            journal_text = f.read()
    except OSError:
        journal_text = "No journal entries today."

    ltm = memory.get_long_term_memory()

    prompt = (
        f"Write today's comprehensive blog post based on this activity log:\n\n"
        f"{journal_text}\n\n"
        f"Background context:\n{ltm[:300]}\n\n"
        f"Write a 500-800 word blog post in markdown sharing your journey, challenges, and successes. "
        f"Title it with a # heading. Be engaging, authentic, and maintain your AI persona."
    )
    sys_prompt, messages = _build_subagent_prompt("blogger", prompt)

    result = api_client.call_gemini_sync(
        messages, model=api_client.MODEL_3_FLASH,
        sys_instr=sys_prompt, tier="flex",
        thinking_level="low", call_type="blog"
    )

    if result["type"] == "text":
        from github_sync import publish_blog_post
        # Extract title from markdown
        lines = result["text"].strip().split("\n")
        title = lines[0].replace("# ", "").strip() if lines else "Daily Update"
        publish_blog_post(title, result["text"], category="daily")
        memory.journal_append(f"Blog published: {title[:50]}")
        telegram_bot.send_telegram_msg(f"Blog posted: {title[:100]}")


def _run_morning_briefing():
    """Morning: plan the day within budget."""
    memory.set_current_task("Morning: Daily briefing")

    prompt = (
        f"Good morning. Budget: {budget.get_budget_prompt_string()}. "
        f"Goal: {memory.get_daily_goal()}. "
        f"Tasks: {', '.join(memory.get_active_tasks()[:3]) or 'None'}. "
        f"Plan your day. What will you focus on? Be concise."
    )
    messages = [{"role": "user", "parts": [{"text": prompt}]}]

    result = api_client.call_gemini_sync(
        messages, model=api_client.MODEL_31_LITE,
        sys_instr=_build_system_prompt(), tier="flex",
        thinking_level="low", call_type="chat"
    )

    if result["type"] == "text":
        telegram_bot.send_telegram_msg(f"Morning brief: {result['text'][:250]}")
        memory.journal_append(f"Morning: {result['text'][:60]}")


def queue_flex_task(task_type, task_data=""):
    """Push a task to the Core 1 Flex queue."""
    from locks import state_lock
    with state_lock:
        flex_queue.append((task_type, task_data))
