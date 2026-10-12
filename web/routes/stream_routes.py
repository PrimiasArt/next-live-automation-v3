from flask import Blueprint, request, jsonify
from core.obs_engine import engine
from core.state import state
from core.stream_process_manager import process_manager

stream_bp = Blueprint('stream', __name__)

@stream_bp.route('/api/stream/settings', methods=['GET'])
def get_stream_settings():
    res = engine.get_stream_settings()
    return jsonify(res)

@stream_bp.route('/api/stream/settings', methods=['POST'])
def set_stream_settings():
    data = request.json or {}
    server = data.get('server', '').strip()
    key = data.get('key', '').strip()
    service_type = data.get('service_type', 'rtmp_custom')

    if not server:
        return jsonify({"success": False, "message": "Vui lòng nhập RTMP Server URL"}), 400

    res = engine.set_stream_settings(server=server, key=key, service_type=service_type)
    status_code = 200 if res.get("success") else 500
    return jsonify(res), status_code

@stream_bp.route('/api/stream/status', methods=['GET'])
def get_stream_status():
    status = engine.get_stream_status()
    return jsonify({"success": True, **status})

@stream_bp.route('/api/stream/start', methods=['POST'])
def start_stream():
    res = engine.start_streaming()
    status_code = 200 if res.get("success") else 500
    return jsonify(res), status_code

@stream_bp.route('/api/stream/stop', methods=['POST'])
def stop_stream():
    res = engine.stop_streaming()
    status_code = 200 if res.get("success") else 500
    return jsonify(res), status_code

@stream_bp.route('/api/obs/video_settings', methods=['GET'])
@stream_bp.route('/api/processor/video_settings', methods=['GET'])
def get_video_settings():
    res = engine.get_video_settings()
    status_code = 200 if res.get("success") else 500
    return jsonify(res), status_code

@stream_bp.route('/api/obs/video_settings', methods=['POST'])
@stream_bp.route('/api/processor/video_settings', methods=['POST'])
def set_video_settings():
    data = request.json or {}
    base_w = int(data.get('base_width', 1080))
    base_h = int(data.get('base_height', 1920))
    out_w = int(data.get('output_width', 1080))
    out_h = int(data.get('output_height', 1920))
    fps = int(data.get('fps', 30))

    res = engine.set_video_settings(
        base_width=base_w,
        base_height=base_h,
        output_width=out_w,
        output_height=out_h,
        fps_numerator=fps,
        fps_denominator=1
    )
    status_code = 200 if res.get("success") else 400
    return jsonify(res), status_code

@stream_bp.route('/api/obs/output_settings', methods=['GET'])
@stream_bp.route('/api/processor/output_settings', methods=['GET'])
def get_output_settings():
    res = engine.get_output_parameters()
    status_code = 200 if res.get("success") else 500
    return jsonify(res), status_code

@stream_bp.route('/api/obs/output_settings', methods=['POST'])
@stream_bp.route('/api/processor/output_settings', methods=['POST'])
def set_output_settings():
    data = request.json or {}
    vbitrate = data.get('video_bitrate')
    abitrate = data.get('audio_bitrate')
    encoder = data.get('video_encoder')
    sample_rate = data.get('sample_rate')
    channels = data.get('channels')

    res = engine.set_output_parameters(
        video_bitrate=vbitrate,
        audio_bitrate=abitrate,
        video_encoder=encoder,
        sample_rate=sample_rate,
        channels=channels
    )
    status_code = 200 if res.get("success") else 400
    return jsonify(res), status_code

@stream_bp.route('/api/settings/overlap', methods=['GET', 'POST'])
def handle_overlap_settings():
    if request.method == 'GET':
        overlap = engine.get_current_overlap_time()
        return jsonify({"success": True, "overlap_time": overlap})
    data = request.json or {}
    try:
        overlap = float(data.get('overlap_time', 1.0))
        if state.current_profile:
            state.current_profile['overlap_time'] = overlap
        state.add_log("SETTINGS", f"⏱️ Đã cập nhật Overlap Transition: {overlap}s")
        return jsonify({"success": True, "overlap_time": overlap})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@stream_bp.route('/api/stream/preview', methods=['GET'])
def get_stream_preview():
    w = int(request.args.get('w', 360))
    h = int(request.args.get('h', 640))
    q = int(request.args.get('q', 70))
    res = engine.get_preview_frame(width=w, height=h, quality=q)
    status_code = 200 if res.get("success") else 400
    return jsonify(res), status_code

@stream_bp.route('/api/processor/status', methods=['GET'])
def get_processor_status():
    status = process_manager.get_status()
    status["connected"] = engine.ensure_connection()
    return jsonify(status)

@stream_bp.route('/api/processor/start', methods=['POST'])
def start_processor():
    res = process_manager.start_processor()
    if res.get("success"):
        engine.connect_obs(auto_launch=False)
    status_code = 200 if res.get("success") else 500
    return jsonify(res), status_code

@stream_bp.route('/api/processor/stop', methods=['POST'])
def stop_processor():
    res = process_manager.stop_processor()
    status_code = 200 if res.get("success") else 500
    return jsonify(res), status_code

@stream_bp.route('/api/processor/restart', methods=['POST'])
def restart_processor():
    res = process_manager.restart_processor()
    if res.get("success"):
        engine.connect_obs(auto_launch=False)
    status_code = 200 if res.get("success") else 500
    return jsonify(res), status_code
