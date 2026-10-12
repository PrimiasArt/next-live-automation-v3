from flask import Blueprint, request, jsonify
from core.profile_manager import profile_manager
from core.obs_engine import engine
from core.state import state

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/api/profiles', methods=['GET'])
def get_profiles():
    profiles = profile_manager.list_profiles()
    active_id = state.current_profile.get("id") if state.current_profile else None
    return jsonify({
        "success": True,
        "profiles": profiles,
        "active_profile_id": active_id,
        "is_running": state.is_running
    })

@profile_bp.route('/api/profiles/<profile_id>', methods=['GET'])
def get_profile_detail(profile_id):
    p = profile_manager.get_profile(profile_id)
    if not p:
        return jsonify({"success": False, "message": "Không tìm thấy Profile"}), 404
    return jsonify({"success": True, "profile": p})

@profile_bp.route('/api/scene/select', methods=['POST'])
def select_scene_and_run():
    """
    Chọn Scene từ OBS để bắt đầu chạy:
    1. Quét hoặc lấy Profile tương ứng
    2. Tự động đổi Program Scene trên OBS
    3. Chỉ tắt mắt các source base_xxx
    4. Bắt đầu phát!
    """
    data = request.json or {}
    scene_name = data.get('scene_name', '').strip()

    if not scene_name:
        return jsonify({"success": False, "message": "Vui lòng chọn một Scene trong OBS"}), 400

    engine.ensure_connection()
    # Tìm profile đã có hoặc tự động tạo từ Scene OBS
    profile = profile_manager.create_or_get_profile_for_scene(engine.cl, scene_name)
    if not profile:
        return jsonify({"success": False, "message": f"Không thể nạp dữ liệu cho Scene '{scene_name}'"}), 500

    # Chuyển đổi Scene và bắt đầu phát
    engine.switch_profile(profile, fast_switch=True)
    return jsonify({
        "success": True,
        "message": f"Đã kích hoạt Scene: '{scene_name}'",
        "profile": profile
    })

@profile_bp.route('/api/scene/standby', methods=['POST'])
def set_standby_mode():
    """
    Đưa hệ thống về chế độ chờ (Tạm dừng phát)
    """
    state.set_standby()
    return jsonify({"success": True, "message": "Hệ thống đã về Chế độ Chờ (Standby)"})

@profile_bp.route('/api/profiles/switch', methods=['POST'])
def switch_profile():
    data = request.json or {}
    profile_id = data.get('profile_id')
    fast_switch = data.get('fast_switch', True)

    if not profile_id:
        return jsonify({"success": False, "message": "Thiếu profile_id"}), 400

    new_profile = profile_manager.get_profile(profile_id)
    if not new_profile:
        return jsonify({"success": False, "message": f"Không tìm thấy cấu hình {profile_id}"}), 404

    engine.switch_profile(new_profile, fast_switch=fast_switch)
    return jsonify({
        "success": True,
        "message": f"Đã chuyển sang Profile: {new_profile.get('name')} (Scene OBS: {new_profile.get('scene_name')})",
        "profile": new_profile
    })

@profile_bp.route('/api/profiles/save', methods=['POST'])
def save_profile():
    data = request.json or {}
    name = data.get('name', '').strip()
    scene_name = data.get('scene_name', '').strip()
    videos = data.get('videos', [])

    if not name or not scene_name:
        return jsonify({"success": False, "message": "Vui lòng nhập Tên Brand và Tên Scene trong OBS"}), 400

    if not videos:
        return jsonify({"success": False, "message": "Danh sách video không được để trống"}), 400

    clean_videos = []
    for idx, v in enumerate(videos):
        v_name = v.get('name', f"base_{idx+1}").strip()
        if not v_name.lower().startswith("base_"):
            v_name = f"base_{v_name}"
        v_dur = float(v.get('duration', 30.0))
        v_title = v.get('title', v_name).strip() or v_name
        clean_videos.append({
            "name": v_name,
            "duration": max(0.1, v_dur),
            "title": v_title
        })

    profile_data = {
        "id": data.get('id'),
        "name": name,
        "scene_name": scene_name,
        "overlap_time": float(data.get('overlap_time', 1.0)),
        "videos": clean_videos
    }

    if profile_manager.save_profile(profile_data):
        state.add_log("PROFILE", f"💾 Đã lưu cấu hình Profile: {name} (Scene: {scene_name})")
        
        # Nếu đang là Scene đang active -> Cập nhật và đổi scene ngay
        if state.current_profile and state.current_profile.get("id") == profile_data.get("id"):
            engine.switch_profile(profile_data, fast_switch=True)
            
        return jsonify({"success": True, "profile": profile_data})
    else:
        return jsonify({"success": False, "message": "Lỗi lưu file profile"}), 500

@profile_bp.route('/api/profiles/<profile_id>', methods=['DELETE'])
def delete_profile(profile_id):
    if state.current_profile and profile_id == state.current_profile.get("id"):
        return jsonify({"success": False, "message": "Không thể xóa Profile đang hoạt động!"}), 400

    if profile_manager.delete_profile(profile_id):
        state.add_log("PROFILE", f"🗑️ Đã xóa Profile: {profile_id}")
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Không thể xóa profile này"}), 400

@profile_bp.route('/api/obs/scenes', methods=['GET'])
@profile_bp.route('/api/processor/scenes', methods=['GET'])
def get_obs_scenes():
    engine.ensure_connection()
    result = profile_manager.scan_obs_scenes(engine.cl)
    return jsonify(result)

@profile_bp.route('/api/obs/scene_items', methods=['GET'])
@profile_bp.route('/api/processor/scene_items', methods=['GET'])
def get_obs_scene_items():
    scene_name = request.args.get('scene_name', '').strip()
    if not scene_name:
        return jsonify({"success": False, "message": "Thiếu tham số scene_name"}), 400

    engine.ensure_connection()
    result = profile_manager.scan_scene_items(engine.cl, scene_name)
    return jsonify(result)
