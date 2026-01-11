import subprocess


def get_git_diff() -> str:
    """Get unstaged changes."""
    try:
        result = subprocess.run(
            ["git", "diff"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout or "(no unstaged changes)"
    except Exception as e:
        return f"Error: {e}"


def get_git_staged() -> str:
    """Get staged changes."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout or "(nothing staged)"
    except Exception as e:
        return f"Error: {e}"


def get_git_log(n: int = 5) -> str:
    """Get recent commit log."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{n}", "--oneline"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout or "(no commits)"
    except Exception as e:
        return f"Error: {e}"

