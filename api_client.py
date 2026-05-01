# api_client.py — Unified Gemini REST client for Pico 2W
import urequests
import ujson
import gc
import micropython
from secrets import GEMINI_API_KEY
from locks import net_lock
import budget

# --- Model constants ---
MODEL_31_LITE = "gemini-3.1-flash-lite-preview"
MODEL_3_FLASH = "gemini-3-flash-preview"
MODEL_25_LITE = "gemini-2.5-flash-lite"

# Pre-built URL base (avoids repeated string allocation)
_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models/"
_API_SUFFIX = ":generateContent?key=" + GEMINI_API_KEY

# Max output tokens by call type
TOKEN_CAPS = {
    "chat": 500,
    "plan": 800,
    "checkpoint": 200,
    "research": 1000,
    "coding": 2000,
    "summarize": 500,
    "blog": 1500,
}


def call_gemini(messages, model=MODEL_31_LITE, sys_instr=None,
                tools=None, grounding=False, tier="standard",
                thinking_level=None, thinking_budget=None,
                call_type="chat", response_schema=None):
    """Make a single Gemini API call.
    
    Args:
        messages: List of {"role": "user"/"model", "parts": [{"text": "..."}]}
        model: Model identifier string
        sys_instr: System instruction text
        tools: Tool schema list (from schemas.py)
        grounding: Enable Google Search grounding
        tier: "standard" or "flex"
        thinking_level: For 3.x models — "minimal","low","medium","high"
        thinking_budget: For 2.5 models — integer token budget
        call_type: Key into TOKEN_CAPS for maxOutputTokens
        response_schema: For structured JSON output
    
    Returns:
        {"type": "text"/"tool"/"error", "text": str, "name": str, "args": dict, "usage": dict}
    """
    gc.collect()
    url = _API_BASE + model + _API_SUFFIX

    # Build generation config
    gen_config = {"maxOutputTokens": TOKEN_CAPS.get(call_type, 500)}

    if model.startswith("gemini-3"):
        gen_config["temperature"] = 1.0  # Required for reasoning models
        if thinking_level:
            gen_config["thinkingConfig"] = {"thinkingLevel": thinking_level}
    elif model.startswith("gemini-2.5"):
        gen_config["temperature"] = 0.7
        if thinking_budget is not None:
            gen_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}
    else:
        gen_config["temperature"] = 0.7

    # Structured output
    if response_schema:
        gen_config["responseMimeType"] = "application/json"
        gen_config["responseSchema"] = response_schema

    # Build payload
    payload = {
        "contents": messages,
        "generationConfig": gen_config,
        # Disable safety metadata to reduce response size
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "OFF"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "OFF"},
        ],
    }

    if sys_instr:
        payload["system_instruction"] = {"parts": [{"text": sys_instr}]}

    if tools:
        payload["tools"] = tools

    if grounding:
        if "tools" not in payload:
            payload["tools"] = []
        payload["tools"].append({"google_search": {}})

    if tier == "flex":
        payload["service_tier"] = "flex"

    # Make request
    timeout = 600 if tier == "flex" else 30
    res = None
    try:
        with net_lock:
            res = urequests.post(url, json=payload, timeout=timeout)
        data = res.json()

        if "error" in data:
            err_msg = data["error"].get("message", "Unknown API error")
            print(f"[API] Error: {err_msg}")
            return {"type": "error", "text": err_msg, "usage": {}}

        # Extract usage
        usage = data.get("usageMetadata", {})
        t_in = usage.get("promptTokenCount", 0)
        t_out = usage.get("candidatesTokenCount", 0)
        t_think = usage.get("thoughtsTokenCount", 0)

        # Log spend
        budget.log_spend(model, t_in, t_out, t_think, tier,
                         is_grounding=grounding)

        # Parse response — find first actionable part
        candidates = data.get("candidates", [{}])
        parts = candidates[0].get("content", {}).get("parts", [])

        for part in parts:
            # Skip thought parts (thoughtSignature)
            if part.get("thought"):
                continue
            if "functionCall" in part:
                fc = part["functionCall"]
                return {
                    "type": "tool",
                    "name": fc["name"],
                    "args": fc.get("args", {}),
                    "usage": {"in": t_in, "out": t_out, "think": t_think},
                }
            if "text" in part:
                return {
                    "type": "text",
                    "text": part["text"],
                    "usage": {"in": t_in, "out": t_out, "think": t_think},
                }

        return {"type": "text", "text": "", "usage": {"in": t_in, "out": t_out, "think": t_think}}

    except Exception as e:
        # Invalidate DNS cache on connection errors
        from wifi_mgmt import invalidate_dns_cache
        invalidate_dns_cache()
        return {"type": "error", "text": str(e), "usage": {}}
    finally:
        if res:
            res.close()
        gc.collect()


def call_gemini_sync(messages, model=MODEL_31_LITE, sys_instr=None,
                     tools=None, tier="flex", thinking_level=None,
                     call_type="chat"):
    """Synchronous version for Core 1 (background thread).
    Core 1 cannot use uasyncio, so this is a blocking call."""
    return call_gemini(messages, model=model, sys_instr=sys_instr,
                       tools=tools, tier=tier, thinking_level=thinking_level,
                       call_type=call_type)


def call_with_fallback(messages, model=MODEL_31_LITE, sys_instr=None,
                       tools=None, tier="flex", thinking_level=None,
                       call_type="chat", retries=3):
    """Try Flex tier first, fallback to Standard after retries."""
    import uasyncio as asyncio
    for attempt in range(retries):
        result = call_gemini(messages, model=model, sys_instr=sys_instr,
                             tools=tools, tier=tier,
                             thinking_level=thinking_level,
                             call_type=call_type)
        if result["type"] != "error":
            return result
        # Brief delay before retry
        import time
        time.sleep(2)
    # Final attempt on standard tier
    return call_gemini(messages, model=model, sys_instr=sys_instr,
                       tools=tools, tier="standard",
                       thinking_level=thinking_level,
                       call_type=call_type)
