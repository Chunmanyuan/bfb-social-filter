from __future__ import annotations

import atexit
import ctypes
import msvcrt
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw
from pystray import MenuItem as item


SERVICE_URL = "http://127.0.0.1:8090/"
HEALTH_URL = f"{SERVICE_URL}api/health"
WINDOW_TITLE = "社媒筛选器"


class LauncherState:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.service_proc: subprocess.Popen | None = None
        self.started_by_launcher = False
        self.lock_handle = None
        self.lock_path = project_root / ".dashboard_launcher.lock"

    @property
    def python_bin(self) -> Path:
        return self.project_root / "venv" / "Scripts" / "python.exe"

    @property
    def pythonw_bin(self) -> Path:
        return self.project_root / "venv" / "Scripts" / "pythonw.exe"

    @property
    def app_file(self) -> Path:
        return self.project_root / "DashboardQuerying" / "app.py"


def show_error(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, WINDOW_TITLE, 0x10)
    except Exception:
        print(message)


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def is_project_root(path: Path) -> bool:
    return (
        (path / "DashboardQuerying" / "app.py").exists()
        and (path / "Launcher").is_dir()
        and (path / "requirements_all.txt").exists()
    )


def locate_project_root() -> Path | None:
    base = get_base_dir()

    # Support shipping the EXE one level above the actual project folder.
    candidates = [base]
    try:
        child_dirs = sorted([p for p in base.iterdir() if p.is_dir()])
        candidates.extend(child_dirs)
    except OSError:
        pass

    for candidate in candidates:
        if is_project_root(candidate):
            return candidate

    cursor = base
    for _ in range(8):
        if is_project_root(cursor):
            return cursor
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    return None


def is_service_running(timeout: float = 0.6) -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def open_dashboard() -> None:
    webbrowser.open(SERVICE_URL)


def acquire_lock(state: LauncherState) -> bool:
    state.lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(state.lock_path, "w", encoding="utf-8")
    handle.write("1")
    handle.flush()
    handle.seek(0)

    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return False

    state.lock_handle = handle
    return True


def release_lock(state: LauncherState) -> None:
    handle = state.lock_handle
    if handle is None:
        return

    try:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    finally:
        handle.close()
        state.lock_handle = None


def stop_service(state: LauncherState) -> None:
    proc = state.service_proc
    if proc is None:
        return

    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

    state.service_proc = None


def start_service(state: LauncherState) -> bool:
    if is_service_running():
        return True

    python_launcher = state.pythonw_bin if state.pythonw_bin.exists() else state.python_bin

    if not python_launcher.exists():
        show_error(
            "venv\\Scripts\\pythonw.exe / python.exe not found.\n"
            "Please run the environment setup first."
        )
        return False

    if not state.app_file.exists():
        show_error("DashboardQuerying\\app.py not found.")
        return False

    flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    proc = subprocess.Popen(
        [str(python_launcher), str(state.app_file)],
        cwd=str(state.project_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        startupinfo=startupinfo,
    )
    state.service_proc = proc
    state.started_by_launcher = True

    for _ in range(40):
        if is_service_running():
            return True
        if proc.poll() is not None:
            return False
        time.sleep(0.5)

    return False


def create_icon_image() -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((9, 6, 33, 30), fill="#ff6fa6", outline="#d6387b", width=2)
    draw.ellipse((31, 6, 55, 30), fill="#ff6fa6", outline="#d6387b", width=2)
    draw.polygon([(10, 24), (32, 56), (54, 24)], fill="#ff6fa6", outline="#d6387b")
    draw.ellipse((17, 12, 29, 22), fill="#ffc2d8")
    return img


def run_tray(state: LauncherState) -> None:
    def on_open(icon, _item):
        open_dashboard()

    def on_exit(icon, _item):
        stop_service(state)
        icon.stop()

    menu = pystray.Menu(
        item("Open Dashboard", on_open, default=True),
        item("Exit", on_exit),
    )

    icon = pystray.Icon(
        "dashboard-launcher",
        create_icon_image(),
        WINDOW_TITLE,
        menu,
    )
    icon.run()


def main() -> int:
    project_root = locate_project_root()
    if project_root is None:
        show_error("Cannot find project root (DashboardQuerying/app.py).")
        return 1

    state = LauncherState(project_root)
    atexit.register(release_lock, state)

    if not acquire_lock(state):
        open_dashboard()
        return 0

    if not start_service(state):
        stop_service(state)
        show_error("Failed to start local dashboard service.")
        return 1

    open_dashboard()
    run_tray(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
