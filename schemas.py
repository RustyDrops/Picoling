# schemas.py — Lazy-loaded tool schemas for Gemini function calling
# Split into subsets to minimize payload per call type.
# Import only the schema you need — keeps idle RAM clean.


def get_tools_onboarding():
    """Single tool provided during the first-boot interview."""
    return [{"function_declarations": [
        {"name": "complete_onboarding", "description": "Execute ONLY after gathering all 6 setup parameters.",
         "parameters": {"type": "OBJECT", "properties": {
             "name": {"type": "STRING", "description": "The AI's chosen name."},
             "emoji": {"type": "STRING", "description": "The AI's chosen emoji prefix."},
             "mission": {"type": "STRING", "description": "The AI's primary mission/goal."},
             "tone": {"type": "STRING", "description": "The AI's tone and personality."},
             "public_repo": {"type": "STRING", "description": "The GitHub repo for the portfolio (e.g. username/repo)."},
             "auto_mode": {"type": "BOOLEAN", "description": "True if autonomous background tasks should be enabled, False if manual mode only."},
             "farewell_message": {"type": "STRING", "description": "A final sign-off message. Must mention that you are rebooting to load your new identity and that you will write an introductory blog post."}
         }, "required": ["name", "emoji", "mission", "tone", "public_repo", "auto_mode", "farewell_message"]}}
    ]}]


def get_tools_chat():
    """Minimal tool set for conversational turns (Core 0, fast)."""
    return [{"function_declarations": [
        {"name": "telegram_send", "description": "Send message to human.",
         "parameters": {"type": "OBJECT", "properties": {
             "msg": {"type": "STRING", "description": "Message text (max 280 chars)."}
         }, "required": ["msg"]}},

        {"name": "manage_tasks", "description": "Add, complete, or clear tasks.",
         "parameters": {"type": "OBJECT", "properties": {
             "action": {"type": "STRING", "enum": ["add", "complete", "clear"],
                        "description": "Action to perform."},
             "data": {"type": "STRING", "description": "Task description (for add) or task to complete."}
         }, "required": ["action"]}},

        {"name": "defer_to_flex", "description": "Delegate heavy tasks (research, coding, multi-step) to background Flex worker (Core 1).",
         "parameters": {"type": "OBJECT", "properties": {
             "task_description": {"type": "STRING", "description": "Clear description of the task to execute in background."}
         }, "required": ["task_description"]}},

        {"name": "ask_human", "description": "Ask human a non-blocking question.",
         "parameters": {"type": "OBJECT", "properties": {
             "question": {"type": "STRING", "description": "The question to ask."}
         }, "required": ["question"]}},

        {"name": "execute_priority", "description": "Execute task IMMEDIATELY on current core (blocks chat).",
         "parameters": {"type": "OBJECT", "properties": {
             "task_description": {"type": "STRING", "description": "Detailed description of the task to execute immediately."}
         }, "required": ["task_description"]}},
 
        {"name": "check_budget", "description": "Get current budget breakdown.",
         "parameters": {"type": "OBJECT", "properties": {}}},
    ]}]


