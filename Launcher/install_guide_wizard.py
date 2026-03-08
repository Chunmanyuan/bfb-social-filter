from __future__ import annotations

import re
import shutil
import subprocess
import sys
import threading
import webbrowser
import ctypes
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import messagebox


CHROME_DOWNLOAD_URL = "https://www.google.com/chrome/"
TUNA_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"


@dataclass
class PythonRuntime:
    launcher: str  # "py" or "exe"
    command_prefix: list[str]
    version: tuple[int, int, int]
    version_text: str
    executable: str


def set_high_dpi_awareness() -> None:
    if sys.platform != "win32":
        return

    try:
        # Windows 10+ per-monitor-v2 DPI awareness
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass

    try:
        # Windows 8.1 fallback
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    try:
        # Legacy fallback
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def decode_output(raw: bytes) -> str:
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_version(text: str) -> tuple[int, int, int] | None:
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def run_probe(prefix: list[str]) -> PythonRuntime | None:
    try:
        proc = subprocess.run(
            [*prefix, "-c", "import sys;print(sys.version.split()[0]);print(sys.executable)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except FileNotFoundError:
        return None
    except Exception:
        return None

    if proc.returncode != 0:
        return None

    out = decode_output(proc.stdout).strip().splitlines()
    if len(out) < 2:
        return None

    version_text = out[0].strip()
    exe = out[1].strip()
    parsed = parse_version(version_text)
    if not parsed:
        return None

    launcher = "py" if prefix and prefix[0].lower() == "py" else "exe"
    return PythonRuntime(
        launcher=launcher,
        command_prefix=prefix,
        version=parsed,
        version_text=version_text,
        executable=exe,
    )


def detect_python_runtime() -> PythonRuntime | None:
    probes = [
        ["py", "-3"],
        ["python"],
        ["python3"],
    ]
    for p in probes:
        runtime = run_probe(p)
        if runtime:
            return runtime
    return None


def find_chrome() -> str | None:
    import os

    candidates = [
        Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LocalAppData", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    found = shutil.which("chrome")
    return found


def is_project_root(path: Path) -> bool:
    return (
        (path / "requirements_all.txt").exists()
        and (path / "MediaCrawler").is_dir()
        and (path / "Launcher").is_dir()
    )


class InstallGuideApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("安装引导")
        self._apply_ui_scaling()
        self._apply_window_size()
        self.root.minsize(720, 520)

        self.project_root = self._locate_project_root()
        self.required_version = self._read_required_python_version()
        self.runtime: PythonRuntime | None = None

        self.stage = "ready"
        self.is_running = False
        self.venv_python = self.project_root / "venv" / "Scripts" / "python.exe"

        self._build_ui()

    def _apply_ui_scaling(self) -> None:
        try:
            dpi = float(self.root.winfo_fpixels("1i"))
            scale = dpi / 96.0
            # Keep scaling conservative to avoid layout overflow on some screens.
            if scale < 1.0:
                scale = 1.0
            if scale > 1.35:
                scale = 1.35
            if 1.0 <= scale <= 1.35:
                self.root.tk.call("tk", "scaling", scale)
        except Exception:
            pass

    def _apply_window_size(self) -> None:
        screen_w = max(800, int(self.root.winfo_screenwidth()))
        screen_h = max(600, int(self.root.winfo_screenheight()))

        width = min(980, screen_w - 120)
        height = min(700, screen_h - 140)
        width = max(820, width)
        height = max(560, height)

        x = max(20, (screen_w - width) // 2)
        y = max(20, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _base_dirs_for_search(self) -> list[Path]:
        bases: list[Path] = []

        # In PyInstaller onefile mode, __file__ points to temp extraction dir.
        # Use exe dir first so project-relative lookup remains stable after distribution.
        if getattr(sys, "frozen", False):
            bases.append(Path(sys.executable).resolve().parent)

        bases.append(Path.cwd())
        bases.append(Path(__file__).resolve().parent)

        out: list[Path] = []
        seen = set()
        for b in bases:
            key = str(b)
            if key in seen:
                continue
            seen.add(key)
            out.append(b)
        return out

    def _locate_project_root(self) -> Path:
        for base in self._base_dirs_for_search():
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
            for _ in range(10):
                if is_project_root(cursor):
                    return cursor
                if cursor.parent == cursor:
                    break
                cursor = cursor.parent
        raise RuntimeError("未找到项目根目录（requirements_all.txt / MediaCrawler）。")

    def _read_required_python_version(self) -> tuple[int, int, int]:
        text = (self.project_root / ".python-version").read_text(encoding="utf-8").strip()
        parsed = parse_version(text)
        if not parsed:
            raise RuntimeError(f".python-version 格式无效: {text}")
        return parsed

    def _build_ui(self) -> None:
        top = tk.Frame(self.root, padx=16, pady=12)
        top.pack(fill="x")

        self.title_label = tk.Label(
            top,
            text="社媒内容提取系统 - 安装引导",
            font=("Microsoft YaHei UI", 16, "bold"),
            anchor="w",
        )
        self.title_label.pack(fill="x")

        self.desc_label = tk.Label(
            top,
            text="将执行：环境安装/修复 -> 平台登录引导",
            font=("Microsoft YaHei UI", 10),
            fg="#444",
            anchor="w",
        )
        self.desc_label.pack(fill="x", pady=(6, 0))

        body = tk.Frame(self.root, padx=16, pady=8)
        body.pack(fill="both", expand=True)

        self.log_text = tk.Text(body, wrap="word", font=("Consolas", 10))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

        bottom = tk.Frame(self.root, padx=16, pady=12)
        bottom.pack(fill="x")

        self.primary_btn = tk.Button(
            bottom,
            text="开始安装",
            width=22,
            command=self.on_primary_click,
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.primary_btn.pack(side="left")

        self.exit_btn = tk.Button(
            bottom,
            text="退出",
            width=12,
            command=self.root.destroy,
            font=("Microsoft YaHei UI", 10),
        )
        self.exit_btn.pack(side="right")

        self.append_log("准备就绪。点击“开始安装”。")

    def append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def set_stage(self, stage: str, button_text: str, description: str) -> None:
        self.stage = stage
        self.primary_btn.configure(text=button_text, state="normal")
        self.desc_label.configure(text=description)

    def choose_dialog(self, title: str, message: str, options: list[tuple[str, str]]) -> str:
        result = {"value": ""}
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("520x240")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        label = tk.Label(
            win,
            text=message,
            justify="left",
            wraplength=480,
            font=("Microsoft YaHei UI", 10),
            padx=16,
            pady=16,
            anchor="w",
        )
        label.pack(fill="both", expand=True)

        btn_row = tk.Frame(win, padx=12, pady=12)
        btn_row.pack(fill="x")

        def pick(val: str) -> None:
            result["value"] = val
            win.destroy()

        for value, text in options:
            tk.Button(
                btn_row,
                text=text,
                command=lambda v=value: pick(v),
                width=20,
                font=("Microsoft YaHei UI", 9),
            ).pack(side="left", padx=4)

        self.root.wait_window(win)
        return result["value"]

    def show_copyable_command(self, command: str) -> None:
        win = tk.Toplevel(self.root)
        win.title("Python 安装命令")
        win.geometry("700x260")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        tk.Label(
            win,
            text="请复制下面命令，在命令行中执行安装；安装完成后重新打开安装引导。",
            font=("Microsoft YaHei UI", 10),
            padx=12,
            pady=12,
            anchor="w",
            justify="left",
        ).pack(fill="x")

        text = tk.Text(win, height=5, font=("Consolas", 11))
        text.pack(fill="x", padx=12)
        text.insert("1.0", command)
        text.configure(state="disabled")

        row = tk.Frame(win, padx=12, pady=12)
        row.pack(fill="x")

        def copy_cmd() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(command)
            messagebox.showinfo("提示", "安装命令已复制到剪贴板。")

        tk.Button(row, text="复制命令", width=14, command=copy_cmd).pack(side="left")
        tk.Button(row, text="关闭", width=14, command=win.destroy).pack(side="right")

        self.root.wait_window(win)

    def required_python_install_command(self) -> str:
        major, minor, _ = self.required_version
        return f"winget install -e --id Python.Python.{major}.{minor}"

    def ensure_chrome(self) -> bool:
        chrome = find_chrome()
        if chrome:
            self.append_log(f"[检查通过] Chrome: {chrome}")
            return True

        self.append_log("[检查失败] 未检测到 Chrome。")
        choice = self.choose_dialog(
            "缺少 Chrome",
            "未检测到 Google Chrome。\n\n请选择：\n- 打开 Chrome 官方下载页\n- 退出安装流程",
            [("open", "打开Chrome官网"), ("exit", "退出安装")],
        )
        if choice == "open":
            webbrowser.open(CHROME_DOWNLOAD_URL)
            messagebox.showinfo("提示", "已打开 Chrome 官网。安装完成后请重新运行安装引导。")
        return False

    def ensure_python_runtime(self) -> PythonRuntime | None:
        runtime = detect_python_runtime()
        required = self.required_version
        required_text = ".".join(str(x) for x in required)

        if runtime is None:
            self.append_log("[检查失败] 未检测到 Python。")
            choice = self.choose_dialog(
                "缺少 Python",
                f"未检测到 Python（需要 {required_text}）。\n\n请选择：\n- 查看安装命令\n- 退出安装流程",
                [("command", "查看安装命令"), ("exit", "退出安装")],
            )
            if choice == "command":
                self.show_copyable_command(self.required_python_install_command())
            return None

        self.append_log(f"[检测到] Python {runtime.version_text} ({runtime.executable})")
        if runtime.version == required:
            self.append_log("[检查通过] Python 版本符合要求。")
            return runtime

        choice = self.choose_dialog(
            "Python 版本不符合要求",
            (
                f"检测到 Python {runtime.version_text}，但推荐版本为 {required_text}。\n\n"
                "请选择：\n"
                "- 退出安装流程\n"
                "- 查看安装命令（复制后手动安装）\n"
                "- 仍继续安装（可能不兼容）"
            ),
            [
                ("exit", "退出安装"),
                ("command", "查看安装命令"),
                ("continue", "仍继续安装"),
            ],
        )
        if choice == "command":
            self.show_copyable_command(self.required_python_install_command())
            return None
        if choice == "continue":
            self.append_log("[警告] 用户选择使用非推荐 Python 版本继续安装。")
            return runtime
        return None

    def run_cmd_stream(self, cmd: list[str], cwd: Path, title: str) -> int:
        self.append_log(f"[执行] {title}")
        self.append_log("  " + " ".join(cmd))
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert proc.stdout is not None
        while True:
            raw = proc.stdout.readline()
            if not raw and proc.poll() is not None:
                break
            if raw:
                line = decode_output(raw).rstrip("\r\n")
                if line:
                    self.append_log(line)
        return proc.wait()

    def on_primary_click(self) -> None:
        if self.stage == "ready":
            self.start_install_flow()
        elif self.stage == "login_prompt":
            self.open_login_windows()
        elif self.stage == "login_wait":
            self.finish_install()
        elif self.stage == "done":
            self.root.destroy()

    def start_install_flow(self) -> None:
        if self.is_running:
            return

        self.primary_btn.configure(state="disabled")
        self.exit_btn.configure(state="disabled")
        self.desc_label.configure(text="正在准备安装环境，请勿关闭...")
        self.append_log("正在准备安装环境，请勿关闭。")
        self.root.update_idletasks()

        if not self.ensure_chrome():
            self.primary_btn.configure(state="normal")
            self.exit_btn.configure(state="normal")
            self.desc_label.configure(text="将执行：环境安装/修复 -> 平台登录引导")
            return

        runtime = self.ensure_python_runtime()
        if runtime is None:
            self.primary_btn.configure(state="normal")
            self.exit_btn.configure(state="normal")
            self.desc_label.configure(text="将执行：环境安装/修复 -> 平台登录引导")
            return

        self.runtime = runtime
        self.desc_label.configure(text="正在执行环境安装/修复，请稍候...")
        self.is_running = True

        t = threading.Thread(target=self._install_worker, daemon=True)
        t.start()

    def _build_create_venv_cmd(self) -> list[str]:
        assert self.runtime is not None
        if self.runtime.launcher == "py":
            return [*self.runtime.command_prefix, "-m", "venv", "venv", "--clear"]
        return [self.runtime.executable, "-m", "venv", "venv", "--clear"]

    def _install_worker(self) -> None:
        try:
            self.root.after(0, lambda: self.append_log("========== 环境安装/修复 =========="))
            venv_ok = self.venv_python.exists()
            if venv_ok:
                code = self.run_cmd_stream([str(self.venv_python), "--version"], self.project_root, "检查现有 venv")
                venv_ok = code == 0

            if not venv_ok:
                code = self.run_cmd_stream(self._build_create_venv_cmd(), self.project_root, "创建/重建 venv")
                if code != 0:
                    raise RuntimeError("创建虚拟环境失败。")

            code = self.run_cmd_stream(
                [str(self.venv_python), "-m", "pip", "install", "-i", TUNA_INDEX, "--upgrade", "pip"],
                self.project_root,
                "升级 pip",
            )
            if code != 0:
                raise RuntimeError("升级 pip 失败。")

            code = self.run_cmd_stream(
                [str(self.venv_python), "-m", "pip", "install", "-i", TUNA_INDEX, "-r", "requirements_all.txt"],
                self.project_root,
                "安装/修复依赖",
            )
            if code != 0:
                raise RuntimeError("安装依赖失败。")

            code = self.run_cmd_stream(
                [str(self.venv_python), "-m", "pip", "check"],
                self.project_root,
                "依赖一致性检查",
            )
            if code != 0:
                raise RuntimeError("依赖检查失败，请重试。")

            self.root.after(0, self.enter_login_stage)
        except Exception as exc:
            self.root.after(0, lambda: self.install_failed(str(exc)))

    def install_failed(self, reason: str) -> None:
        self.is_running = False
        self.exit_btn.configure(state="normal")
        self.primary_btn.configure(state="normal")
        self.append_log(f"[失败] {reason}")
        self.desc_label.configure(text="安装失败，请修复后重试。")
        messagebox.showerror("安装失败", reason)

    def enter_login_stage(self) -> None:
        self.is_running = False
        self.exit_btn.configure(state="normal")
        self.append_log("========== 环境安装完成 ==========")
        self.append_log("下一步将打开小红书和B站登录窗口。")
        self.append_log("请在两个窗口都登录成功后，保持页面打开至少10秒，再关闭窗口。")
        self.set_stage(
            "login_prompt",
            "完成安装并打开登录窗口",
            "环境安装完成。点击按钮进入平台登录阶段。",
        )

    def open_login_windows(self) -> None:
        helper = self.project_root / "MediaCrawler" / "login_browser_helper.py"
        if not helper.exists():
            messagebox.showerror("错误", f"未找到登录脚本：{helper}")
            return

        self.primary_btn.configure(state="disabled")
        code = self.run_cmd_stream(
            [str(self.venv_python), str(helper)],
            self.project_root,
            "打开登录窗口（小红书 + B站）",
        )
        if code != 0:
            self.primary_btn.configure(state="normal")
            messagebox.showerror("错误", "打开登录窗口失败，请检查 Chrome 是否可用。")
            return

        self.append_log("登录窗口已打开。")
        self.append_log("请完成登录后，保持页面打开至少10秒，再关闭窗口。")
        self.set_stage(
            "login_wait",
            "我已完成登录",
            "登录完成后点击“我已完成登录”。（务必保持页面打开10秒后再关闭）",
        )

    def finish_install(self) -> None:
        self.append_log("========== 安装引导完成 ==========")
        self.append_log("后续请运行第2步或启动器进入系统。")
        self.set_stage("done", "完成并退出", "安装与登录引导已完成。")
        messagebox.showinfo("完成", "安装引导已完成。")


def main() -> int:
    set_high_dpi_awareness()
    root = tk.Tk()
    try:
        InstallGuideApp(root)
    except Exception as exc:
        messagebox.showerror("启动失败", str(exc))
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
