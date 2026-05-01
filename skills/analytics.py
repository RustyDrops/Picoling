# skills/analytics.py — GitHub repo stats for measuring growth
import urequests
import ujson
import gc
from secrets import GH_TOKEN, GH_PUBLIC_REPO, GH_PRIVATE_REPO
from locks import net_lock

HEADERS = {
    "Authorization": f"token {GH_TOKEN}",
    "User-Agent": "Picoling-Pico"
}


def tool_repo_stats(repo=None):
    """Fetch basic stats for a GitHub repo: stars, forks, watchers, open issues."""
    if repo is None:
        repo = GH_PUBLIC_REPO
    url = f"https://api.github.com/repos/{repo}"
    res = None
    try:
        with net_lock:
            res = urequests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return (
                f"Repo: {repo}\n"
                f"Stars: {data.get('stargazers_count', 0)}\n"
                f"Forks: {data.get('forks_count', 0)}\n"
                f"Watchers: {data.get('subscribers_count', 0)}\n"
                f"Open Issues: {data.get('open_issues_count', 0)}\n"
                f"Size: {data.get('size', 0)}KB"
            )
        return f"API error: HTTP {res.status_code}"
    except Exception as e:
        return f"Stats error: {e}"
    finally:
        if res:
            res.close()
        gc.collect()


def tool_pages_stats():
    """Fetch GitHub Pages build status."""
    url = f"https://api.github.com/repos/{GH_PUBLIC_REPO}/pages"
    res = None
    try:
        with net_lock:
            res = urequests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return (
                f"Pages URL: {data.get('html_url', 'N/A')}\n"
                f"Status: {data.get('status', 'unknown')}\n"
                f"HTTPS: {data.get('https_enforced', False)}"
            )
        return f"Pages API: HTTP {res.status_code}"
    except Exception as e:
        return f"Pages error: {e}"
    finally:
        if res:
            res.close()
        gc.collect()