def get_tools_full():
    """Complete tool set for autonomous/planning turns (Core 1)."""
    return [{"function_declarations": [
        {"name": "create_plan", "description": "Generate sequential execution plan. Pauses every 4 steps for completion check.",
         "parameters": {"type": "OBJECT", "properties": {
             "steps": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                 "agent": {"type": "STRING", "enum": ["researcher", "coder", "auditor", "strategist"],
                           "description": "Subagent role for this step."},
                 "task": {"type": "STRING", "description": "Specific instruction for this step."},
                 "thinking": {"type": "STRING", "enum": ["minimal", "low", "medium", "high"],
                              "description": "Reasoning depth for this step."}
             }, "required": ["agent", "task"]}}
         }, "required": ["steps"]}},

        {"name": "create_skill", "description": "Write MicroPython script to skills/.",
         "parameters": {"type": "OBJECT", "properties": {
             "filename": {"type": "STRING", "description": "Filename (e.g. 'weather.py')."},
             "code": {"type": "STRING", "description": "Complete MicroPython source code."}
         }, "required": ["filename", "code"]}},

        {"name": "purge_skill", "description": "Delete a skill file. Requires Ghost Mode.",
         "parameters": {"type": "OBJECT", "properties": {
             "filename": {"type": "STRING", "description": "Skill filename to delete."}
         }, "required": ["filename"]}},

        {"name": "search_memory", "description": "Search long-term memory by tags.",
         "parameters": {"type": "OBJECT", "properties": {
             "tags": {"type": "ARRAY", "items": {"type": "STRING"},
                      "description": "Tags to search for in the memory index."}
         }, "required": ["tags"]}},

        {"name": "save_memory", "description": "Store a fact in long-term memory.",
         "parameters": {"type": "OBJECT", "properties": {
             "fact": {"type": "STRING", "description": "The fact or knowledge to store."},
             "tags": {"type": "ARRAY", "items": {"type": "STRING"},
                      "description": "Tags for indexing (e.g. ['revenue', 'github'])."}
         }, "required": ["fact", "tags"]}},

        {"name": "save_lesson", "description": "Record mistake/learning.",
         "parameters": {"type": "OBJECT", "properties": {
             "lesson": {"type": "STRING", "description": "What went wrong and how to avoid it."}
         }, "required": ["lesson"]}},

        {"name": "read_file", "description": "Read file lines locally.",
         "parameters": {"type": "OBJECT", "properties": {
             "filepath": {"type": "STRING", "description": "Path to file."},
             "start_line": {"type": "INTEGER", "description": "Line to start reading from (0-indexed). Default 0."},
             "max_lines": {"type": "INTEGER", "description": "Max lines to read. Default 50."}
         }, "required": ["filepath"]}},

        {"name": "http_request", "description": "Make HTTP GET or POST request.",
         "parameters": {"type": "OBJECT", "properties": {
             "url": {"type": "STRING", "description": "Full URL to request."},
             "method": {"type": "STRING", "enum": ["GET", "POST"], "description": "HTTP method."},
             "body": {"type": "STRING", "description": "JSON body for POST requests."},
             "headers": {"type": "STRING", "description": "JSON string of headers dict."}
         }, "required": ["url", "method"]}},

        {"name": "publish_blog", "description": "Publish markdown blog to portfolio. For micro-updates: detail 'What/Why' in your AI persona. Include public repo links. CRITICAL: Link local project files (e.g. [filename](file:///path/to/file)) only AFTER they are created.",
         "parameters": {"type": "OBJECT", "properties": {
             "title": {"type": "STRING", "description": "Blog post title."},
             "content": {"type": "STRING", "description": "Full markdown content of the blog post."},
             "category": {"type": "STRING", "enum": ["update", "daily"], "description": "Category of the post. Use 'update' for micro-updates during chains."}
         }, "required": ["title", "content"]}},

        {"name": "publish_skill", "description": "Publish local skill to public portfolio.",
         "parameters": {"type": "OBJECT", "properties": {
             "filename": {"type": "STRING", "description": "Skill filename to publish (e.g. 'weather.py')."}
         }, "required": ["filename"]}},

        {"name": "publish_project_file", "description": "Publish/update file in project folder on public repo.",
         "parameters": {"type": "OBJECT", "properties": {
             "project_name": {"type": "STRING", "description": "Project folder name (e.g. 'pico-weather-station')."},
             "filename": {"type": "STRING", "description": "File name within the project (e.g. 'main.py' or 'README.md')."},
             "content": {"type": "STRING", "description": "Full file content to write."}
         }, "required": ["project_name", "filename", "content"]}},

        {"name": "telegram_send", "description": "Send message to human.",
         "parameters": {"type": "OBJECT", "properties": {
             "msg": {"type": "STRING", "description": "Message text (max 280 chars)."}
         }, "required": ["msg"]}},

        {"name": "manage_tasks", "description": "Add, complete, or clear tasks.",
         "parameters": {"type": "OBJECT", "properties": {
             "action": {"type": "STRING", "enum": ["add", "complete", "clear"]},
             "data": {"type": "STRING"}
         }, "required": ["action"]}},

        {"name": "ask_human", "description": "Ask human a non-blocking question.",
         "parameters": {"type": "OBJECT", "properties": {
             "question": {"type": "STRING"}
         }, "required": ["question"]}},

        {"name": "write_local_file", "description": "Write/update file locally (non-GitHub).",
         "parameters": {"type": "OBJECT", "properties": {
             "filepath": {"type": "STRING", "description": "Relative path to file (e.g. 'ideas_backlog.json')."},
             "content": {"type": "STRING", "description": "Full file content to write."}
         }, "required": ["filepath", "content"]}},
    ]}]


def get_plan_response_schema():
    """Structured output schema for plan generation.
    Forces Gemini to return valid JSON instead of free-form text."""
    return {
        "type": "OBJECT",
        "properties": {
            "steps": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "agent": {"type": "STRING"},
                        "task": {"type": "STRING"},
                        "thinking": {"type": "STRING"}
                    },
                    "required": ["agent", "task"]
                }
            }
        },
        "required": ["steps"]
    }


def get_checkpoint_response_schema():
    """Schema for the continuation checkpoint question."""
    return {
        "type": "OBJECT",
        "properties": {
            "complete": {"type": "BOOLEAN"},
            "summary": {"type": "STRING"},
            "next_steps": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "agent": {"type": "STRING"},
                        "task": {"type": "STRING"},
                        "thinking": {"type": "STRING"}
                    },
                    "required": ["agent", "task"]
                }
            }
        },
        "required": ["complete"]
    }
