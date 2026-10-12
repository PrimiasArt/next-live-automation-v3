import os
import sys
import time
import subprocess
import psutil
from core.state import state

DEFAULT_PATHS = [
    os.getenv("STREAM_PROCESSOR_PATH", ""),
    r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
    r"C:\Program Files (x86)\obs-studio\bin\64bit\obs64.exe",
    r"C:\Program Files\obs-studio\bin\32bit\obs32.exe",
    r"D:\Program Files\obs-studio\bin\64bit\obs64.exe",
    r"E:\Program Files\obs-studio\bin\64bit\obs64.exe"
]

class StreamProcessManager:
    def __init__(self):
        self.cached_path = None

    def find_processor_path(self) -> str | None:
        if self.cached_path and os.path.isfile(self.cached_path):
            return self.cached_path

        for p in DEFAULT_PATHS:
            if p and os.path.isfile(p):
                self.cached_path = p
                return p

        # Thử tìm qua Registry Windows
        try:
            import winreg
            for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(root_key, r"SOFTWARE\OBS Studio") as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        candidate = os.path.join(val, "bin", "64bit", "obs64.exe")
                        if os.path.isfile(candidate):
                            self.cached_path = candidate
                            return candidate
                except OSError:
                    pass
        except Exception:
            pass

        return None

    def get_process_info(self) -> tuple[bool, int | None]:
        """
        Kiểm tra xem Bộ Xử Lý Luồng (Stream Processor) có đang chạy không.
        Trả về: (is_running, pid)
        """
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = (proc.info['name'] or '').lower()
                if name in ('obs64.exe', 'obs32.exe', 'obs.exe'):
                    return True, proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False, None

    def start_processor(self, minimize_to_tray: bool = True) -> dict:
        """
        Khởi chạy Stream Processor ở chế độ chạy ngầm (Silent / Minimize to Tray)
        """
        is_running, pid = self.get_process_info()
        if is_running:
            return {"success": True, "message": f"Stream Processor đang hoạt động (PID: {pid})", "pid": pid}

        exe_path = self.find_processor_path()
        if not exe_path:
            msg = "Không tìm thấy file thực thi của Stream Processor trên máy tính."
            state.add_log("PROCESSOR", f"❌ {msg}")
            return {"success": False, "message": msg}

        work_dir = os.path.dirname(exe_path)
        cmd = [exe_path, "--disable-updater"]
        if minimize_to_tray:
            cmd.append("--minimize-to-tray")

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=work_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
            )
            state.add_log("PROCESSOR", f"🚀 [STREAM PROCESSOR] Đã khởi chạy Bộ Xử Lý Luồng chạy ngầm (PID: {proc.pid})")
            time.sleep(2.0)
            return {"success": True, "message": f"Đã khởi động Stream Processor (PID: {proc.pid})", "pid": proc.pid}
        except Exception as e:
            err = f"Lỗi khởi chạy Stream Processor: {str(e)}"
            state.add_log("PROCESSOR", f"❌ {err}")
            return {"success": False, "message": err}

    def stop_processor(self) -> dict:
        """
        Dừng tiến trình Stream Processor
        """
        is_running, pid = self.get_process_info()
        if not is_running:
            return {"success": True, "message": "Stream Processor hiện không chạy."}

        try:
            proc = psutil.Process(pid)
            proc.terminate()
            gone, alive = psutil.wait_procs([proc], timeout=3)
            if alive:
                for p in alive:
                    p.kill()
            state.add_log("PROCESSOR", f"🛑 [STREAM PROCESSOR] Đã đóng Bộ Xử Lý Luồng (PID: {pid}).")
            return {"success": True, "message": "Đã dừng Stream Processor thành công."}
        except Exception as e:
            err = f"Lỗi dừng Stream Processor: {str(e)}"
            state.add_log("PROCESSOR", f"❌ {err}")
            return {"success": False, "message": err}

    def restart_processor(self) -> dict:
        self.stop_processor()
        time.sleep(1.5)
        return self.start_processor()

    def get_status(self) -> dict:
        is_running, pid = self.get_process_info()
        path = self.find_processor_path()
        return {
            "success": True,
            "running": is_running,
            "pid": pid,
            "path": path,
            "installed": path is not None
        }

process_manager = StreamProcessManager()
