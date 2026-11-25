"""
Application Control for AI-OS.

Provides application discovery, safe process launching, window management,
and explicit process termination. The default backend uses standard-library
facilities and Windows APIs; no application is launched during import.
"""

from __future__ import annotations

import csv
import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Any


class WindowsApplicationDriver:
    """Windows-oriented application and window backend with portable fallbacks."""

    def __init__(self) -> None:
        self._user_start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        self._common_start_menu = Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


    def launch_application(self, application: str, args: list[str], working_directory: str | None = None) -> dict[str, Any]:
        """Launch an executable or a Start Menu shortcut without a command shell."""
        requested = Path(application).expanduser()
        if requested.suffix.casefold() == ".lnk" and requested.is_file():
            if args:
                raise ValueError("Arguments are not supported when launching a Windows shortcut")
            if os.name != "nt":
                raise RuntimeError("Windows shortcuts can only be launched on Windows")
            import ctypes
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "open", str(requested.resolve()), None, working_directory, 1
            )
            if result <= 32:
                raise OSError(f"Windows could not open shortcut (ShellExecute code {result})")
            return {"success": True, "application": str(requested.resolve()), "pid": None, "launch_method": "shortcut"}

        resolved = None
        if requested.exists():
            if not requested.is_file():
                raise IsADirectoryError(f"Application path is not a file: {application}")
            resolved = requested.resolve()
        else:
            resolved = shutil.which(application)

        if resolved is None:
            shortcuts = self.find_start_menu_shortcuts(application)
            if len(shortcuts) > 1:
                raise ValueError(f"Application name is ambiguous; use a shortcut path: {shortcuts[:10]}")
            if len(shortcuts) == 1:
                return self.launch_application(shortcuts[0], [], working_directory)
            raise FileNotFoundError(f"Application was not found by path, PATH lookup, or Start Menu name: {application}")

        executable = Path(resolved).resolve()
        suffix = executable.suffix.casefold()
        if os.name == "nt":
            if suffix not in {".exe", ".com"}:
                raise ValueError("Direct application launch accepts .exe or .com files; use a Start Menu shortcut for other app types")
        elif not os.access(executable, os.X_OK):
            raise PermissionError(f"Application is not executable: {executable}")

        process = subprocess.Popen(
            [str(executable), *args],
            cwd=working_directory,
            shell=False,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )
        return {
            "success": True,
            "application": str(executable),
            "pid": int(process.pid),
            "launch_method": "executable",
        }

    def _start_menu_shortcuts(self, limit: int = 1000) -> list[dict[str, Any]]:
        shortcuts: list[dict[str, Any]] = []
        seen: set[str] = set()
        for root in (self._user_start_menu, self._common_start_menu):
            if not root.is_dir():
                continue
            try:
                iterator = root.rglob("*.lnk")
                for shortcut in iterator:
                    resolved = str(shortcut.resolve()).casefold()
                    if resolved in seen:
                        continue
                    seen.add(resolved)
                    shortcuts.append({
                        "name": shortcut.stem,
                        "shortcut_path": str(shortcut),
                        "source": "start_menu",
                    })
                    if len(shortcuts) >= limit:
                        return shortcuts
            except (OSError, PermissionError):
                continue
        return shortcuts

    def _registry_applications(self, limit: int = 1000) -> list[dict[str, Any]]:
        if os.name != "nt":
            return []
        try:
            import winreg
        except ImportError:
            return []

        roots = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hive, key_path in roots:
            try:
                parent = winreg.OpenKey(hive, key_path)
            except OSError:
                continue
            with parent:
                try:
                    count = winreg.QueryInfoKey(parent)[0]
                except OSError:
                    continue
                for index in range(count):
                    try:
                        child_name = winreg.EnumKey(parent, index)
                        with winreg.OpenKey(parent, child_name) as child:
                            values: dict[str, Any] = {}
                            for value_name in ("DisplayName", "DisplayVersion", "Publisher", "InstallLocation"):
                                try:
                                    values[value_name] = winreg.QueryValueEx(child, value_name)[0]
                                except OSError:
                                    pass
                        name = values.get("DisplayName")
                        if not isinstance(name, str) or not name.strip():
                            continue
                        identity = name.strip().casefold()
                        if identity in seen:
                            continue
                        seen.add(identity)
                        results.append({
                            "name": name.strip(),
                            "version": values.get("DisplayVersion"),
                            "publisher": values.get("Publisher"),
                            "install_location": values.get("InstallLocation"),
                            "source": "windows_registry",
                        })
                        if len(results) >= limit:
                            return results
                    except OSError:
                        continue
        return results

    def list_installed_applications(self, limit: int = 500) -> list[dict[str, Any]]:
        shortcuts = self._start_menu_shortcuts(limit)
        registry = self._registry_applications(max(0, limit - len(shortcuts)))
        combined = shortcuts + registry
        return sorted(combined, key=lambda item: str(item.get("name", "")).casefold())[:limit]

    def find_start_menu_shortcuts(self, name: str) -> list[str]:
        target = name.casefold().strip()
        return [
            item["shortcut_path"]
            for item in self._start_menu_shortcuts()
            if item["name"].casefold() == target
        ]

    def list_running_applications(self, limit: int = 500) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")

        try:
            import psutil
        except ImportError:
            psutil = None

        if psutil is not None:
            results: list[dict[str, Any]] = []
            for process in psutil.process_iter(["pid", "name", "exe", "username", "memory_info"]):
                try:
                    info = process.info
                    memory = info.get("memory_info")
                    results.append({
                        "pid": int(info["pid"]),
                        "name": info.get("name") or "",
                        "executable": info.get("exe"),
                        "username": info.get("username"),
                        "memory_bytes": int(memory.rss) if memory else None,
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
                    continue
                if len(results) >= limit:
                    break
            return sorted(results, key=lambda item: str(item["name"]).casefold())

        if os.name == "nt":
            completed = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError("Could not query running applications with tasklist")
            results = []
            for row in csv.reader(completed.stdout.splitlines()):
                if len(row) < 2:
                    continue
                try:
                    pid = int(row[1].replace(",", ""))
                except ValueError:
                    continue
                results.append({"pid": pid, "name": row[0], "executable": None, "username": None, "memory_bytes": None})
                if len(results) >= limit:
                    break
            return results

        completed = subprocess.run(
            ["ps", "-eo", "pid=,comm="],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError("Could not query running applications")
        results = []
        for line in completed.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) != 2:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            results.append({"pid": pid, "name": parts[1], "executable": None, "username": None, "memory_bytes": None})
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _win32():
        if os.name != "nt":
            raise RuntimeError("Window management is currently supported on Windows only")
        import ctypes
        from ctypes import wintypes

        return ctypes, wintypes

    def list_application_windows(self, limit: int = 500) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        ctypes, wintypes = self._win32()
        user32 = ctypes.windll.user32
        results: list[dict[str, Any]] = []

        enum_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = [enum_callback, wintypes.LPARAM]
        user32.EnumWindows.restype = wintypes.BOOL
        user32.IsWindow.argtypes = [wintypes.HWND]
        user32.IsWindow.restype = wintypes.BOOL
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        def visit(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            title = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title, length + 1)
            if not title.value.strip():
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            results.append({"window_handle": int(hwnd), "title": title.value, "pid": int(pid.value)})
            return len(results) < limit

        callback = enum_callback(visit)
        user32.EnumWindows(callback, 0)
        return results

    @staticmethod
    def _configure_user32(ctypes, wintypes):
        user32 = ctypes.windll.user32
        user32.IsWindow.argtypes = [wintypes.HWND]
        user32.IsWindow.restype = wintypes.BOOL
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.PostMessageW.restype = wintypes.BOOL
        return user32

    def _validate_window(self, window_handle: int) -> int:
        if isinstance(window_handle, bool) or not isinstance(window_handle, int) or window_handle <= 0:
            raise ValueError("window_handle must be a positive integer")
        ctypes, wintypes = self._win32()
        user32 = self._configure_user32(ctypes, wintypes)
        if not user32.IsWindow(wintypes.HWND(window_handle)):
            raise ValueError("The window handle is not valid")
        return window_handle

    def focus_window(self, window_handle: int) -> bool:
        hwnd = self._validate_window(window_handle)
        ctypes, wintypes = self._win32()
        user32 = self._configure_user32(ctypes, wintypes)
        user32.ShowWindow(wintypes.HWND(hwnd), 9)  # SW_RESTORE
        return bool(user32.SetForegroundWindow(wintypes.HWND(hwnd)))

    def minimize_window(self, window_handle: int) -> bool:
        hwnd = self._validate_window(window_handle)
        ctypes, wintypes = self._win32()
        user32 = self._configure_user32(ctypes, wintypes)
        user32.ShowWindow(wintypes.HWND(hwnd), 6)  # SW_MINIMIZE
        return bool(user32.IsWindow(wintypes.HWND(hwnd)))

    def maximize_window(self, window_handle: int) -> bool:
        hwnd = self._validate_window(window_handle)
        ctypes, wintypes = self._win32()
        user32 = self._configure_user32(ctypes, wintypes)
        user32.ShowWindow(wintypes.HWND(hwnd), 3)  # SW_MAXIMIZE
        return bool(user32.IsWindow(wintypes.HWND(hwnd)))

    def restore_window(self, window_handle: int) -> bool:
        hwnd = self._validate_window(window_handle)
        ctypes, wintypes = self._win32()
        user32 = self._configure_user32(ctypes, wintypes)
        user32.ShowWindow(wintypes.HWND(hwnd), 9)  # SW_RESTORE
        return bool(user32.IsWindow(wintypes.HWND(hwnd)))

    def close_window(self, window_handle: int) -> bool:
        hwnd = self._validate_window(window_handle)
        ctypes, wintypes = self._win32()
        user32 = self._configure_user32(ctypes, wintypes)
        # Post WM_CLOSE rather than blocking on an unresponsive application.
        return bool(user32.PostMessageW(wintypes.HWND(hwnd), 0x0010, 0, 0))

    def terminate_application(self, pid: int, expected_name: str, force: bool = False) -> dict[str, Any]:
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise ValueError("pid must be a positive integer")
        if pid == os.getpid():
            raise PermissionError("AI-OS cannot terminate its own process")
        if not isinstance(expected_name, str) or not expected_name.strip():
            raise ValueError("expected_name is required to guard against terminating the wrong process")
        if not isinstance(force, bool):
            raise TypeError("force must be a boolean")

        try:
            import psutil
        except ImportError:
            psutil = None

        if psutil is not None:
            try:
                process = psutil.Process(pid)
                actual_name = process.name()
                if actual_name.casefold() != expected_name.strip().casefold():
                    raise PermissionError(f"Process name mismatch: expected {expected_name}, found {actual_name}")
                process.kill() if force else process.terminate()
                try:
                    process.wait(timeout=3)
                    return {"success": True, "pid": pid, "name": actual_name, "terminated": True, "force": force}
                except psutil.TimeoutExpired:
                    if force:
                        process.kill()
                        process.wait(timeout=3)
                        return {"success": True, "pid": pid, "name": actual_name, "terminated": True, "force": True}
                    return {"success": True, "pid": pid, "name": actual_name, "terminated": False, "state": "termination_requested", "force": False}
            except psutil.NoSuchProcess as exc:
                raise ProcessLookupError(f"Process {pid} no longer exists") from exc

        if os.name == "nt":
            completed = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            rows = list(csv.reader(completed.stdout.splitlines()))
            actual_name = rows[0][0] if completed.returncode == 0 and rows and len(rows[0]) > 1 else ""
            if not actual_name or actual_name.casefold() != expected_name.strip().casefold():
                raise PermissionError(f"Process name mismatch or process unavailable: expected {expected_name}, found {actual_name}")
            command = ["taskkill", "/PID", str(pid), "/T"]
            if force:
                command.append("/F")
            result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "taskkill failed")
            return {"success": True, "pid": pid, "name": actual_name, "terminated": force, "state": "termination_requested" if not force else "terminated", "force": force}

        try:
            completed = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True, timeout=10, check=False)
            actual_name = Path(completed.stdout.strip()).name
            if completed.returncode != 0 or actual_name.casefold() != expected_name.strip().casefold():
                raise PermissionError(f"Process name mismatch or process unavailable: expected {expected_name}, found {actual_name}")
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            raise
        return {"success": True, "pid": pid, "name": actual_name, "terminated": force, "state": "termination_requested" if not force else "terminated", "force": force}


