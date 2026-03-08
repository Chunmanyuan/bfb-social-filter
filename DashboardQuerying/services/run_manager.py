# -*- coding: utf-8 -*-
import asyncio
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class DashboardRunManager:
    """Manage dashboard runtime config, one-off runs, and lightweight daily scheduling."""

    DEFAULT_CONFIG: Dict[str, Any] = {
        "keywords": "",
        "hours_back": 24,
        "max_notes": 30,
        "max_video_size_mb": 100,
        "num_frames": 40,
        "dedup_threshold": 5,
        "ocr_device": "auto",
        "ocr_workers": 1,
        "headless": True,
        "daily_enabled": False,
        "daily_time": "09:00",
        "last_daily_run_date": "",
    }

    def __init__(self):
        self._lock = asyncio.Lock()
        self.process: Optional[subprocess.Popen] = None
        self.status = "idle"
        self.started_at: Optional[datetime] = None
        self.ended_at: Optional[datetime] = None
        self.last_exit_code: Optional[int] = None
        self.last_task_id: Optional[str] = None
        self.last_trigger: Optional[str] = None
        self._read_task: Optional[asyncio.Task] = None
        self._scheduler_task: Optional[asyncio.Task] = None
        self._stop_requested = False
        self._logs = []

        self.module_root = Path(__file__).resolve().parents[1]
        self.workspace_root = self.module_root.parent
        self.config_path = self.module_root / "runtime_config.json"

    def _append_log(self, level: str, message: str):
        self._logs.append(
            {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "level": level,
                "message": message,
            }
        )
        if len(self._logs) > 400:
            self._logs = self._logs[-400:]

    @staticmethod
    def _decode_output(raw: Any) -> str:
        if raw is None:
            return ""
        if isinstance(raw, str):
            return raw
        if not isinstance(raw, (bytes, bytearray)):
            return str(raw)

        for encoding in ("utf-8", "gb18030"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue

        return raw.decode("utf-8", errors="replace")

    def get_logs(self, limit: int = 100):
        if limit <= 0:
            return self._logs
        return self._logs[-limit:]

    def load_config(self) -> Dict[str, Any]:
        config = dict(self.DEFAULT_CONFIG)
        if self.config_path.exists():
            try:
                import json

                raw = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    config.update(raw)
            except Exception:
                self._append_log("warning", "Failed to parse runtime config, using defaults.")
        return config

    def save_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(self.DEFAULT_CONFIG)
        merged.update(config or {})

        import json

        self.config_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return merged

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "last_exit_code": self.last_exit_code,
            "last_task_id": self.last_task_id,
            "last_trigger": self.last_trigger,
            "logs": self.get_logs(120),
        }

    def _build_pipeline_cmd(self, cfg: Dict[str, Any]) -> list:
        if sys.platform == "win32":
            python_bin = self.workspace_root / "venv" / "Scripts" / "python.exe"
        else:
            python_bin = self.workspace_root / "venv" / "bin" / "python"
        if not python_bin.exists():
            python_bin = Path(sys.executable)

        script_path = self.workspace_root / "测试模块连贯运行.py"
        cmd = [
            str(python_bin),
            str(script_path),
            "--keywords",
            str(cfg.get("keywords", "")),
            "--hours-back",
            str(cfg.get("hours_back", 24)),
            "--max-notes",
            str(cfg.get("max_notes", 30)),
            "--max-video-size-mb",
            str(cfg.get("max_video_size_mb", 100)),
            "--num-frames",
            str(cfg.get("num_frames", 40)),
            "--threshold",
            str(cfg.get("dedup_threshold", 5)),
            "--ocr-device",
            str(cfg.get("ocr_device", "auto")),
            "--ocr-workers",
            str(cfg.get("ocr_workers", 1)),
            "--headless",
            "true" if bool(cfg.get("headless", True)) else "false",
        ]

        if bool(cfg.get("enable_mkldnn", False)):
            cmd.append("--enable-mkldnn")

        return cmd

    async def start_once(self, overrides: Optional[Dict[str, Any]] = None, trigger: str = "manual") -> bool:
        async with self._lock:
            if self.process and self.process.poll() is None:
                return False

            cfg = self.load_config()
            if overrides:
                cfg.update(overrides)

            cmd = self._build_pipeline_cmd(cfg)
            self._append_log("info", f"Starting pipeline ({trigger}): {' '.join(cmd)}")

            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=False,
                    bufsize=0,
                    cwd=str(self.workspace_root),
                    env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
                )
                self.status = "running"
                self.started_at = datetime.now()
                self.ended_at = None
                self.last_exit_code = None
                self.last_trigger = trigger
                self._stop_requested = False
                self._read_task = asyncio.create_task(self._read_output())
                return True
            except Exception as exc:
                self.status = "error"
                self.ended_at = datetime.now()
                self._append_log("error", f"Failed to start pipeline: {exc}")
                return False

    async def stop_once(self) -> Dict[str, Any]:
        async with self._lock:
            if not self.process or self.process.poll() is not None:
                return {"stopped": False, "message": "No pipeline run is currently in progress"}

            process = self.process
            self._stop_requested = True
            self.status = "stopping"
            self._append_log("warning", f"Manual stop requested for PID {process.pid}.")

        loop = asyncio.get_running_loop()

        def _wait_for_exit(timeout: float) -> bool:
            try:
                process.wait(timeout=timeout)
                return True
            except subprocess.TimeoutExpired:
                return False

        if sys.platform == "win32":
            self._append_log("warning", "Stopping pipeline process tree with taskkill.")
            await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                ),
            )
            await loop.run_in_executor(None, _wait_for_exit, 5.0)
        else:
            try:
                process.terminate()
                self._append_log("warning", "Terminate signal sent to pipeline process.")
            except Exception as exc:
                self._append_log("warning", f"Failed to terminate pipeline process gracefully: {exc}")

            exited = await loop.run_in_executor(None, _wait_for_exit, 5.0)
            if not exited:
                self._append_log("warning", "Terminate timed out. Killing pipeline process.")
                try:
                    process.kill()
                except Exception as exc:
                    self._append_log("warning", f"Failed to kill pipeline process: {exc}")
                await loop.run_in_executor(None, _wait_for_exit, 5.0)

        if self._read_task and not self._read_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self._read_task), timeout=5.0)
            except asyncio.TimeoutError:
                self._append_log("warning", "Timed out while waiting for pipeline log reader to stop.")

        return {"stopped": True, "message": "Pipeline stop requested"}

    async def _read_output(self):
        loop = asyncio.get_event_loop()
        task_pattern = re.compile(r"Task ID:\s*([A-Za-z0-9\-_]+)")

        try:
            while self.process and self.process.poll() is None:
                raw_line = await loop.run_in_executor(None, self.process.stdout.readline)
                if not raw_line:
                    continue
                line = self._decode_output(raw_line)
                clean = line.rstrip("\r\n")
                if clean:
                    match = task_pattern.search(clean)
                    if match:
                        self.last_task_id = match.group(1)
                    self._append_log("info", clean)

            if self.process and self.process.stdout:
                remaining_raw = await loop.run_in_executor(None, self.process.stdout.read)
                if remaining_raw:
                    remaining = self._decode_output(remaining_raw)
                    for line in remaining.splitlines():
                        clean = line.strip()
                        if not clean:
                            continue
                        match = task_pattern.search(clean)
                        if match:
                            self.last_task_id = match.group(1)
                        self._append_log("info", clean)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            self._append_log("error", f"Error while reading pipeline output: {exc}")
        finally:
            self.ended_at = datetime.now()
            if self.process:
                self.last_exit_code = self.process.returncode
                if self.process.stdout:
                    self.process.stdout.close()

            if self._stop_requested:
                self.status = "idle"
                self._append_log("warning", f"Pipeline stopped by user. Exit code: {self.last_exit_code}")
            elif self.last_exit_code == 0:
                self.status = "idle"
                self._append_log("success", "Pipeline finished successfully.")
            else:
                self.status = "error"
                self._append_log("warning", f"Pipeline finished with exit code: {self.last_exit_code}")

            self.process = None
            self._read_task = None

    async def scheduler_loop(self):
        self._append_log("info", "Dashboard daily scheduler loop started.")
        while True:
            try:
                cfg = self.load_config()
                if bool(cfg.get("daily_enabled", False)):
                    daily_time = str(cfg.get("daily_time", "09:00")).strip()
                    now = datetime.now()
                    now_hm = now.strftime("%H:%M")
                    today = now.strftime("%Y-%m-%d")
                    last_daily = str(cfg.get("last_daily_run_date", "")).strip()
                    if daily_time == now_hm and today != last_daily:
                        started = await self.start_once(trigger="daily")
                        if started:
                            cfg["last_daily_run_date"] = today
                            self.save_config(cfg)
                            self._append_log("info", f"Daily schedule triggered at {daily_time}.")
                await asyncio.sleep(20)
            except Exception as exc:
                self._append_log("error", f"Scheduler loop error: {exc}")
                await asyncio.sleep(20)

    async def start_scheduler(self):
        if self._scheduler_task is None or self._scheduler_task.done():
            self._scheduler_task = asyncio.create_task(self.scheduler_loop())

    async def stop_scheduler(self):
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        self._scheduler_task = None


run_manager = DashboardRunManager()
