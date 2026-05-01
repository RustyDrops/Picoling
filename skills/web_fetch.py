# skills/web_fetch.py — HTTP GET with size limits
import urequests
import gc
from locks import net_lock


def tool_fetch_url(url, max_bytes=2000, timeout=10):
    """Fetch content from a URL with size and timeout limits.
    Returns the first max_bytes of the response body."""
    res = None
    try:
        with net_lock:
            res = urequests.get(url, timeout=timeout)
        status = res.status_code
        text = res.text[:max_bytes] if res.text else ""
        return f"HTTP {status}:\n{text}"
    except Exception as e:
        return f"Fetch error: {e}"
    finally:
        if res:
            res.close()
        gc.collect()
