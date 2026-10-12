from flask import Blueprint, request, jsonify
from core.state import state
from core.obs_engine import engine
from core.group_manager import group_manager

group_bp = Blueprint('group', __name__)

@group_bp.route('/api/groups', methods=['GET'])
def get_groups():
    groups = group_manager.get_all()
    return jsonify({
        "success": True,
        "groups": groups,
        "active_sources": state.active_sources_by_group
    })

@group_bp.route('/api/groups/add', methods=['POST'])
def add_group():
    data = request.json or {}
    name = data.get('name', '').strip()
    res = group_manager.add_group(name)
    return jsonify(res)

@group_bp.route('/api/groups/rename', methods=['POST'])
def rename_group():
    data = request.json or {}
    group_id = data.get('group_id')
    name = data.get('name', '').strip()
    res = group_manager.rename_group(group_id, name)
    return jsonify(res)

@group_bp.route('/api/groups/delete', methods=['POST'])
def delete_group():
    data = request.json or {}
    group_id = data.get('group_id')
    res = group_manager.delete_group(group_id, engine=engine)
    return jsonify(res)

@group_bp.route('/api/groups/source/add', methods=['POST'])
def add_source():
    data = request.json or {}
    group_id = data.get('group_id')
    name = data.get('name', '').strip()
    thumb = data.get('thumb', '')
    res = group_manager.add_source(group_id, name, thumb)
    return jsonify(res)

@group_bp.route('/api/groups/source/delete', methods=['POST'])
def delete_source():
    data = request.json or {}
    group_id = data.get('group_id')
    name = data.get('name', '').strip()
    res = group_manager.delete_source(group_id, name, engine=engine)
    return jsonify(res)

@group_bp.route('/api/groups/source/upload_thumb', methods=['POST'])
def upload_thumb():
    data = request.json or {}
    group_id = data.get('group_id')
    name = data.get('name', '').strip()
    thumb = data.get('thumb', '')
    res = group_manager.upload_thumb(group_id, name, thumb)
    return jsonify(res)

@group_bp.route('/api/groups/source/toggle', methods=['POST'])
def toggle_source():
    data = request.json or {}
    group_id = data.get('group_id')
    name = data.get('name', '').strip()

    if not group_id or not name:
        return jsonify({"success": False, "message": "Thiếu group_id hoặc tên source"}), 400

    groups = group_manager.get_all()
    target_grp = next((g for g in groups if g["id"] == group_id), None)
    if not target_grp:
        return jsonify({"success": False, "message": "Không tìm thấy nhóm"}), 404

    current_active = state.active_sources_by_group.get(group_id, "")

    if current_active == name:
        # Tắt source đang bật
        engine.set_source_enabled(name, False)
        state.remove_group_active_source(group_id)
        state.add_log("GROUP", f"⚪ [TẮT] {name} ({target_grp['name']})")
    else:
        # Tắt tất cả các source khác trong nhóm này (cơ chế exclusive)
        for s in target_grp.get("sources", []):
            if s["name"] != name:
                engine.set_source_enabled(s["name"], False)
                
        # Bật source được chọn
        success = engine.set_source_enabled(name, True)
        if success:
            state.set_group_active_source(group_id, name)
            state.add_log("GROUP", f"🎯 [KÍCH HOẠT] {name} ({target_grp['name']})")
        else:
            state.add_log("OBS", f"⚠️ Không thể bật '{name}' trên OBS. Đảm bảo tên trùng khớp trong Scene.")

    return jsonify({
        "success": True,
        "active_sources": state.active_sources_by_group
    })
