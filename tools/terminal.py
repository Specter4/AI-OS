"""Controlled terminal/process execution for AI-OS.

The direct process API never invokes a shell. The shell API invokes one of a
small set of explicitly selected system shells, and is intended to be
registered at the destructive permission tier.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from core.logger import log


_MAX_TIMEOUT_SECONDS = 300.0
_MAX_OUTPUT_CHARS = 100_000
_MAX_ARGUMENTS = 128
_MAX_ARGUMENT_CHARS = 32_000


class _BoundedCapture:
    """Drain a pipe continuously while retaining only a bounded byte prefix."""

    def __init__(self, stream: Any, max_bytes: int) -> None:
        self.stream = stream
        self.max_bytes = max_bytes
        self.parts: list[bytes] = []
        self.size = 0
        self.truncated = False

    def drain(self) -> None:
        while True:
            chunk = self.stream.read(8192)
            if not chunk:
                break
            remaining = self.max_bytes - self.size
            if remaining > 0:
                kept = chunk[:remaining]
                self.parts.append(kept)
                self.size += len(kept)
            if len(chunk) > max(remaining, 0):
                self.truncated = True

    def text(self, max_chars: int) -> tuple[str, bool]:
        value = b"".join(self.parts).decode("utf-8", errors="replace")
        truncated = self.truncated or len(value) > max_chars
        return value[:max_chars], truncated


class Terminal:
    """One-shot process and shell execution with bounded runtime and output."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def _validate_timeout(timeout: float) -> float:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise TypeError("timeout must be a number of seconds")
        value = float(timeout)
        if not 0.1 <= value <= _MAX_TIMEOUT_SECONDS:
            raise ValueError(f"timeout must be between 0.1 and {_MAX_TIMEOUT_SECONDS:g} seconds")
        return value

    @staticmethod
    def _validate_output_limit(max_output_chars: int) -> int:
        if isinstance(max_output_chars, bool) or not isinstance(max_output_chars, int):
            raise TypeError("max_output_chars must be an integer")
        if not 1 <= max_output_chars <= _MAX_OUTPUT_CHARS:
            raise ValueError(f"max_output_chars must be between 1 and {_MAX_OUTPUT_CHARS}")
        return max_output_chars

    @staticmethod
    def _validate_cwd(cwd: str | Path | None) -> str | None:
        if cwd is None:
            return None
        if not isinstance(cwd, (str, Path)) or not str(cwd).strip() or "\x00" in str(cwd):
            raise ValueError("cwd must be a non-empty directory path")
        target = Path(cwd).expanduser().resolve()
        if not target.is_dir():
            raise NotADirectoryError(f"Working directory does not exist: {target}")
        return str(target)

    @staticmethod
    def _validate_command(command: list[str] | tuple[str, ...]) -> list[str]:
        if not isinstance(command, (list, tuple)):
            raise TypeError("command must be a list or tuple of strings; shell text belongs in run_shell")
        if not command or len(command) > _MAX_ARGUMENTS:
            raise ValueError(f"command must contain between 1 and {_MAX_ARGUMENTS} items")
        normalized: list[str] = []
        total = 0
        for item in command:
            if not isinstance(item, str):
                raise TypeError("Every command item must be a string")
            if not item or "\x00" in item:
                raise ValueError("Command items must be non-empty and cannot contain NUL")
            total += len(item)
            normalized.append(item)
        if total > _MAX_ARGUMENT_CHARS:
            raise ValueError(f"Combined command length cannot exceed {_MAX_ARGUMENT_CHARS} characters")
        return normalized

    @staticmethod
    def _shell_command(command: str, shell: str | None) -> tuple[list[str], str]:
        if not isinstance(command, str):
            raise TypeError("command must be a string")
        if not command.strip() or "\x00" in command:
            raise ValueError("command must be non-empty and cannot contain NUL")
        if len(command) > _MAX_ARGUMENT_CHARS:
            raise ValueError(f"command cannot exceed {_MAX_ARGUMENT_CHARS} characters")

        if shell is not None and (not isinstance(shell, str) or not shell.strip()):
            raise ValueError("shell must be a non-empty string when specified")
        selected = (shell if shell is not None else ("powershell" if os.name == "nt" else "sh")).strip().lower()
        if selected == "powershell":
            executable = shutil.which("pwsh") or shutil.which("powershell")
            if not executable:
                raise FileNotFoundError("PowerShell (pwsh or powershell) was not found")
            return [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command], selected
        if selected == "cmd":
            if os.name != "nt":
                raise ValueError("cmd shell is available only on Windows")
            executable = shutil.which("cmd.exe") or os.environ.get("COMSPEC") or "cmd.exe"
            return [executable, "/d", "/s", "/c", command], selected
        if selected == "sh":
            executable = shutil.which("sh")
            if not executable:
                raise FileNotFoundError("POSIX sh was not found")
            return [executable, "-c", command], selected
        raise ValueError("shell must be one of: powershell, cmd, sh")

    @staticmethod
    def _stop_process_tree(process: subprocess.Popen[bytes]) -> None:
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    check=False,
                    shell=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
            if process.poll() is None:
                process.kill()
            return

        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            if process.poll() is None:
                process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                if process.poll() is None:
                    process.kill()

    def _execute(
        self,
        command: list[str],
        *,
        cwd: str | None,
        timeout: float,
        max_output_chars: int,
        shell_name: str | None,
    ) -> dict[str, Any]:
        timeout = self._validate_timeout(timeout)
        max_output_chars = self._validate_output_limit(max_output_chars)
        started = time.monotonic()
        popen_kwargs: dict[str, Any] = {
            "cwd": cwd,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "shell": False,
            "close_fds": True,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            popen_kwargs["start_new_session"] = True

        process = subprocess.Popen(command, **popen_kwargs)
        # UTF-8 can use up to four bytes per character. Keep a bounded prefix
        # of each stream while continuing to drain pipes to avoid deadlocks.
        max_bytes = max_output_chars * 4
        stdout_capture = _BoundedCapture(process.stdout, max_bytes)
        stderr_capture = _BoundedCapture(process.stderr, max_bytes)
        stdout_thread = threading.Thread(target=stdout_capture.drain, daemon=True)
        stderr_thread = threading.Thread(target=stderr_capture.drain, daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        timed_out = False
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._stop_process_tree(process)
            exit_code = process.poll()

        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        stdout, stdout_truncated = stdout_capture.text(max_output_chars)
        stderr, stderr_truncated = stderr_capture.text(max_output_chars)
        duration = round(time.monotonic() - started, 3)
        result = {
            "success": exit_code == 0 and not timed_out,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": timed_out,
            "duration_seconds": duration,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "working_directory": cwd or os.getcwd(),
            "execution_mode": "shell" if shell_name else "process",
        }
        if shell_name:
            result["shell"] = shell_name
        log(f"Terminal execution finished: mode={result['execution_mode']}, exit_code={exit_code}, timed_out={timed_out}, duration={duration}s")
        return result

    def run_program(
        self,
        command: list[str] | tuple[str, ...],
        cwd: str | Path | None = None,
        timeout: float = 30,
        max_output_chars: int = 20_000,
    ) -> dict[str, Any]:
        """Run a program using argv, never through a shell."""
        validated = self._validate_command(command)
        working_directory = self._validate_cwd(cwd)
        log("Terminal process execution started (argument-vector mode)")
        return self._execute(
            validated,
            cwd=working_directory,
            timeout=timeout,
            max_output_chars=max_output_chars,
            shell_name=None,
        )

    def run_shell(
        self,
        command: str,
        shell: str | None = None,
        cwd: str | Path | None = None,
        timeout: float = 30,
        max_output_chars: int = 20_000,
    ) -> dict[str, Any]:
        """Run explicit shell text; caller must register this as destructive."""
        argv, selected_shell = self._shell_command(command, shell)
        working_directory = self._validate_cwd(cwd)
        log(f"Terminal shell execution started: shell={selected_shell}")
        return self._execute(
            argv,
            cwd=working_directory,
            timeout=timeout,
            max_output_chars=max_output_chars,
            shell_name=selected_shell,
        )


terminal = Terminal()

__all__ = ["Terminal", "terminal"]
