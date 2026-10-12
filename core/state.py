import datetime
import threading
from collections import deque

class AppState:
    def __init__(self):
        self._lock = threading.RLock()
        
        self.is_authorized = False
        self.is_running = False  # Ban đầu ở chế độ chờ (Standby)
        self.current_video = "Chế độ chờ (Vui lòng chọn Scene)"
        self.remaining = 0.0
        self.progress = 0.0
        self.task_queue = deque(maxlen=20)
        self.api_key_id = None
        self.quota_remaining = 0
        self.web_logs = deque(maxlen=40)
        self.active_sources_by_group = {}
        
        # Profile ban đầu là None (Không có scene mặc định)
        self.current_profile = None
        self.public_url = None
        
        # Event để hỗ trợ Fast Switch (cắt ngang video ngay lập tức)
        self.fast_switch_event = threading.Event()

    def add_log(self, tag: str, message: str):
        with self._lock:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.web_logs.append(f"[{timestamp}] [{tag}] {message}")

    def set_authorized(self, authorized: bool, key_id=None, quota: int = 0):
        with self._lock:
            self.is_authorized = authorized
            self.api_key_id = key_id
            self.quota_remaining = quota
            if not authorized:
                self.is_running = False
                self.current_video = "System Locked"

    def set_standby(self):
        """
        Đưa hệ thống về chế độ chờ (Standby)
        """
        with self._lock:
            self.is_running = False
            self.current_video = "Chế độ chờ (Vui lòng chọn Scene)"
            self.remaining = 0.0
            self.progress = 0.0
            self.task_queue.clear()
            self.fast_switch_event.set()
            self.add_log("SYSTEM", "⏸️ Hệ thống đang ở chế độ CHỜ (Standby). Chờ chọn Scene...")

    def set_profile(self, profile: dict, fast_switch: bool = True):
        with self._lock:
            self.current_profile = profile
            self.task_queue.clear()
            self.is_running = True
            p_name = profile.get('name', profile.get('scene_name', 'Chưa đặt tên'))
            v_count = len(profile.get('videos', []))
            self.add_log("PROFILE", f"▶️ Đã chọn Scene: {profile.get('scene_name')} ({v_count} video base_*) - BẮT ĐẦU CHẠY!")
            if fast_switch:
                self.fast_switch_event.set()

    def add_task(self, video_name: str, is_fast_track: bool = False) -> bool:
        with self._lock:
            if not self.is_running:
                return False
            if is_fast_track:
                self.task_queue.appendleft(video_name)
                self.add_log("QUEUE", f"⚡ [FAST TRACK] Đẩy video '{video_name}' lên đầu hàng đợi")
            else:
                self.task_queue.append(video_name)
                self.add_log("QUEUE", f"📥 Đã xếp video '{video_name}' vào cuối hàng chờ")
            return True

    def remove_task(self, index: int) -> bool:
        with self._lock:
            if index is not None and 0 <= index < len(self.task_queue):
                temp = list(self.task_queue)
                removed = temp.pop(index)
                self.task_queue = deque(temp, maxlen=20)
                self.add_log("QUEUE", f"🗑️ Đã xóa video '{removed}' khỏi hàng đợi")
                return True
            return False

    def clear_queue(self) -> bool:
        with self._lock:
            self.task_queue.clear()
            self.add_log("QUEUE", "🧹 Đã xóa sạch toàn bộ hàng chờ")
            return True

    def set_group_active_source(self, group_id: str, source_name: str):
        with self._lock:
            self.active_sources_by_group[group_id] = source_name

    def remove_group_active_source(self, group_id: str):
        with self._lock:
            self.active_sources_by_group.pop(group_id, None)

    def get_next_task(self):
        with self._lock:
            if self.task_queue:
                return self.task_queue.popleft()
            return None

    def update_video_status(self, video_name: str, remaining: float, progress: float):
        with self._lock:
            self.current_video = video_name
            self.remaining = remaining
            self.progress = progress

    def deduct_quota(self, amount: int = 1) -> int:
        with self._lock:
            self.quota_remaining = max(0, self.quota_remaining - amount)
            if self.quota_remaining <= 0:
                self.is_authorized = False
                self.is_running = False
                self.current_video = "System Locked"
                self.add_log("AUTH", "⚠️ Hạn mức credits đã hết! Hệ thống bị khóa.")
            return self.quota_remaining

    def to_dict(self):
        with self._lock:
            p_dict = None
            if self.current_profile:
                p_dict = {
                    "id": self.current_profile.get("id"),
                    "name": self.current_profile.get("name"),
                    "scene_name": self.current_profile.get("scene_name"),
                    "video_count": len(self.current_profile.get("videos", []))
                }
            return {
                "authorized": self.is_authorized,
                "is_running": self.is_running,
                "current_video": self.current_video,
                "remaining": round(self.remaining, 1),
                "progress": min(100.0, max(0.0, round(self.progress, 1))),
                "queue": list(self.task_queue),
                "quota_remaining": self.quota_remaining,
                "logs": list(self.web_logs),
                "public_url": self.public_url,
                "current_profile": p_dict,
                "active_sources": dict(self.active_sources_by_group)
            }

state = AppState()