class Applications:
    """Validated application control facade with an injectable backend."""

    def __init__(self, driver: Any | None = None) -> None:
        self.driver = driver or WindowsApplicationDriver()

    @staticmethod
    def _validate_limit(limit: int, *, maximum: int = 5000) -> int:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= maximum:
            raise ValueError(f"limit must be between 1 and {maximum}")
        return limit

    @staticmethod
    def _validate_application(application: str) -> str:
        if not isinstance(application, str) or not application.strip() or "\x00" in application:
            raise ValueError("A non-empty application name or path is required")
        return application.strip()

    @staticmethod
    def _validate_args(args: list[str] | None) -> list[str]:
        if args is None:
            return []
        if not isinstance(args, list):
            raise TypeError("args must be a list of strings")
        if len(args) > 100:
            raise ValueError("args cannot contain more than 100 entries")
        total = 0
        for item in args:
            if not isinstance(item, str) or "\x00" in item:
                raise TypeError("Every argument must be a string without NUL characters")
            if len(item) > 4096:
                raise ValueError("An application argument exceeds 4096 characters")
            total += len(item)
        if total > 32000:
            raise ValueError("Combined application arguments exceed 32000 characters")
        return args

    @staticmethod
    def _validate_window_handle(window_handle: int) -> int:
        if isinstance(window_handle, bool) or not isinstance(window_handle, int) or window_handle <= 0:
            raise ValueError("window_handle must be a positive integer")
        return window_handle

    def list_installed_applications(self, limit: int = 500) -> list[dict[str, Any]]:
        self._validate_limit(limit, maximum=1000)
        return self.driver.list_installed_applications(limit)

    def list_running_applications(self, limit: int = 500) -> list[dict[str, Any]]:
        self._validate_limit(limit)
        return self.driver.list_running_applications(limit)

    def list_application_windows(self, limit: int = 500) -> list[dict[str, Any]]:
        self._validate_limit(limit)
        return self.driver.list_application_windows(limit)

    def launch_application(
        self,
        application: str,
        args: list[str] | None = None,
        working_directory: str | None = None,
    ) -> dict[str, Any]:
        name = self._validate_application(application)
        validated_args = self._validate_args(args)
        cwd = None
        if working_directory is not None:
            if not isinstance(working_directory, str) or not working_directory.strip() or "\x00" in working_directory:
                raise ValueError("working_directory must be a non-empty path")
            cwd_path = Path(working_directory).expanduser().resolve()
            if not cwd_path.is_dir():
                raise NotADirectoryError(f"Working directory does not exist: {working_directory}")
            cwd = str(cwd_path)
        return self.driver.launch_application(name, validated_args, cwd)

    def focus_window(self, window_handle: int) -> dict[str, Any]:
        hwnd = self._validate_window_handle(window_handle)
        return {"success": bool(self.driver.focus_window(hwnd)), "window_handle": hwnd, "action": "focus"}

    def minimize_window(self, window_handle: int) -> dict[str, Any]:
        hwnd = self._validate_window_handle(window_handle)
        return {"success": bool(self.driver.minimize_window(hwnd)), "window_handle": hwnd, "action": "minimize"}

    def maximize_window(self, window_handle: int) -> dict[str, Any]:
        hwnd = self._validate_window_handle(window_handle)
        return {"success": bool(self.driver.maximize_window(hwnd)), "window_handle": hwnd, "action": "maximize"}

    def restore_window(self, window_handle: int) -> dict[str, Any]:
        hwnd = self._validate_window_handle(window_handle)
        return {"success": bool(self.driver.restore_window(hwnd)), "window_handle": hwnd, "action": "restore"}

    def close_window(self, window_handle: int) -> dict[str, Any]:
        hwnd = self._validate_window_handle(window_handle)
        return {"success": bool(self.driver.close_window(hwnd)), "window_handle": hwnd, "action": "close"}

    def terminate_application(self, pid: int, expected_name: str, force: bool = False) -> dict[str, Any]:
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise ValueError("pid must be a positive integer")
        if not isinstance(expected_name, str) or not expected_name.strip():
            raise ValueError("expected_name is required to guard against terminating the wrong process")
        if not isinstance(force, bool):
            raise TypeError("force must be a boolean")
        return self.driver.terminate_application(pid, expected_name, force)


applications = Applications()


__all__ = ["Applications", "WindowsApplicationDriver", "applications"]
