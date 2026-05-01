# skills/template_engine.py — Simple string template system for HTML generation
# Lightweight alternative to Jinja2 for MicroPython


def render(template, **kwargs):
    """Render a template string by replacing {{key}} with values.
    
    Example:
        render("Hello {{name}}!", name="World") -> "Hello World!"
    """
    result = template
    for key, value in kwargs.items():
        placeholder = "{{" + key + "}}"
        result = result.replace(placeholder, str(value))
    return result


# Pre-built HTML templates for blog pages
BLOG_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{title}} — Picoling</title>
<meta name="description" content="{{description}}">
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif;
       max-width: 700px; margin: 0 auto; padding: 20px;
       color: #e0e0e0; background: #1a1a2e; line-height: 1.6; }
h1 { color: #64ffda; }
a { color: #82b1ff; }
.meta { color: #888; font-size: 0.9em; }
.nav { padding: 10px 0; border-bottom: 1px solid #333; margin-bottom: 20px; }
.nav a { margin-right: 15px; text-decoration: none; }
</style>
</head>
<body>
<div class="nav">
<a href="/">Home</a> <a href="/about">About</a>
</div>
<article>
<h1>{{title}}</h1>
<p class="meta">{{date}} — Picoling</p>
{{content}}
</article>
<footer><p>Powered by Raspberry Pi Pico 2W & Gemini AI</p></footer>
</body>
</html>"""


def render_blog_post(title, date, content, description=""):
    """Render a complete blog post HTML page."""
    if not description:
        # Auto-generate description from first 150 chars of content
        description = content[:150].replace("\n", " ").replace('"', "'")
    return render(BLOG_TEMPLATE,
                  title=title, date=date,
                  content=content, description=description)
