import os
import json
import time
from config import BASE_DIR, PROFILES_DIR
from core.state import state

SCHEME_FILE_PATH = os.path.join(PROFILES_DIR, "scheme.json")

class GroupManager:
    def __init__(self, file_path=SCHEME_FILE_PATH):
        self.file_path = file_path
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            default_data = {
                "groups": [
                    {
                        "id": "group_promo",
                        "name": "Khuyến Mãi & Voucher",
                        "sources": []
                    },
                    {
                        "id": "group_overlay",
                        "name": "Khung Viền & Logo",
                        "sources": []
                    }
                ]
            }
            self._write_data(default_data)

    def _read_data(self) -> dict:
        try:
            if not os.path.exists(self.file_path):
                self._ensure_file()
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return {"groups": []}
                return json.loads(content)
        except Exception as e:
            state.add_log("STORAGE", f"Lỗi đọc scheme.json: {e}")
            return {"groups": []}

    def _write_data(self, data: dict) -> bool:
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            state.add_log("STORAGE", f"Lỗi ghi scheme.json: {e}")
            return False

    def get_all(self) -> list:
        data = self._read_data()
        return data.get("groups", [])

    def add_group(self, name: str) -> dict:
        name = name.strip()
        if not name:
            return {"success": False, "message": "Tên nhóm không được để trống"}
        
        data = self._read_data()
        grp_id = f"grp_{int(time.time() * 1000)}"
        new_grp = {
            "id": grp_id,
            "name": name,
            "sources": []
        }
        data.setdefault("groups", []).append(new_grp)
        if self._write_data(data):
            state.add_log("GROUP", f"📁 Đã tạo nhóm mới: '{name}'")
            return {"success": True, "group": new_grp}
        return {"success": False, "message": "Lỗi lưu file"}

    def rename_group(self, group_id: str, new_name: str) -> dict:
        new_name = new_name.strip()
        if not new_name:
            return {"success": False, "message": "Tên nhóm không được để trống"}
        
        data = self._read_data()
        for g in data.get("groups", []):
            if g["id"] == group_id:
                old = g["name"]
                g["name"] = new_name
                self._write_data(data)
                state.add_log("GROUP", f"✏️ Đổi tên nhóm: '{old}' -> '{new_name}'")
                return {"success": True}
        return {"success": False, "message": "Không tìm thấy nhóm"}

    def delete_group(self, group_id: str, engine=None) -> dict:
        data = self._read_data()
        groups = data.get("groups", [])
        target = next((g for g in groups if g["id"] == group_id), None)
        if not target:
            return {"success": False, "message": "Không tìm thấy nhóm"}

        # Nếu có source đang bật trong nhóm này, tắt nó trên OBS
        active_src = state.active_sources_by_group.get(group_id)
        if active_src and engine:
            engine.set_source_enabled(active_src, False)
        state.remove_group_active_source(group_id)

        data["groups"] = [g for g in groups if g["id"] != group_id]
        self._write_data(data)
        state.add_log("GROUP", f"🗑️ Đã xóa nhóm: '{target['name']}'")
        return {"success": True}

    def add_source(self, group_id: str, source_name: str, thumb: str = "") -> dict:
        source_name = source_name.strip()
        if not source_name:
            return {"success": False, "message": "Tên source không được để trống"}
            
        data = self._read_data()
        for g in data.get("groups", []):
            if g["id"] == group_id:
                if any(s["name"] == source_name for s in g.get("sources", [])):
                    return {"success": False, "message": "Source này đã tồn tại trong nhóm"}
                g.setdefault("sources", []).append({
                    "name": source_name,
                    "thumb": thumb
                })
                self._write_data(data)
                state.add_log("GROUP", f"➕ Đã thêm source [{source_name}] vào nhóm [{g['name']}]")
                return {"success": True}
        return {"success": False, "message": "Không tìm thấy nhóm"}

    def delete_source(self, group_id: str, source_name: str, engine=None) -> dict:
        source_name = source_name.strip()
        data = self._read_data()
        for g in data.get("groups", []):
            if g["id"] == group_id:
                g["sources"] = [s for s in g.get("sources", []) if s["name"] != source_name]
                self._write_data(data)
                
                # Nếu source đang bật, tắt trên OBS
                if state.active_sources_by_group.get(group_id) == source_name:
                    if engine:
                        engine.set_source_enabled(source_name, False)
                    state.remove_group_active_source(group_id)
                    
                state.add_log("GROUP", f"🗑️ Đã xóa source [{source_name}] khỏi nhóm [{g['name']}]")
                return {"success": True}
        return {"success": False, "message": "Không tìm thấy source hoặc nhóm"}

    def upload_thumb(self, group_id: str, source_name: str, thumb_data: str) -> dict:
        if not group_id or not source_name or not thumb_data:
            return {"success": False, "message": "Thiếu dữ liệu ảnh"}
            
        data = self._read_data()
        for g in data.get("groups", []):
            if g["id"] == group_id:
                for s in g.get("sources", []):
                    if s["name"] == source_name:
                        s["thumb"] = thumb_data
                        self._write_data(data)
                        state.add_log("GROUP", f"🖼️ Đã cập nhật ảnh thumbnail cho [{source_name}]")
                        return {"success": True}
        return {"success": False, "message": "Không tìm thấy source"}

group_manager = GroupManager()
