import time
import random
import threading
import obsws_python as obs
from config import OBS_HOST, OBS_PORT, OBS_PASSWORD
from core.state import state
from core.quota_manager import quota_manager

class HLCEngine:
    def __init__(self):
        self.cl = None
        self.last_video = None
        self.running = True
        self.connect_obs()

    def connect_obs(self):
        try:
            kwargs = {"host": OBS_HOST, "port": OBS_PORT}
            if OBS_PASSWORD:
                kwargs["password"] = OBS_PASSWORD
            self.cl = obs.ReqClient(**kwargs)
            state.add_log("OBS", f"✅ Đã kết nối OBS WebSocket tại {OBS_HOST}:{OBS_PORT}")
            return True
        except Exception as e:
            state.add_log("OBS", f"❌ Không thể kết nối tới OBS Studio: {str(e)}")
            self.cl = None
            return False

    def ensure_connection(self):
        if not self.cl:
            return self.connect_obs()
        return True

    def get_current_scene_name(self):
        if state.current_profile:
            return state.current_profile.get("scene_name")
        return None

    def get_current_overlap_time(self):
        if state.current_profile:
            return float(state.current_profile.get("overlap_time", 1.0))
        return 1.0

    def change_obs_program_scene(self, scene_name: str) -> bool:
        """
        Tự động chuyển đổi Program Scene trên màn hình OBS Studio
        """
        if not scene_name or not self.ensure_connection():
            return False
        try:
            self.cl.set_current_program_scene(scene_name)
            state.add_log("OBS", f"🎬 [SCENE SWITCH] Đã tự động chuyển Scene OBS sang: '{scene_name}'")
            return True
        except Exception as e:
            state.add_log("OBS", f"❌ Không thể đổi sang Scene '{scene_name}' trên OBS: {str(e)}")
            return False

    def get_stream_settings(self) -> dict:
        """
        Lấy cấu hình RTMP Server và Stream Key hiện tại từ OBS
        """
        if not self.ensure_connection():
            return {"success": False, "message": "Chưa kết nối được tới OBS Studio"}
        try:
            res = self.cl.get_stream_service_settings()
            settings = getattr(res, "stream_service_settings", {})
            service_type = getattr(res, "stream_service_type", "rtmp_custom")
            return {
                "success": True,
                "service_type": service_type,
                "server": settings.get("server", ""),
                "key": settings.get("key", "")
            }
        except Exception as e:
            return {"success": False, "message": f"Lỗi lấy cấu hình Stream từ OBS: {str(e)}"}

    def set_stream_settings(self, server: str, key: str, service_type: str = "rtmp_custom") -> dict:
        """
        Đẩy RTMP Server và Stream Key trực tiếp vào cài đặt Stream của OBS
        """
        if not self.ensure_connection():
            return {"success": False, "message": "Chưa kết nối được tới OBS Studio"}
        try:
            payload = {
                "server": server.strip(),
                "key": key.strip()
            }
            self.cl.set_stream_service_settings(service_type, payload)
            # Mask stream key khi ghi log để bảo mật
            masked_key = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
            state.add_log("STREAM", f"📡 [RTMP CONFIG] Đã áp dụng URL: {server.strip()} | Key: {masked_key} sang OBS")
            return {"success": True, "message": "Đã cập nhật RTMP Server & Stream Key sang OBS thành công!"}
        except Exception as e:
            state.add_log("STREAM", f"❌ Lỗi cập nhật RTMP trên OBS: {str(e)}")
            return {"success": False, "message": f"Không thể lưu cấu hình Stream trên OBS: {str(e)}"}

    def get_stream_status(self) -> dict:
        """
        Kiểm tra trạng thái phát Live hiện tại của OBS
        """
        if not self.ensure_connection():
            return {"active": False, "reconnecting": False, "timecode": "00:00:00", "duration": 0}
        try:
            res = self.cl.get_stream_status()
            return {
                "active": getattr(res, "output_active", False),
                "reconnecting": getattr(res, "output_reconnecting", False),
                "timecode": getattr(res, "output_timecode", "00:00:00"),
                "duration": getattr(res, "output_duration", 0)
            }
        except Exception:
            return {"active": False, "reconnecting": False, "timecode": "00:00:00", "duration": 0}

    def start_streaming(self) -> dict:
        """
        Kích hoạt nút Bắt Đầu Live (Start Streaming) trên OBS
        """
        if not self.ensure_connection():
            return {"success": False, "message": "Chưa kết nối được tới OBS Studio"}
        try:
            self.cl.start_stream()
            state.add_log("STREAM", "🔴 [LIVE START] Đã kích hoạt PHÁT STREAM trực tiếp trên OBS!")
            return {"success": True, "message": "Đã bắt đầu phát Stream trên OBS"}
        except Exception as e:
            return {"success": False, "message": f"Lỗi bắt đầu Stream: {str(e)}"}

    def stop_streaming(self) -> dict:
        """
        Kích hoạt nút Dừng Live (Stop Streaming) trên OBS
        """
        if not self.ensure_connection():
            return {"success": False, "message": "Chưa kết nối được tới OBS Studio"}
        try:
            self.cl.stop_stream()
            state.add_log("STREAM", "⏹ [LIVE STOP] Đã DỪNG PHÁT STREAM trên OBS!")
            return {"success": True, "message": "Đã dừng phát Stream trên OBS"}
        except Exception as e:
            return {"success": False, "message": f"Lỗi dừng Stream: {str(e)}"}

    def play_video(self, v_name: str) -> bool:
        if not self.ensure_connection():
            return False
            
        scene_name = self.get_current_scene_name()
        if not scene_name:
            return False

        overlap = self.get_current_overlap_time()

        try:
            items_res = self.cl.get_scene_item_list(scene_name)
            items = items_res.scene_items
            
            # Tìm ID của video mới (khớp tên nguồn hoặc tên kèm .mp4)
            nid = next((i['sceneItemId'] for i in items if i['sourceName'] in [v_name, f"{v_name}.mp4"]), None)
            
            if nid is not None:
                # 1. Sử dụng ExecuteBatch của OBS WebSocket v5 để chuyển video tức thì (<5ms)
                batch_requests = []
                
                # Bật nguồn video mới
                batch_requests.append({
                    "requestType": "SetSceneItemEnabled",
                    "requestData": {"sceneName": scene_name, "sceneItemId": nid, "sceneItemEnabled": True}
                })
                # Khởi động lại video từ đầu
                batch_requests.append({
                    "requestType": "TriggerMediaInputAction",
                    "requestData": {"inputName": v_name, "mediaAction": "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"}
                })
                
                # Tắt nguồn video cũ: CHỈ TẮT NẾU LÀ SOURCE base_
                if self.last_video and self.last_video != v_name:
                    if self.last_video.lower().startswith("base_"):
                        oid = next((i['sceneItemId'] for i in items if i['sourceName'] in [self.last_video, f"{self.last_video}.mp4"]), None)
                        if oid is not None and oid != nid:
                            batch_requests.append({
                                "requestType": "SetSceneItemEnabled",
                                "requestData": {"sceneName": scene_name, "sceneItemId": oid, "sceneItemEnabled": False}
                            })

                try:
                    self.cl.send("ExecuteBatch", {"requests": batch_requests, "executionType": 0})
                except Exception:
                    # Fallback tuần tự nếu phiên bản OBS không hỗ trợ batch
                    self.cl.set_scene_item_enabled(scene_name, nid, True)
                    time.sleep(overlap)
                    if self.last_video and self.last_video != v_name and self.last_video.lower().startswith("base_"):
                        oid = next((i['sceneItemId'] for i in items if i['sourceName'] in [self.last_video, f"{self.last_video}.mp4"]), None)
                        if oid is not None and oid != nid:
                            self.cl.set_scene_item_enabled(scene_name, oid, False)

                self.last_video = v_name
                state.current_video = v_name
                state.add_log("OBS", f"🎬 [FAST-BATCH] Đang phát: {v_name} (Scene: {scene_name})")
                return True
            else:
                state.add_log("OBS", f"⚠️ Không tìm thấy source '{v_name}' trong Scene '{scene_name}'")
        except Exception as e:
            state.add_log("OBS", f"❌ Lỗi chuyển video {v_name}: {str(e)}")
            self.cl = None
        return False

    def hide_all_sources(self, target_scene: str = None) -> bool:
        """
        CHỈ TẮT MẮT các source có tiền tố 'base_', bảo vệ 100% các layer khác (logo, camera, text, audio)
        Sử dụng ExecuteBatch của OBS WebSocket v5 để tắt đồng loạt trong 1 roundtrip duy nhất.
        """
        if not self.ensure_connection():
            return False
            
        scene_name = target_scene or self.get_current_scene_name()
        if not scene_name:
            return False

        try:
            items_res = self.cl.get_scene_item_list(scene_name)
            items = items_res.scene_items
            base_items = [
                i for i in items 
                if i.get('sourceName', '').lower().startswith("base_")
            ]
            
            if base_items:
                batch_requests = [
                    {
                        "requestType": "SetSceneItemEnabled",
                        "requestData": {
                            "sceneName": scene_name,
                            "sceneItemId": item['sceneItemId'],
                            "sceneItemEnabled": False
                        }
                    }
                    for item in base_items
                ]
                try:
                    self.cl.send("ExecuteBatch", {"requests": batch_requests, "executionType": 0})
                except Exception:
                    # Fallback tuần tự nếu cần
                    for item in base_items:
                        self.cl.set_scene_item_enabled(scene_name, item['sceneItemId'], False)
                        
            state.add_log("OBS", f"⚡ [EXECUTE-BATCH] Đã ẩn siêu tốc {len(base_items)} nguồn video base_ trong Scene '{scene_name}'")
            return True
        except Exception as e:
            state.add_log("OBS", f"❌ Lỗi ẩn source trong Scene '{scene_name}': {str(e)}")
            return False

    def switch_profile(self, new_profile: dict, fast_switch: bool = True):
        """
        Chuyển đổi sang Brand / Profile mới:
        1. Tự động đổi Program Scene trên OBS sang scene của Brand mới
        2. Chỉ tắt mắt các source base_xxx (giữ nguyên camera, logo, text)
        3. Bắt đầu chạy vòng lặp phát video
        """
        old_scene = self.get_current_scene_name()
        new_scene = new_profile.get("scene_name")
        
        state.add_log("PROFILE", f"🚀 Kích hoạt chuyển đổi Scene -> {new_profile.get('name', new_scene)}")

        if fast_switch:
            state.fast_switch_event.set()
            if old_scene:
                self.hide_all_sources(old_scene)

        # Cập nhật profile mới vào state và bật is_running = True
        state.set_profile(new_profile, fast_switch=fast_switch)
        
        if new_scene:
            # 1. TỰ ĐỘNG CHUYỂN PROGRAM SCENE TRÊN OBS
            self.change_obs_program_scene(new_scene)
            # 2. CHỈ TẮT MẮT CÁC SOURCE base_ TRONG SCENE MỚI
            self.hide_all_sources(new_scene)

        self.last_video = None

    def start_loop(self):
        """
        Vòng lặp chính điều khiển phát video tự động.
        Ban đầu hệ thống ở chế độ CHỜ (Standby), không can thiệp vào OBS.
        Chỉ khi người dùng chọn Scene mới bắt đầu chạy!
        """
        accumulated_seconds = 0.0

        while self.running:
            if not state.is_authorized:
                time.sleep(0.5)
                continue

            if not state.is_running or not state.current_profile:
                time.sleep(0.5)
                continue

            if state.quota_remaining <= 0:
                state.set_authorized(False)
                time.sleep(1)
                continue

            if state.fast_switch_event.is_set():
                state.fast_switch_event.clear()

            videos_list = state.current_profile.get("videos", [])
            if not videos_list:
                state.current_video = "Scene chưa có video base_ nào"
                state.remaining = 0.0
                state.progress = 0.0
                time.sleep(1)
                continue

            durations_map = {v["name"]: float(v.get("duration", 30.0)) for v in videos_list}

            next_task = state.get_next_task()
            if next_task:
                current_name = next_task
            else:
                available_keys = list(durations_map.keys())
                if len(available_keys) > 1 and self.last_video in available_keys:
                    available_keys.remove(self.last_video)
                current_name = random.choice(available_keys) if available_keys else list(durations_map.keys())[0]

            duration = durations_map.get(current_name, 30.0)
            overlap = self.get_current_overlap_time()

            if self.play_video(current_name):
                wait_time = max(0.1, duration - overlap)
                start_p = time.time()
                
                interrupted = False
                while (time.time() - start_p) < wait_time:
                    if state.fast_switch_event.is_set() or not state.is_running:
                        state.add_log("FAST-SWITCH", f"⚡ [NGẮT] Dừng video '{current_name}'!")
                        interrupted = True
                        break
                    
                    elapsed = time.time() - start_p
                    rem = max(0.0, wait_time - elapsed)
                    prog = (elapsed / wait_time) * 100.0 if wait_time > 0 else 0.0
                    state.update_video_status(current_name, rem, prog)
                    time.sleep(0.1)

                if interrupted:
                    state.fast_switch_event.clear()
                    continue

                accumulated_seconds += duration

                if accumulated_seconds >= 60.0:
                    mins = int(accumulated_seconds // 60)
                    accumulated_seconds -= (mins * 60)
                    new_quota = state.deduct_quota(mins)
                    threading.Thread(
                        target=quota_manager.deduct_quota,
                        args=(state.api_key_id, new_quota),
                        daemon=True
                    ).start()
            else:
                time.sleep(2.0)

engine = HLCEngine()
