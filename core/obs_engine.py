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

    def connect_obs(self, auto_launch: bool = True):
        try:
            kwargs = {"host": OBS_HOST, "port": OBS_PORT}
            if OBS_PASSWORD:
                kwargs["password"] = OBS_PASSWORD
            self.cl = obs.ReqClient(**kwargs)
            state.add_log("PROCESSOR", f"✅ Đã kết nối Stream Processor Engine tại {OBS_HOST}:{OBS_PORT}")
            return True
        except Exception as e:
            if auto_launch:
                from core.stream_process_manager import process_manager
                is_running, _ = process_manager.get_process_info()
                if not is_running:
                    state.add_log("PROCESSOR", "⚙️ Stream Processor chưa chạy -> Đang tự động kích hoạt ngầm...")
                    res = process_manager.start_processor(minimize_to_tray=True)
                    if res.get("success"):
                        return self.connect_obs(auto_launch=False)
            state.add_log("PROCESSOR", f"❌ Không thể kết nối tới Stream Processor Engine: {str(e)}")
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
        Tự động chuyển đổi Program Scene trên màn hình Stream Processor
        """
        if not scene_name or not self.ensure_connection():
            return False
        try:
            self.cl.set_current_program_scene(scene_name)
            state.add_log("PROCESSOR", f"🎬 [SCENE SWITCH] Đã chuyển Kịch Bản sang: '{scene_name}'")
            return True
        except Exception as e:
            state.add_log("PROCESSOR", f"❌ Không thể đổi sang Kịch Bản '{scene_name}': {str(e)}")
            return False

    def get_stream_settings(self) -> dict:
        """
        Lấy cấu hình RTMP Server và Stream Key hiện tại từ Stream Processor
        """
        if not self.ensure_connection():
            return {"success": False, "message": "Chưa kết nối được tới Stream Processor"}
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
            return {"success": False, "message": f"Lỗi lấy cấu hình Stream từ Stream Processor: {str(e)}"}

    def set_stream_settings(self, server: str, key: str, service_type: str = "rtmp_custom") -> dict:
        """
        Đẩy RTMP Server và Stream Key trực tiếp vào cài đặt Stream của Stream Processor
        """
        if not self.ensure_connection():
            return {"success": False, "message": "Chưa kết nối được tới Stream Processor"}
        try:
            payload = {
                "server": server.strip(),
                "key": key.strip()
            }
            self.cl.set_stream_service_settings(service_type, payload)
            # Mask stream key khi ghi log để bảo mật
            masked_key = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
            state.add_log("STREAM", f"📡 [RTMP CONFIG] Đã áp dụng URL: {server.strip()} | Key: {masked_key} sang Stream Processor")
            return {"success": True, "message": "Đã cập nhật RTMP Server & Stream Key sang Stream Processor thành công!"}
        except Exception as e:
            state.add_log("STREAM", f"❌ Lỗi cập nhật RTMP trên Stream Processor: {str(e)}")
            return {"success": False, "message": f"Không thể lưu cấu hình Stream trên Stream Processor: {str(e)}"}

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
            return {"success": False, "message": "Chưa kết nối được tới Stream Processor"}
        try:
            self.cl.start_stream()
            state.add_log("STREAM", "🔴 [LIVE START] Đã kích hoạt PHÁT STREAM trực tiếp trên Stream Processor!")
            return {"success": True, "message": "Đã bắt đầu phát Stream"}
        except Exception as e:
            return {"success": False, "message": f"Lỗi bắt đầu Stream: {str(e)}"}

    def stop_streaming(self) -> dict:
        """
        Kích hoạt nút Dừng Live (Stop Streaming) trên Stream Processor
        """
        if not self.ensure_connection():
            return {"success": False, "message": "Chưa kết nối được tới Stream Processor"}
        try:
            self.cl.stop_stream()
            state.add_log("STREAM", "⏹ [LIVE STOP] Đã DỪNG PHÁT STREAM trên Stream Processor!")
            return {"success": True, "message": "Đã dừng phát Stream"}
        except Exception as e:
            return {"success": False, "message": f"Lỗi dừng Stream: {str(e)}"}

    def get_video_settings(self) -> dict:
        """
        Lấy thông số Canvas (Base), Output (Scaled), Tỷ lệ khung hình và FPS từ OBS
        """
        if not self.ensure_connection():
            return {"success": False, "message": "Chưa kết nối được tới OBS Studio"}
        try:
            vs = self.cl.get_video_settings()
            fps = round(vs.fps_numerator / vs.fps_denominator) if vs.fps_denominator else vs.fps_numerator
            return {
                "success": True,
                "base_width": vs.base_width,
                "base_height": vs.base_height,
                "output_width": vs.output_width,
                "output_height": vs.output_height,
                "fps_numerator": vs.fps_numerator,
                "fps_denominator": vs.fps_denominator,
                "fps": fps
            }
        except Exception as e:
            return {"success": False, "message": f"Lỗi đọc Video Settings từ OBS: {str(e)}"}

    def set_video_settings(self, base_width: int, base_height: int, output_width: int, output_height: int, fps_numerator: int = 30, fps_denominator: int = 1) -> dict:
        """
        Cập nhật độ phân giải Base (Canvas), Output (Scaled) và FPS trực tiếp sang OBS Studio
        """
        if not self.ensure_connection():
            return {"success": False, "message": "Chưa kết nối được tới OBS Studio"}
            
        stream_st = self.get_stream_status()
        if stream_st.get("active"):
            return {"success": False, "message": "OBS đang phát Live! Bạn cần DỪNG LIVE trước khi đổi tỷ lệ khung hình / Canvas."}

        try:
            self.cl.set_video_settings(fps_numerator, fps_denominator, int(base_width), int(base_height), int(output_width), int(output_height))
            state.add_log("PROCESSOR", f"📐 [CANVAS & RATIO] Đã áp dụng Canvas: {base_width}x{base_height} | Output: {output_width}x{output_height} | {fps_numerator} FPS")
            return {
                "success": True,
                "message": f"Đã cập nhật Canvas ({base_width}x{base_height}) và Output ({output_width}x{output_height}) sang OBS thành công!"
            }
        except Exception as e:
            return {"success": False, "message": f"Lỗi cập nhật Video Settings: {str(e)}"}

    def get_output_parameters(self) -> dict:
        """
        Lấy thông số Video Bitrate, Audio Bitrate, Encoder và Audio từ OBS
        """
        if not self.ensure_connection():
            return {"success": False, "message": "Chưa kết nối được tới OBS Studio"}
        try:
            vbitrate = 3500
            abitrate = 160
            encoder = "nvenc"
            sample_rate = "48000"
            channels = "Stereo"

            try:
                vbitrate = int(self.cl.get_profile_parameter('SimpleOutput', 'VBitrate').parameter_value or 3500)
            except Exception: pass

            try:
                abitrate = int(self.cl.get_profile_parameter('SimpleOutput', 'ABitrate').parameter_value or 160)
            except Exception: pass

            try:
                encoder = self.cl.get_profile_parameter('SimpleOutput', 'StreamEncoder').parameter_value or "nvenc"
            except Exception: pass

            try:
                sample_rate = self.cl.get_profile_parameter('Audio', 'SampleRate').parameter_value or "48000"
            except Exception: pass

            try:
                channels = self.cl.get_profile_parameter('Audio', 'ChannelSetup').parameter_value or "Stereo"
            except Exception: pass

            return {
                "success": True,
                "video_bitrate": vbitrate,
                "audio_bitrate": abitrate,
                "video_encoder": encoder,
                "sample_rate": sample_rate,
                "channels": channels
            }
        except Exception as e:
            return {"success": False, "message": f"Lỗi đọc thông số Output: {str(e)}"}

    def set_output_parameters(self, video_bitrate=None, audio_bitrate=None, video_encoder=None, sample_rate=None, channels=None) -> dict:
        """
        Lưu thông số Video Bitrate, Audio Bitrate, Encoder sang OBS Profile
        """
        if not self.ensure_connection():
            return {"success": False, "message": "Chưa kết nối được tới OBS Studio"}
        try:
            updated = []
            if video_bitrate is not None:
                self.cl.set_profile_parameter('SimpleOutput', 'VBitrate', str(video_bitrate))
                updated.append(f"VBitrate: {video_bitrate}k")
            if audio_bitrate is not None:
                self.cl.set_profile_parameter('SimpleOutput', 'ABitrate', str(audio_bitrate))
                updated.append(f"ABitrate: {audio_bitrate}k")
            if video_encoder is not None:
                self.cl.set_profile_parameter('SimpleOutput', 'StreamEncoder', str(video_encoder))
                updated.append(f"Encoder: {video_encoder}")
            if sample_rate is not None:
                self.cl.set_profile_parameter('Audio', 'SampleRate', str(sample_rate))
                updated.append(f"SampleRate: {sample_rate}Hz")
            if channels is not None:
                self.cl.set_profile_parameter('Audio', 'ChannelSetup', str(channels))
                updated.append(f"Channels: {channels}")

            log_msg = ", ".join(updated)
            state.add_log("PROCESSOR", f"🎛️ [OUTPUT CONFIG] Đã áp dụng: {log_msg}")
            return {"success": True, "message": f"Đã lưu thông số Output ({log_msg}) sang OBS!"}
        except Exception as e:
            return {"success": False, "message": f"Lỗi lưu thông số Output: {str(e)}"}

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
                state.add_log("PROCESSOR", f"🎬 [FAST-BATCH] Đang phát: {v_name} (Scene: {scene_name})")
                return True
            else:
                state.add_log("PROCESSOR", f"⚠️ Không tìm thấy source '{v_name}' trong Scene '{scene_name}'")
        except Exception as e:
            state.add_log("PROCESSOR", f"❌ Lỗi chuyển video {v_name}: {str(e)}")
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
                        
            state.add_log("PROCESSOR", f"⚡ [EXECUTE-BATCH] Đã ẩn siêu tốc {len(base_items)} nguồn video base_ trong Scene '{scene_name}'")
            return True
        except Exception as e:
            state.add_log("PROCESSOR", f"❌ Lỗi ẩn source trong Scene '{scene_name}': {str(e)}")
            return False

    def set_source_enabled(self, source_name: str, enabled: bool, scene_name: str = None) -> bool:
        """
        Bật/Tắt một source bất kỳ (Overlay, Banner, Khung viền, Video) trong Scene
        """
        if not self.ensure_connection():
            return False
        scene = scene_name or self.get_current_scene_name()
        if not scene:
            try:
                scene = self.cl.get_current_program_scene().current_program_scene_name
            except Exception:
                pass
        if not scene:
            return False
        try:
            items = self.cl.get_scene_item_list(scene).scene_items
            item_id = next((i['sceneItemId'] for i in items if i.get('sourceName') == source_name), None)
            if item_id is not None:
                self.cl.set_scene_item_enabled(scene, item_id, enabled)
                st = "BẬT" if enabled else "TẮT"
                state.add_log("PROCESSOR", f"👁️ [{st}] Source '{source_name}' (Scene: {scene})")
                return True
            else:
                state.add_log("PROCESSOR", f"⚠️ Không tìm thấy source '{source_name}' trong Scene '{scene}'")
                return False
        except Exception as e:
            state.add_log("PROCESSOR", f"❌ Lỗi đổi trạng thái source '{source_name}': {str(e)}")
            return False

    def get_scene_sources(self, scene_name: str = None) -> list:
        """
        Lấy danh sách tất cả sourceName có trong Scene
        """
        if not self.ensure_connection():
            return []
        scene = scene_name or self.get_current_scene_name()
        if not scene:
            try:
                scene = self.cl.get_current_program_scene().current_program_scene_name
            except Exception:
                pass
        if not scene:
            return []
        try:
            items = self.cl.get_scene_item_list(scene).scene_items
            return [i.get('sourceName', '') for i in items if i.get('sourceName')]
        except Exception as e:
            state.add_log("PROCESSOR", f"❌ Lỗi lấy danh sách source Scene '{scene}': {str(e)}")
            return []

    def bulk_create_sources(self, folder_path: str, source_type: str, file_pattern: str, name_pattern: str, looping: bool = True, visible: bool = True, target_scene: str = None) -> dict:
        """
        Tạo hàng loạt Media/Image Source từ thư mục vào Scene OBS chỉ trong 1 click
        """
        import re, os
        if not self.ensure_connection():
            return {"success": False, "message": "OBS chưa được kết nối!"}
        
        scene = target_scene or self.get_current_scene_name()
        if not scene:
            try:
                scene = self.cl.get_current_program_scene().current_program_scene_name
            except Exception:
                pass
        if not scene:
            return {"success": False, "message": "Chưa chọn Scene OBS để nạp source!"}

        if not os.path.exists(folder_path):
            return {"success": False, "message": f"Thư mục không tồn tại: {folder_path}"}

        match_file = re.search(r'\[(\d+)-(\d+)\]', file_pattern)
        match_name = re.search(r'\[(\d+)-(\d+)\]', name_pattern)
        if not match_file or not match_name:
            return {"success": False, "message": "Sai định dạng khoảng số [đầu-cuối] (ví dụ: base_[1-28])"}

        f_start, f_end = int(match_file.group(1)), int(match_file.group(2))
        n_start, n_end = int(match_name.group(1)), int(match_name.group(2))
        steps = f_end - f_start + 1

        success_count = 0
        failed_count = 0
        folder_files = os.listdir(folder_path)

        for i in range(steps):
            cur_f = f_start + i
            cur_n = n_start + i
            base_file_name = re.sub(r'\[\d+-\d+\]', str(cur_f), file_pattern)
            actual_name = re.sub(r'\[\d+-\d+\]', str(cur_n), name_pattern)

            matched_file = None
            for ext in ['', '.mp4', '.mov', '.mkv', '.avi', '.flv', '.png', '.jpg', '.jpeg', '.webp']:
                test_name = base_file_name if ext == '' else f"{base_file_name}{ext}"
                if test_name in folder_files or os.path.exists(os.path.join(folder_path, test_name)):
                    matched_file = test_name
                    break

            if not matched_file:
                failed_count += 1
                continue

            full_path = os.path.join(folder_path, matched_file)
            try:
                settings = {"local_file": full_path, "looping": looping, "restart_on_activate": True} if source_type == "ffmpeg_source" else {"file": full_path}
                self.cl.create_input(
                    sceneName=scene,
                    inputName=actual_name,
                    inputKind=source_type,
                    inputSettings=settings,
                    sceneItemEnabled=visible
                )
                success_count += 1
            except Exception:
                failed_count += 1

        state.add_log("PROCESSOR", f"🚀 [BULK-CREATE] Đã nạp thành công {success_count} sources vào Scene '{scene}'")
        return {
            "success": True,
            "created_count": success_count,
            "failed_count": failed_count,
            "message": f"Đã tạo thành công {success_count} sources vào Scene '{scene}' (Bỏ qua/Lỗi: {failed_count})"
        }

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

    def get_preview_frame(self, width: int = 360, height: int = 640, quality: int = 70) -> dict:
        """
        Lấy khung hình ảnh xem trước (Live Preview Monitor) thời gian thực từ Program Scene
        """
        if not self.ensure_connection():
            return {"success": False, "message": "Chưa kết nối được tới Stream Processor"}
        try:
            scene_list = self.cl.get_scene_list()
            current_scene = getattr(scene_list, "current_program_scene_name", None)
            if not current_scene:
                return {"success": False, "message": "Chưa có Kịch Bản (Scene) nào được kích hoạt"}

            shot = self.cl.get_source_screenshot(current_scene, "jpg", width, height, quality)
            image_data = getattr(shot, "image_data", None)
            if not image_data:
                return {"success": False, "message": "Không nhận được khung hình từ Stream Processor"}

            return {
                "success": True,
                "scene": current_scene,
                "image": image_data
            }
        except Exception as e:
            return {"success": False, "message": f"Lỗi chụp khung hình preview: {str(e)}"}

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
