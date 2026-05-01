# skills/blog_post.py — Publish markdown blog posts to GitHub Pages
import urequests
import ujson
import ubinascii
import gc
import time
from secrets import GH_TOKEN, GH_PUBLIC_REPO
from locks import net_lock

GITHUB_API = f"https://api.github.com/repos/{GH_PUBLIC_REPO}/contents/"
HEADERS = {
    "Authorization": f"token {GH_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "Picoling-Pico"
}


def _get_sha(path):
    """Get the SHA of an existing file (needed for updates)."""
    url = GITHUB_API + path
    res = None
    try:
        with net_lock:
            res = urequests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            return res.json().get("sha")
    except:
        pass
    finally:
        if res:
            res.close()
    return None


def tool_publish_blog(title, markdown_content):
    """Publish a markdown blog post to GitHub Pages.
    Creates a dated file in the _posts/ directory."""
    t = time.localtime()
    date_str = f"{t[0]}-{t[1]:02d}-{t[2]:02d}"
    # Sanitize title for filename
    slug = title.lower().replace(" ", "-")
    for ch in "!@#$%^&*()[]{}|\\;:'\",.<>?/":
        slug = slug.replace(ch, "")
    slug = slug[:50]  # Limit length

    filepath = f"_posts/{date_str}-{slug}.md"

    # Add front matter for Jekyll
    full_content = (
        f"---\n"
        f"title: \"{title}\"\n"
        f"date: {date_str}\n"
        f"---\n\n"
        f"{markdown_content}"
    )

    b64 = ubinascii.b2a_base64(full_content.encode()).decode().strip()
    sha = _get_sha(filepath)

    payload = {
        "message": f"Blog: {title[:50]}",
        "content": b64,
    }
    if sha:
        payload["sha"] = sha

    url = GITHUB_API + filepath
    res = None
    try:
        with net_lock:
            res = urequests.put(url, json=payload, headers=HEADERS, timeout=20)
        status = res.status_code
        if 200 <= status <= 201:
            return f"Published: {filepath}"
        else:
            return f"Publish failed: HTTP {status}"
    except Exception as e:
        return f"Publish error: {e}"
    finally:
        if res:
            res.close()
        gc.collect()
