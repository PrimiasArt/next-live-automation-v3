import os
import signal
from flask import Blueprint, request, jsonify
from core.state import state

live_bp = Blueprint('live', __name__)

@live_bp.route('/api/state', methods=['GET'])
def get_state():
    return jsonify(state.to_dict())

@live_bp.route('/api/order', methods=['POST'])
def order_video():
    data = request.json or {}
    video_name = data.get('video_name')
    is_ft = bool(data.get('ft', False))
    
    # Hỗ trợ cả trường hợp gửi số thứ tự val (1-indexed) để tương thích ngược
    raw_val = data.get('val')
    if not video_name and raw_val is not None:
        try:
            idx = int(raw_val) - 1
            videos = state.current_profile.get("videos", [])
            if 0 <= idx < len(videos):
                video_name = videos[idx]["name"]
        except Exception:
            pass

    if not video_name:
        return jsonify({"success": False, "message": "Tên video không hợp lệ"}), 400

    # Kiểm tra xem video_name có trong profile hiện tại không
    current_videos = [v["name"] for v in state.current_profile.get("videos", [])]
    if video_name not in current_videos:
        return jsonify({"success": False, "message": f"Video '{video_name}' không tồn tại trong Brand hiện tại"}), 400

    state.add_task(video_name, is_fast_track=is_ft)
    return jsonify({"success": True, "target": video_name, "fast_track": is_ft})

import re

@live_bp.route('/api/chat/webhook', methods=['POST'])
def chat_webhook():
    """
    Webhook nhận bình luận từ livestream (TikTok, Shopee, FB) hoặc từ Live Chat Simulator.
    Tự động phân tích số/mã sản phẩm và kích hoạt video tương ứng!
    """
    data = request.json or {}
    comment = data.get('comment', '').strip()
    author = data.get('author', 'Khách hàng')
    mode = data.get('mode', 'queue') # 'queue' hoặc 'fast_track'
    is_ft = (mode == 'fast_track')

    if not comment:
        return jsonify({"success": False, "message": "Bình luận trống"}), 400

    if not state.is_running or not state.current_profile:
        return jsonify({"success": False, "message": "Hệ thống đang ở chế độ chờ (Standby)"}), 400

    # Regex nhận diện: 'mẫu 5', 'mã 12', 'áo 3', 'sp 8', 'số 24', '#15', 'b4', hoặc chỉ gõ số '5'
    patterns = [
        r'(?:mẫu|mau|mã|ma|áo|ao|sp|sản phẩm|san pham|số|so|b|#|base[_\s]?)\s*(\d+)',
        r'^\s*(\d+)\s*$'
    ]

    matched_num = None
    for p in patterns:
        m = re.search(p, comment, re.IGNORECASE)
        if m:
            matched_num = int(m.group(1))
            break

    if matched_num is None:
        return jsonify({"success": False, "message": "Không nhận diện được số/mã sản phẩm trong bình luận"}), 200

    videos = state.current_profile.get("videos", [])
    target_video = None

    # Tìm theo thứ tự (1-indexed) hoặc theo tên chứa số đó (ví dụ base_5wp)
    for v in videos:
        vname = v.get("name", "").lower()
        if f"base_{matched_num}" in vname or f"base{matched_num}" in vname:
            target_video = v.get("name")
            break

    if not target_video and 0 < matched_num <= len(videos):
        target_video = videos[matched_num - 1].get("name")

    if not target_video:
        return jsonify({"success": False, "message": f"Không tìm thấy video nào tương ứng với số {matched_num}"}), 200

    state.add_task(target_video, is_fast_track=is_ft)
    action_text = "⚡ FAST TRACK (Phát ngay)" if is_ft else "📥 HÀNG ĐỢI (Queue)"
    state.add_log("AUTO-PILOT", f"🤖 [{author}] \"{comment}\" -> Tự động nhận diện Mã #{matched_num} ({target_video}) -> {action_text}")

    return jsonify({
        "success": True,
        "matched_number": matched_num,
        "target": target_video,
        "fast_track": is_ft,
        "message": f"Đã tự động kích hoạt video '{target_video}'"
    })

@live_bp.route('/api/terminate', methods=['POST'])
def terminate():
    state.add_log("SYSTEM", "🛑 Đã nhận lệnh TERMINATE - Đang đóng tiến trình...")
    os.kill(os.getpid(), signal.SIGTERM)
    return jsonify({"success": True})

