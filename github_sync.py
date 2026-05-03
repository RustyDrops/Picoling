# github_sync.py — Dual-repo GitHub integration
# Private repo: Automated nightly backups of internal state and skills
# Public repo: Blog posts, curated skill sharing, open-source projects
import urequests
import ujson
import ubinascii
import uos
import gc
from secrets import GH_TOKEN, GH_PRIVATE_REPO, GH_PUBLIC_REPO
from locks import net_lock

PRIVATE_API = f"https://api.github.com/repos/{GH_PRIVATE_REPO}/contents/"
PUBLIC_API = f"https://api.github.com/repos/{GH_PUBLIC_REPO}/contents/"

HEADERS = {
    "Authorization": f"token {GH_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "Picoling-Pico"
}


def _get_sha(api_base, path):
    """Get file SHA for updates."""
    url = api_base + path
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


def _push_file(api_base, path, content, message):
    """Push content to a GitHub repo."""
    url = api_base + path
    sha = _get_sha(api_base, path)

    b64 = ubinascii.b2a_base64(content.encode() if isinstance(content, str) else content).decode().strip()
    payload = {"message": message, "content": b64}
    if sha:
        payload["sha"] = sha

    res = None
    try:
        with net_lock:
            res = urequests.put(url, json=payload, headers=HEADERS, timeout=20)
        status = res.status_code
        return 200 <= status <= 201
    except Exception as e:
        print(f"GH Push ({path}): {e}")
        return False
    finally:
        if res:
            res.close()
        gc.collect()


# ============================================================
# PRIVATE REPO — Automated nightly backups (disaster recovery)
# ============================================================

def backup_to_private():
    """Backup internal state and skills to the private repo."""
    print("[BACKUP] Starting private repo sync...")
    count = 0

    # Backup soul.json
    try:
        with open("soul.json", "r") as f:
            content = f.read()
        if _push_file(PRIVATE_API, "backups/soul.json", content, "Backup: soul.json"):
            count += 1
    except OSError:
        pass

    # Backup stats.json
    try:
        with open("stats.json", "r") as f:
            content = f.read()
        if _push_file(PRIVATE_API, "backups/stats.json", content, "Backup: stats.json"):
            count += 1
    except OSError:
        pass

    # Backup memory.txt (Hippocampus)
    try:
        with open("memory.txt", "r") as f:
            content = f.read()
        if _push_file(PRIVATE_API, "backups/memory.txt", content, "Backup: memory"):
            count += 1
    except OSError:
        pass

    # Backup memory_index.json (tagged memories and lessons)
    try:
        with open("memory_index.json", "r") as f:
            content = f.read()
        if _push_file(PRIVATE_API, "backups/memory_index.json", content, "Backup: memory index"):
            count += 1
    except OSError:
        pass

    # Backup skills
    try:
        files = uos.listdir("skills")
        for filename in files:
            if filename.endswith(".py"):
                with open(f"skills/{filename}", "r") as f:
                    content = f.read()
                if _push_file(PRIVATE_API, f"backups/skills/{filename}", content, f"Backup: {filename}"):
                    count += 1
                gc.collect()
    except OSError:
        pass

    print(f"[BACKUP] Synced {count} files to private repo")
    return count


# ============================================================
# PUBLIC REPO — Portfolio, blog, skill sharing, projects
# ============================================================

def publish_blog_post(title, markdown_content, category="update"):
    """Publish a blog post to the public GitHub Pages repo."""
    import time
    t = time.localtime()
    date_str = f"{t[0]}-{t[1]:02d}-{t[2]:02d}"

    # Sanitize title for filename
    slug = title.lower().replace(" ", "-")
    for ch in "!@#$%^&*()[]{}|\\;:'\",.<>?/`~":
        slug = slug.replace(ch, "")
    slug = slug[:50]

    filepath = f"_posts/{date_str}-{slug}.md"

    # Add Jekyll front matter
    full_content = (
        f"---\n"
        f"title: \"{title}\"\n"
        f"date: {date_str}\n"
        f"layout: post\n"
        f"category: {category}\n"
        f"---\n\n"
        f"{markdown_content}"
    )

    if _push_file(PUBLIC_API, filepath, full_content, f"Blog ({category}): {title[:50]}"):
        print(f"[BLOG] Published: {filepath}")
        return f"Published: {filepath}"

    print(f"[BLOG] Publish failed: {filepath}")
    return f"Publish failed: {filepath}"


def publish_skill(filename):
    """Publish a local skill to the public repo for others to use."""
    if not filename:
        return "Error: filename required."
    if not filename.endswith(".py"):
        filename += ".py"

    filepath = f"skills/{filename}"
    try:
        with open(filepath, "r") as f:
            content = f.read()
    except OSError:
        return f"Skill not found locally: {filepath}"

    if _push_file(PUBLIC_API, f"skills/{filename}", content, f"Publish skill: {filename}"):
        print(f"[PUBLISH] Skill shared: {filename}")
        return f"Published to public repo: skills/{filename}"

    return f"Publish failed: {filename}"


def publish_project_file(project_name, filename, content):
    """Create or update a file in a named project on the public repo."""
    if not project_name or not filename or not content:
        return "Error: project_name, filename, and content are all required."

    # Sanitize project name
    safe_name = project_name.lower().replace(" ", "-")
    for ch in "!@#$%^&*()[]{}|\\;:'\",.<>?/`~":
        safe_name = safe_name.replace(ch, "")

    path = f"projects/{safe_name}/{filename}"

    if _push_file(PUBLIC_API, path, content, f"Project {safe_name}: {filename}"):
        print(f"[PUBLISH] Project file: {path}")
        return f"Published: {path}"

    return f"Publish failed: {path}"
