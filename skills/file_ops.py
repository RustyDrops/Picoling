# skills/file_ops.py — File read/write with safety
import uos


def tool_read_file(filepath, max_lines=50, start_line=0):
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


def tool_write_file(filepath, content, mode="w"):
    """Write content to a file with syntax checking for .py files."""
    if filepath.endswith('.py'):
        try:
            compile(content, '<syntax_check>', 'exec')
        except SyntaxError as e:
            return f"SyntaxError: {e}"

    try:
        with open(filepath, mode) as f:
            f.write(content)
        return f"Written: {filepath}"
    except OSError as e:
        return f"Write error: {e}"


def tool_list_dir(path="."):
    """List files and directories at the given path."""
    try:
        items = uos.listdir(path)
        return "\n".join(items) if items else "(empty)"
    except OSError:
        return f"Path not found: {path}"
