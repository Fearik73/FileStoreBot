import asyncio
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def _run(*cmd, timeout=300):
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=ROOT,
        env={**os.environ, "PYTHON": sys.executable},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "timed out"
    return proc.returncode, out.decode(errors="replace").strip()


async def update_from_upstream():
    if shutil.which("git") is None:
        return "error", "git is not installed on this machine."
    if not os.path.exists(os.path.join(ROOT, "update.sh")):
        return "error", "update.sh not found."

    rc, old = await _run("git", "rev-parse", "--short", "HEAD")
    old = old if rc == 0 else None

    rc, out = await _run("bash", "update.sh")
    if rc:
        return "error", out[-600:]

    _, new = await _run("git", "rev-parse", "--short", "HEAD")
    if old == new:
        return "uptodate", f"Already up to date ({new})."

    changes = ""
    if old:
        rc, log = await _run("git", "log", "--oneline", "-n", "5", f"{old}..{new}")
        if rc == 0 and log:
            changes = "\n" + log

    notes = "".join(
        "\n" + line for line in out.splitlines()
        if line.startswith(("⚠️", "✅ requirements"))
    )
    return "updated", f"{old or 'none'} → {new}{changes}{notes}"
  
