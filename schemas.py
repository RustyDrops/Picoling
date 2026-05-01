# schemas.py — Lazy-loaded tool schemas for Gemini function calling
# Split into subsets to minimize payload per call type.
# Import only the schema you need — keeps idle RAM clean.


def get_tools_onboarding():
    """Single tool provided during the first-boot interview."""
    return [{"function_declarations": [
        {"name": "complete_onboarding", "description": "Call this ONLY after you have gathered all 6 pieces of information from the human.",
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
        {"name": "telegram_send", "description": "Send a message to the human operator.",
         "parameters": {"type": "OBJECT", "properties": {
             "msg": {"type": "STRING", "description": "Message text (max 280 chars)."}
         }, "required": ["msg"]}},

        {"name": "manage_tasks", "description": "Add, complete, or clear tasks in the task queue.",
         "parameters": {"type": "OBJECT", "properties": {
             "action": {"type": "STRING", "enum": ["add", "complete", "clear"],
                        "description": "Action to perform."},
             "data": {"type": "STRING", "description": "Task description (for add) or task to complete."}
         }, "required": ["action"]}},

        {"name": "defer_to_flex", "description": "Push a complex task to the background Flex worker (Core 1). Use this for research, coding, multi-step plans, or anything that takes time.",
         "parameters": {"type": "OBJECT", "properties": {
             "task_description": {"type": "STRING", "description": "Clear description of the task to execute in background."}
         }, "required": ["task_description"]}},

        {"name": "ask_human", "description": "Ask the human a non-blocking question. Creates a ticket they can answer later.",
         "parameters": {"type": "OBJECT", "properties": {
             "question": {"type": "STRING", "description": "The question to ask."}
         }, "required": ["question"]}},

        {"name": "check_budget", "description": "Get current budget breakdown.",
         "parameters": {"type": "OBJECT", "properties": {}}},
    ]}]


def get_tools_full():
    """Complete tool set for autonomous/planning turns (Core 1)."""
    return [{"function_declarations": [
        {"name": "create_plan", "description": "Generate a multi-step execution plan. Steps run sequentially. After each batch of 4 steps, you will be asked if the objective is complete or if more steps are needed.",
         "parameters": {"type": "OBJECT", "properties": {
             "steps": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                 "agent": {"type": "STRING", "enum": ["researcher", "coder", "auditor", "blogger", "strategist"],
                           "description": "Subagent role for this step."},
                 "task": {"type": "STRING", "description": "Specific instruction for this step."},
                 "thinking": {"type": "STRING", "enum": ["minimal", "low", "medium", "high"],
                              "description": "Reasoning depth for this step."}
             }, "required": ["agent", "task"]}}
         }, "required": ["steps"]}},

        {"name": "create_skill", "description": "Write a MicroPython script to the skills/ directory.",
         "parameters": {"type": "OBJECT", "properties": {
             "filename": {"type": "STRING", "description": "Filename (e.g. 'weather.py')."},
             "code": {"type": "STRING", "description": "Complete MicroPython source code."}
         }, "required": ["filename", "code"]}},

        {"name": "purge_skill", "description": "Delete a skill file. Only works if Ghost Mode is enabled.",
         "parameters": {"type": "OBJECT", "properties": {
             "filename": {"type": "STRING", "description": "Skill filename to delete."}
         }, "required": ["filename"]}},

        {"name": "search_memory", "description": "Search long-term memory by tags.",
         "parameters": {"type": "OBJECT", "properties": {
             "tags": {"type": "ARRAY", "items": {"type": "STRING"},
                      "description": "Tags to search for in the memory index."}
         }, "required": ["tags"]}},

        {"name": "save_memory", "description": "Store a fact in long-term memory with tags for later retrieval.",
         "parameters": {"type": "OBJECT", "properties": {
             "fact": {"type": "STRING", "description": "The fact or knowledge to store."},
             "tags": {"type": "ARRAY", "items": {"type": "STRING"},
                      "description": "Tags for indexing (e.g. ['revenue', 'github'])."}
         }, "required": ["fact", "tags"]}},

        {"name": "save_lesson", "description": "Record a mistake or learning to avoid repeating it.",
         "parameters": {"type": "OBJECT", "properties": {
             "lesson": {"type": "STRING", "description": "What went wrong and how to avoid it."}
         }, "required": ["lesson"]}},

        {"name": "read_file", "description": "Read lines from a file on the Pico filesystem.",
         "parameters": {"type": "OBJECT", "properties": {
             "filepath": {"type": "STRING", "description": "Path to file."},
             "start_line": {"type": "INTEGER", "description": "Line to start reading from (0-indexed). Default 0."},
             "max_lines": {"type": "INTEGER", "description": "Max lines to read. Default 50."}
         }, "required": ["filepath"]}},

        {"name": "http_request", "description": "Make an HTTP GET or POST request to an external API.",
         "parameters": {"type": "OBJECT", "properties": {
             "url": {"type": "STRING", "description": "Full URL to request."},
             "method": {"type": "STRING", "enum": ["GET", "POST"], "description": "HTTP method."},
             "body": {"type": "STRING", "description": "JSON body for POST requests."},
             "headers": {"type": "STRING", "description": "JSON string of headers dict."}
         }, "required": ["url", "method"]}},

        {"name": "publish_blog", "description": "Publish a markdown blog post to the public portfolio repo (GitHub Pages).",
         "parameters": {"type": "OBJECT", "properties": {
             "title": {"type": "STRING", "description": "Blog post title."},
             "content": {"type": "STRING", "description": "Full markdown content of the blog post."}
         }, "required": ["title", "content"]}},

        {"name": "publish_skill", "description": "Publish a skill from the local skills/ directory to the public portfolio repo for others to see and use.",
         "parameters": {"type": "OBJECT", "properties": {
             "filename": {"type": "STRING", "description": "Skill filename to publish (e.g. 'weather.py')."}
         }, "required": ["filename"]}},

        {"name": "publish_project_file", "description": "Create or update a file in a named project folder on the public portfolio repo. Use this to build open-source projects that showcase your capabilities.",
         "parameters": {"type": "OBJECT", "properties": {
             "project_name": {"type": "STRING", "description": "Project folder name (e.g. 'pico-weather-station')."},
             "filename": {"type": "STRING", "description": "File name within the project (e.g. 'main.py' or 'README.md')."},
             "content": {"type": "STRING", "description": "Full file content to write."}
         }, "required": ["project_name", "filename", "content"]}},

        {"name": "telegram_send", "description": "Send a message to the human operator.",
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
