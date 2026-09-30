import obsws_python as obs
import time, random, sys, threading, datetime, webbrowser, os, signal, hashlib, json
import requests
from collections import deque
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SCHEME_FILE_PATH = os.path.join(BASE_DIR, "scheme.txt")
CONFIG_FILE_PATH = os.path.join(BASE_DIR, "config_bases.json")

# --- CẤU HÌNH OBS ---
OBS_HOST, OBS_PORT = '127.0.0.1', 4455
TARGET_SCENE = "IP One"
OVERLAP_TIME = 1.0

# --- CẤU HÌNH SUPABASE CLOUD (GÁN CỨNG TRONG CODE) ---
SUPABASE_URL = "https://frredpdjfmafluafkrmr.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZycmVkcGRqZm1hZmx1YWZrcm1yIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg3Mzk1NTAsImV4cCI6MjA5NDMxNTU1MH0.Rxd8dz_hZxZjqn6uyoStofhMtA2tEKFVxpsQa3e59Xo"

# --- QUẢN LÝ DỮ LIỆU BASE & DURATIONS ĐỘNG ---
def load_dynamic_config():
    default_durations = [
        27.80, 30.83, 27.60, 30.83, 27.93,
        24.80, 27.53, 22.30, 24.40, 25.43,
        24.37, 22.80, 24.77, 22.80, 30.13
    ]
    if not os.path.exists(CONFIG_FILE_PATH):
        # Khởi tạo mặc định nếu chưa có file config
        data = {
            "prefix": "base_",
            "suffix": "ip",
            "durations": default_durations
        }
        save_dynamic_config(data)
        return data
    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return {"prefix": "base_", "suffix": "ip", "durations": default_durations}
            return json.loads(content)
    except Exception:
        return {"prefix": "base_", "suffix": "ip", "durations": default_durations}

def save_dynamic_config(data):
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def get_current_base_setup():
    cfg = load_dynamic_config()
    prefix = cfg.get("prefix", "base_")
    suffix = cfg.get("suffix", "ip")
    durations = cfg.get("durations", [])
    
    base_list = [{"name": f"{prefix}{i+1}{suffix}", "duration": durations[i]} for i in range(len(durations))]
    durations_map = {f"{prefix}{i+1}{suffix}": durations[i] for i in range(len(durations))}
    return base_list, durations_map, len(durations), prefix, suffix

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*", "methods": ["POST", "GET", "OPTIONS"], "allow_headers": ["Content-Type"]}})

web_logs = deque(maxlen=30)
state = {
    "is_authorized": False, 
    "current_video": "System Locked", 
    "remaining": 0.0,
    "task_queue": deque(maxlen=30),  
    "api_key_id": None,
    "quota_remaining": 0,
    "active_sources_by_group": {}
}

global_engine = None

def add_web_log(tag, message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    web_logs.append(f"[{timestamp}] [{tag}] {message}")

def read_groups_data():
    default_structure = {
        "groups": [
            {
                "id": "group_product",
                "name": "Sản phẩm khuyến mãi",
                "sources": []
            }
        ]
    }
    if not os.path.exists(SCHEME_FILE_PATH):
        write_groups_data(default_structure)
        return default_structure
    try:
        with open(SCHEME_FILE_PATH, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return default_structure
            data = json.loads(content)
            if "groups" not in data:
                return default_structure
            return data
    except Exception as e:
        add_web_log("STORAGE", f"Đọc scheme.txt lỗi, khởi tạo lại: {e}")
        return default_structure

def write_groups_data(data):
    try:
        with open(SCHEME_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        add_web_log("STORAGE", f"Lỗi ghi scheme.txt: {e}")
        return False

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>HLC CLOUD | MULTI-GROUP MANAGER & SETUP SUITE</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {
            background-color: #FAF4E6;
            color: #1A1815;
            font-family: sans-serif;
            overflow-x: hidden;
            transition: background-color 0.25s ease, color 0.25s ease;
        }
        .theme-subtext { color: #5C5446; }
        .theme-glass {
            background: #FFFDF7;
            border: 1px solid #E6DCC7;
            box-shadow: 0 4px 18px rgba(92, 70, 30, 0.06);
        }
        .theme-monitor-border { border-left: 4px solid #1075E6; }
        .theme-neon-text {
            color: #0A63C9;
            text-shadow: 0 0 10px rgba(10, 99, 201, 0.25);
        }
        .theme-base-node {
            height: 45px;
            border-radius: 6px;
            background: #F3EBD8;
            border: 1px solid #DFD5BE;
            color: #2E2619;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
        }
        .theme-base-node:hover {
            border-color: #0A63C9;
            background: #E8DDCA;
            color: #0A63C9;
            transform: translateY(-1px);
        }
        .theme-base-active {
            background: #0A63C9 !important;
            color: #FFFFFF !important;
            box-shadow: 0 0 16px rgba(10, 99, 201, 0.45);
            border: none;
            font-weight: bold;
        }
        .theme-terminal {
            font-family: 'Courier New', Courier, monospace;
            background: #191612;
            border: 1px solid #2B241C;
            color: #48E084;
        }
        .theme-progress-track { background-color: #E6DCC7; }
        .theme-queue-empty { color: #8A7E6B; }
        .theme-ft-btn {
            border: 1px solid #B8AB91;
            color: #4A4031;
            background: transparent;
        }
        .theme-ft-btn:hover { background: #EFE4D0; }
        .theme-ft-btn-active {
            border-color: #D97706 !important;
            background: #FEF3C7 !important;
            color: #92400E !important;
            box-shadow: 0 0 10px rgba(217, 119, 6, 0.25);
        }
        .theme-quota-box { border: 1px solid #E0CEAB; background: #FAF0DA; }
        .theme-quota-num { color: #B45309; }
        
        .theme-scheme-item {
            background: #F3EBD8;
            border: 1px solid #DFD5BE;
        }
        .theme-scheme-item.active-scheme {
            border-color: #10B981 !important;
            background: #ECFDF5 !important;
            box-shadow: 0 0 14px rgba(16, 185, 129, 0.25);
        }
        .scheme-thumb-container {
            width: 100%;
            height: 95px;
            background: #E8DDCA;
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }

        /* Tab Styling */
        .tab-btn {
            padding: 10px 20px;
            font-weight: bold;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: all 0.2s;
        }
        .tab-btn.active {
            border-bottom: 3px solid #0A63C9;
            color: #0A63C9;
        }

        body.dark {
            background-color: #050505;
            color: #e0e0e0;
        }
        body.dark .theme-subtext { color: #6b7280; }
        body.dark .theme-glass {
            background: rgba(20, 20, 20, 0.9);
            border: 1px solid #333;
            box-shadow: none;
        }
        body.dark .theme-monitor-border { border-left: 4px solid #3b82f6; }
        body.dark .theme-neon-text {
            color: #1fb6ff;
            text-shadow: 0 0 10px #1fb6ff;
        }
        body.dark .theme-base-node {
            background: #111;
            border: 1px solid #222;
            color: #e0e0e0;
        }
        body.dark .theme-base-node:hover {
            border-color: #1fb6ff;
            background: #161b22;
            color: #1fb6ff;
            transform: none;
        }
        body.dark .theme-base-active {
            background: #1fb6ff !important;
            color: #000000 !important;
            box-shadow: 0 0 20px #1fb6ff;
            border: none;
        }
        body.dark .theme-terminal {
            background: #0a0a0a;
            border: 1px solid #222;
            color: #34d399;
        }
        body.dark .theme-progress-track { background-color: #1f2937; }
        body.dark .theme-queue-empty { color: #4b5563; }
        body.dark .theme-ft-btn {
            border: 1px solid #4b5563;
            color: #9ca3af;
            background: transparent;
        }
        body.dark .theme-ft-btn:hover { background: #1f2937; }
        body.dark .theme-ft-btn-active {
            border-color: #f59e0b !important;
            background: transparent !important;
            color: #f59e0b !important;
            box-shadow: 0 0 10px #f59e0b33;
        }
        body.dark .theme-quota-box { border: 1px solid rgba(202, 138, 4, 0.3); background: rgba(20, 20, 20, 0.9); }
        body.dark .theme-quota-num { color: #eab308; }
        body.dark .theme-scheme-item {
            background: #151515;
            border: 1px solid #262626;
        }
        body.dark .theme-scheme-item.active-scheme {
            border-color: #10B981 !important;
            background: rgba(16, 185, 129, 0.1) !important;
        }
        body.dark .scheme-thumb-container {
            background: #0d0d0d;
        }
        body.dark .tab-btn.active {
            border-bottom: 3px solid #1fb6ff;
            color: #1fb6ff;
        }
    </style>
</head>
<body class="p-8">
    <div id="auth" class="fixed inset-0 bg-black/90 flex items-center justify-center z-50 {{ 'hidden' if is_authorized else '' }}">
        <div class="theme-glass p-10 rounded-2xl w-[28rem] text-center border-t-4 border-blue-500 shadow-2xl">
            <h1 class="text-3xl font-black theme-neon-text mb-2">HLC CLOUD</h1>
            <p class="theme-subtext text-xs mb-6 font-semibold">HỆ THỐNG ĐIỀU KHIỂN THỜI GIAN LIVE STREAM</p>
            
            <input type="password" id="key-input" autocomplete="new-password" value="" class="w-full p-3 bg-neutral-900 border border-neutral-700 text-white rounded mb-4 text-center outline-none focus:border-blue-500 tracking-widest font-mono text-sm" placeholder="NHẬP CLOUD API KEY">
            <button onclick="validateCloudKey()" class="w-full p-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded uppercase tracking-wider transition-all cursor-pointer">KÍCH HOẠT HỆ THỐNG</button>
            <p id="error-msg" class="text-red-500 mt-4 text-xs hidden font-bold"></p>
        </div>
    </div>

    <!-- Modal Dropdown chọn Source trực tiếp từ OBS -->
    <div id="source-modal" class="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 hidden">
        <div class="theme-glass p-6 rounded-2xl w-[26rem] border-t-4 border-emerald-500 shadow-2xl">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-sm font-black uppercase text-emerald-600 dark:text-emerald-400">Chọn Source từ OBS</h3>
                <button onclick="closeSourceModal()" class="text-xs text-gray-500 hover:text-red-500 font-bold">✕</button>
            </div>
            <p class="theme-subtext text-xs mb-3">Danh sách source tự động quét từ Scene: <b class="text-blue-500">IP One</b></p>
            
            <div class="mb-4">
                <select id="obs-source-select" class="w-full p-2.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-xs font-bold outline-none focus:border-emerald-500">
                    <option value="">Đang tải danh sách source từ OBS...</option>
                </select>
            </div>

            <div class="flex gap-2">
                <button onclick="submitSelectSource()" class="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg text-xs transition cursor-pointer">
                    Thêm vào nhóm
                </button>
                <button onclick="closeSourceModal()" class="px-4 py-2 rounded-lg border border-neutral-300 dark:border-neutral-700 text-xs font-bold transition cursor-pointer">
                    Hủy
                </button>
            </div>
        </div>
    </div>

    <!-- Modal Trang Cài Đặt (Setup Suite Modal khi bấm icon Bánh Răng) -->
    <div id="setup-modal" class="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center z-50 hidden">
        <div class="theme-glass p-6 rounded-2xl w-[55rem] max-h-[90vh] flex flex-col border-t-4 border-amber-500 shadow-2xl">
            <div class="flex justify-between items-center pb-3 border-b border-neutral-300 dark:border-neutral-800">
                <h2 class="text-lg font-black uppercase text-amber-600 dark:text-amber-500 flex items-center gap-2">
                    <span>⚙️ Cài Đặt & Quản Lý Hệ Thống (Setup Suite)</span>
                </h2>
                <button onclick="closeSetupModal()" class="text-sm font-bold text-neutral-500 hover:text-red-500 cursor-pointer">✕ Đóng</button>
            </div>

            <!-- Tab Navigation bên trong Modal -->
            <div class="flex border-b border-neutral-300 dark:border-neutral-800 mt-3">
                <div class="tab-btn active" onclick="switchSetupTab('tab-obs-bulk', this)">🚀 OBS Bulk Creator</div>
                <div class="tab-btn" onclick="switchSetupTab('tab-durations', this)">⏱️ Cấu hình Thời Lượng & Base</div>
            </div>

            <!-- Nội dung Tab 1: OBS Bulk Creator & Rename -->
            <div id="tab-obs-bulk" class="setup-tab-content overflow-y-auto flex-grow p-4 space-y-4 max-h-[65vh]">
                <div class="bg-blue-50 dark:bg-neutral-900 p-4 rounded-xl border border-blue-200 dark:border-neutral-800 space-y-3">
                    <h3 class="font-bold text-xs uppercase text-blue-700 dark:text-blue-400">1. Tạo Source & Media Hàng Loạt từ Thư Mục</h3>
                    <div class="grid grid-cols-2 gap-3 text-xs">
                        <div>
                            <label class="font-semibold block mb-1">Đường dẫn thư mục chứa video:</label>
                            <input type="text" id="bulk-folder" class="w-full p-2 rounded border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800" placeholder="VD: D:\Videos">
                        </div>
                        <div>
                            <label class="font-semibold block mb-1">Loại Source:</label>
                            <select id="bulk-type" class="w-full p-2 rounded border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800">
                                <option value="ffmpeg_source">Media Source (Video/Audio)</option>
                                <option value="image_source">Image (Hình ảnh)</option>
                            </select>
                        </div>
                        <div>
                            <label class="font-semibold block mb-1">Mẫu tên file gốc (Hỗ trợ [đầu-cuối]):</label>
                            <input type="text" id="bulk-file-pattern" value="base_[1-15]" class="w-full p-2 rounded border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800">
                        </div>
                        <div>
                            <label class="font-semibold block mb-1">Mẫu đặt tên Source mới trên OBS:</label>
                            <input type="text" id="bulk-name-pattern" value="base_[1-15]ip" class="w-full p-2 rounded border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800">
                        </div>
                    </div>
                    <div class="flex items-center gap-4 text-xs pt-2">
                        <label class="flex items-center gap-1 cursor-pointer"><input type="checkbox" id="bulk-loop" checked> Lặp lại (Loop)</label>
                        <label class="flex items-center gap-1 cursor-pointer"><input type="checkbox" id="bulk-visible" checked> Hiển thị ngay (Mắt mở)</label>
                        <button onclick="runBulkCreate()" class="ml-auto px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded cursor-pointer">Bắt đầu tạo hàng loạt</button>
                    </div>
                </div>

                <div class="bg-neutral-100 dark:bg-neutral-900 p-4 rounded-xl border border-neutral-300 dark:border-neutral-800 space-y-3 text-xs">
                    <h3 class="font-bold text-xs uppercase text-amber-600 dark:text-amber-500">2. Công Cụ Đổi Tên Source Hàng Loạt</h3>
                    <div class="flex gap-2 items-center">
                        <input type="text" id="rename-find" placeholder="Tìm chuỗi (VD: base_)" class="flex-1 p-2 rounded border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800">
                        <input type="text" id="rename-replace" placeholder="Thay bằng (VD: v_) class="flex-1 p-2 rounded border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800">
                        <button onclick="executeRename()" class="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white font-bold rounded cursor-pointer">Đổi tên toàn bộ</button>
                    </div>
                </div>
            </div>

            <!-- Nội dung Tab 2: Quét Thời Lượng & Cấu Hình Base -->
            <div id="tab-durations" class="setup-tab-content overflow-y-auto flex-grow p-4 space-y-4 max-h-[65vh] hidden">
                <div class="bg-emerald-50 dark:bg-neutral-900 p-4 rounded-xl border border-emerald-200 dark:border-neutral-800 space-y-3 text-xs">
                    <h3 class="font-bold uppercase text-emerald-700 dark:text-emerald-400">Tự Động Quét Thời Lượng Video (mp4_duration_v7)</h3>
                    <div class="flex gap-2">
                        <input type="text" id="scan-folder-path" placeholder="Nhập đường dẫn thư mục chứa video cần quét thời lượng..." class="flex-1 p-2 rounded border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800">
                        <button onclick="scanVideoDurations()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded cursor-pointer">⚡ Quét & Lưu Vào Hệ Thống</button>
                    </div>
                    <p class="text-neutral-500 italic">Hệ thống sẽ tự động quét các file .mp4, .mov trong thư mục, đo chính xác thời lượng từng video bằng MediaInfo và cập nhật động vào mảng chạy của ứng dụng.</p>
                </div>

                <div class="theme-glass p-4 rounded-xl space-y-2 text-xs">
                    <h3 class="font-bold uppercase text-blue-600 dark:text-blue-400">Danh Sách Thời Lượng Base Hiện Tại</h3>
                    <div id="durations-preview-box" class="p-3 bg-neutral-900 text-emerald-400 font-mono rounded max-h-40 overflow-y-auto">
                        Đang tải dữ liệu...
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="max-w-7xl mx-auto">
        <header class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-4xl font-black theme-neon-text">HLC <span class="text-current">CLOUD v15.0</span></h1>
                <p class="theme-subtext text-xs mt-1 font-medium">STATION: NAKAMURA | MULTI-GROUP SOURCE SYSTEM</p>
            </div>
            
            <div class="flex gap-3 items-center">
                <button onclick="openSetupModal()" class="theme-glass px-3.5 py-2 rounded-xl flex items-center gap-2 text-xs font-bold transition cursor-pointer hover:border-amber-500">
                    <span>⚙️ Cài đặt</span>
                </button>

                <button onclick="toggleTheme()" class="theme-glass px-3.5 py-2 rounded-xl flex items-center gap-2 text-xs font-bold transition cursor-pointer hover:border-blue-500">
                    <span id="theme-icon">🌙</span>
                    <span id="theme-text">Dark Mode</span>
                </button>

                <div class="theme-quota-box px-4 py-2 rounded-xl">
                    <span class="theme-subtext text-[10px] uppercase font-bold block tracking-wider">Quota Credits</span>
                    <span id="cloud-quota" class="theme-quota-num font-extrabold font-mono text-sm">0 Credits</span>
                </div>
                
                <button onclick="terminate()" class="bg-red-900/20 hover:bg-red-600 text-red-600 dark:text-red-400 hover:text-white px-4 py-2.5 rounded-xl text-xs font-bold border border-red-500/40 transition cursor-pointer">TERMINATE CORE</button>
            </div>
        </header>

        <div class="grid grid-cols-4 gap-6">
            <div class="col-span-3 space-y-6">
                <div class="theme-glass p-8 rounded-2xl theme-monitor-border">
                    <div class="flex justify-between items-end mb-4">
                        <div>
                            <span class="theme-subtext text-xs uppercase tracking-wider font-bold">Active Output Pipeline</span>
                            <h2 id="vid" class="text-5xl font-black mt-1">--</h2>
                        </div>
                        <div id="timer" class="text-5xl font-mono text-amber-500 dark:text-yellow-500 font-bold">0.0s</div>
                    </div>
                    <div class="w-full theme-progress-track h-2.5 rounded-full overflow-hidden">
                        <div id="bar" class="bg-blue-600 h-full transition-all duration-100" style="width:0%"></div>
                    </div>
                </div>

                <div class="theme-glass p-6 rounded-2xl">
                    <div class="flex justify-between mb-4 items-center">
                        <span class="theme-subtext text-xs uppercase font-bold tracking-wider" id="matrix-title">VIDEO MATRIX GRID (DYNAMIC AUTO-LOOP)</span>
                        <button id="ft-btn" onclick="toggleFT()" class="theme-ft-btn px-4 py-1.5 rounded-full text-[10px] font-bold uppercase transition cursor-pointer">⚡ FAST TRACK: <span id="ft-st">OFF</span></button>
                    </div>
                    <!-- Matrix Grid hiển thị linh động tùy thuộc số lượng base -->
                    <div id="base-matrix-grid" class="grid grid-cols-10 gap-2"></div>
                </div>

                <div class="space-y-6">
                    <div class="flex justify-between items-center bg-transparent px-1">
                        <div>
                            <h3 class="text-lg font-black uppercase tracking-wider text-emerald-600 dark:text-emerald-400">Các Cụm Source OBS Độc Lập</h3>
                            <p class="theme-subtext text-xs">Mỗi nhóm hoạt động độc quyền riêng lẻ (ví dụ đổi Background không làm tắt TVC hay Podium).</p>
                        </div>
                        <button onclick="createNewGroup()" class="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-md">
                            <span>+ Thêm Nhóm Mới</span>
                        </button>
                    </div>

                    <div id="groups-container" class="space-y-6"></div>
                </div>
            </div>

            <div class="col-span-1 flex flex-col gap-6">
                <div class="theme-glass p-5 rounded-2xl flex flex-col h-64 overflow-hidden">
                    <div class="flex justify-between items-center mb-3">
                        <h3 class="theme-neon-text text-xs font-bold uppercase tracking-wider">Next Queue</h3>
                        <button onclick="clearAllQueue()" title="Xóa toàn bộ hàng chờ" class="text-[10px] text-red-500 hover:text-red-700 dark:text-red-400 font-bold underline cursor-pointer">Clear All</button>
                    </div>
                    <div id="ql" class="flex flex-col gap-2 overflow-y-auto pr-1 flex-grow"></div>
                </div>

                <div class="theme-glass p-5 rounded-2xl flex flex-col h-72 overflow-hidden border-t-2 border-amber-500">
                    <h3 class="text-amber-600 dark:text-amber-500 text-xs font-bold mb-3 uppercase tracking-wider flex justify-between items-center">
                        <span>📡 Live Reception Logs</span>
                        <span class="animate-pulse text-[9px] bg-amber-500/20 px-2 py-0.5 rounded text-amber-700 dark:text-amber-400 font-bold">CONSOLE OUT</span>
                    </h3>
                    <div id="log-box" class="theme-terminal p-3 rounded-lg text-[10px] overflow-y-auto flex-grow space-y-1.5 scrollbar-thin select-text">
                        <div class="opacity-50 italic">Awaiting connection pipeline...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <input type="file" id="scheme-file-input" class="hidden" accept="image/*" onchange="handleImageSelected(event)" />

    <script>
        let ft = false;
        let currentUploadTargetGroup = null;
        let currentUploadTargetSource = null;
        let currentTargetGroupIdForAdd = null;

        window.addEventListener('DOMContentLoaded', () => {
            const input = document.getElementById('key-input');
            if (input) input.value = '';
            loadDynamicSetupInfo();
        });

        // --- QUẢN LÝ SETUP MODAL & TABS ---
        function openSetupModal() {
            document.getElementById('setup-modal').classList.remove('hidden');
            loadDynamicSetupInfo();
        }

        function closeSetupModal() {
            document.getElementById('setup-modal').classList.add('hidden');
            loadGroups();
            updateCycle();
        }

        function switchSetupTab(tabId, btnElement) {
            document.querySelectorAll('.setup-tab-content').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.remove('hidden');
            btnElement.classList.add('active');
        }

        async function loadDynamicSetupInfo() {
            try {
                const res = await fetch('/api/config/get');
                const data = await res.json();
                if(data.success) {
                    document.getElementById('durations-preview-box').innerText = JSON.stringify(data.durations, null, 2);
                }
            } catch(e) {}
        }

        async function scanVideoDurations() {
            const folder = document.getElementById('scan-folder-path').value.trim();
            if(!folder) {
                alert("Vui lòng nhập đường dẫn thư mục video!");
                return;
            }
            const res = await fetch('/api/config/scan', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({folder_path: folder})
            });
            const d = await res.json();
            if(d.success) {
                alert(d.message);
                loadDynamicSetupInfo();
            } else {
                alert("Lỗi: " + d.message);
            }
        }

        async function runBulkCreate() {
            const folder = document.getElementById('bulk-folder').value.trim();
            const type = document.getElementById('bulk-type').value;
            const filePattern = document.getElementById('bulk-file-pattern').value.trim();
            const namePattern = document.getElementById('bulk-name-pattern').value.trim();
            const looping = document.getElementById('bulk-loop').checked;
            const visible = document.getElementById('bulk-visible').checked;

            if(!folder) {
                alert("Vui lòng nhập thư mục nguồn!");
                return;
            }

            const res = await fetch('/api/obs/bulk_create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    folder_path: folder,
                    source_type: type,
                    file_pattern: filePattern,
                    name_pattern: namePattern,
                    looping: looping,
                    visible: visible
                })
            });
            const d = await res.json();
            alert(d.message);
        }

        async function executeRename() {
            const findStr = document.getElementById('rename-find').value.trim();
            const replaceStr = document.getElementById('rename-replace').value.trim();
            if(!findStr) {
                alert("Vui lòng nhập chuỗi cần tìm!");
                return;
            }
            const res = await fetch('/api/obs/rename', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({find: findStr, replace: replaceStr})
            });
            const d = await res.json();
            alert(d.message);
        }

        function applyTheme(isDark) {
            const body = document.body;
            const icon = document.getElementById('theme-icon');
            const label = document.getElementById('theme-text');
            if (isDark) {
                body.classList.add('dark');
                icon.innerText = '☀️';
                label.innerText = 'Light Mode';
                localStorage.setItem('hlc_theme', 'dark');
            } else {
                body.classList.remove('dark');
                icon.innerText = '🌙';
                label.innerText = 'Dark Mode';
                localStorage.setItem('hlc_theme', 'light');
            }
        }

        function toggleTheme() {
            const isDark = document.body.classList.contains('dark');
            applyTheme(!isDark);
        }

        const savedTheme = localStorage.getItem('hlc_theme') || 'light';
        applyTheme(savedTheme === 'dark');

        async function validateCloudKey() {
            const key = document.getElementById('key-input').value.trim();
            const err = document.getElementById('error-msg');

            if(!key) {
                err.innerText = "Vui lòng nhập API Key!";
                err.classList.remove('hidden');
                return;
            }

            const res = await fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ api_key: key })
            });
            const data = await res.json();
            if(data.success) {
                document.getElementById('auth').classList.add('hidden');
                err.classList.add('hidden');
                loadGroups();
                updateCycle();
            } else {
                err.innerText = data.message;
                err.classList.remove('hidden');
            }
        }

        function toggleFT() {
            ft = !ft;
            const b = document.getElementById('ft-btn');
            document.getElementById('ft-st').innerText = ft ? 'ON' : 'OFF';
            if(ft) {
                b.classList.add('theme-ft-btn-active');
            } else {
                b.classList.remove('theme-ft-btn-active');
            }
        }

        function order(val) {
            fetch('/api/order', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({val: val, ft: ft})});
            if(ft) toggleFT();
        }

        async function removeQueueItem(index) {
            await fetch('/api/queue/remove', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index: index})
            });
        }

        async function clearAllQueue() {
            if(confirm("Xác nhận xóa sạch toàn bộ hàng chờ?")) {
                await fetch('/api/queue/clear', {method: 'POST'});
            }
        }

        async function loadGroups() {
            try {
                const res = await fetch('/api/groups');
                const data = await res.json();
                renderGroups(data.groups, data.active_sources || {});
            } catch(e) {}
        }

        function renderGroups(groups, activeMap) {
            const container = document.getElementById('groups-container');
            if(!groups || groups.length === 0) {
                container.innerHTML = `<div class="theme-glass p-8 rounded-2xl text-center opacity-50 italic text-xs">Chưa có nhóm source nào. Bấm '+ Thêm Nhóm Mới' ở trên để khởi tạo!</div>`;
                return;
            }

            container.innerHTML = groups.map(grp => {
                const grpId = grp.id;
                const activeInThisGroup = activeMap[grpId] || '';

                const sourcesHtml = (grp.sources && grp.sources.length > 0) ? grp.sources.map(src => {
                    const name = src.name;
                    const thumb = src.thumb;
                    const isActive = name === activeInThisGroup;

                    let imgTag = '';
                    if(thumb && thumb.length > 50) {
                        imgTag = `<img src="${thumb}" class="w-full h-full object-contain p-1" alt="${name}"/>`;
                    } else {
                        imgTag = `
                            <div class="flex flex-col items-center justify-center text-center p-2">
                                <span class="text-[11px] opacity-40">Chưa có ảnh</span>
                                <span class="text-[9px] text-blue-600 dark:text-blue-400 underline font-semibold mt-0.5 cursor-pointer" onclick="triggerUpload('${grpId}', '${name}')">Upload</span>
                            </div>
                        `;
                    }

                    return `
                        <div class="theme-scheme-item ${isActive ? 'active-scheme' : ''} p-3 rounded-xl flex flex-col justify-between transition shadow-sm">
                            <div class="flex items-center justify-between mb-2">
                                <span class="font-bold text-xs truncate max-w-[130px]" title="${name}">${name}</span>
                                <span class="text-[8px] px-1.5 py-0.5 rounded font-bold uppercase ${isActive ? 'bg-emerald-500 text-white' : 'bg-neutral-300 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400'}">
                                    ${isActive ? 'ACTIVE' : 'OFF'}
                                </span>
                            </div>
                            
                            <div class="scheme-thumb-container mb-2 border border-neutral-300/40 dark:border-neutral-800 cursor-pointer" onclick="triggerUpload('${grpId}', '${name}')" title="Bấm để đổi ảnh">
                                ${imgTag}
                            </div>

                            <div class="flex items-center gap-1 pt-1.5 border-t border-neutral-300/60 dark:border-neutral-800 text-[10px]">
                                <button onclick="toggleGroupSource('${grpId}', '${name}')" class="flex-1 py-1 rounded-lg font-bold transition text-center ${isActive ? 'bg-amber-600 hover:bg-amber-500 text-white' : 'bg-blue-600 hover:bg-blue-500 text-white'} cursor-pointer">
                                    ${isActive ? 'Tắt' : 'Bật'}
                                </button>
                                <button onclick="triggerUpload('${grpId}', '${name}')" class="px-2 py-1 rounded-lg bg-neutral-200 dark:bg-neutral-800 hover:bg-neutral-300 dark:hover:bg-neutral-700 transition cursor-pointer" title="Đổi ảnh">📷</button>
                                <button onclick="deleteSource('${grpId}', '${name}')" class="px-2 py-1 rounded-lg bg-red-100 dark:bg-red-950/40 text-red-600 hover:bg-red-200 transition cursor-pointer" title="Xóa">🗑️</button>
                            </div>
                        </div>
                    `;
                }).join('') : `<div class="col-span-3 text-xs opacity-50 italic py-3 text-center">Chưa có source trong nhóm này. Bấm '+ Thêm Source' để gán!</div>`;

                return `
                    <div class="theme-glass p-6 rounded-2xl space-y-4">
                        <div class="flex justify-between items-center border-b border-neutral-300/60 dark:border-neutral-800 pb-3">
                            <div class="flex items-center gap-2">
                                <span class="text-sm font-black uppercase text-blue-600 dark:text-blue-400">📁 ${grp.name}</span>
                                <button onclick="renameGroup('${grpId}', '${grp.name}')" class="text-xs opacity-40 hover:opacity-100 cursor-pointer" title="Đổi tên nhóm">✏️</button>
                            </div>
                            <div class="flex items-center gap-2">
                                <button onclick="openSourceModal('${grpId}')" class="bg-neutral-200 dark:bg-neutral-800 hover:bg-neutral-300 dark:hover:bg-neutral-700 px-3 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer">
                                    + Thêm Source
                                </button>
                                <button onclick="deleteGroup('${grpId}', '${grp.name}')" class="text-xs text-red-500 hover:text-red-700 font-bold px-2 py-1 rounded cursor-pointer" title="Xóa toàn bộ nhóm này">
                                    ✕ Xóa Nhóm
                                </button>
                            </div>
                        </div>
                        <div class="grid grid-cols-3 gap-4">${sourcesHtml}</div>
                    </div>
                `;
            }).join('');
        }

        async function createNewGroup() {
            const name = prompt("Nhập tên nhóm mới (Ví dụ: Background, TVC, Podium, Banner,...):");
            if(name && name.trim()) {
                const res = await fetch('/api/groups/add', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: name.trim()})
                });
                const d = await res.json();
                if(!d.success) alert(d.message);
                loadGroups();
            }
        }

        async function renameGroup(grpId, oldName) {
            const newName = prompt(`Đổi tên nhóm [${oldName}] thành:`, oldName);
            if(newName && newName.trim() && newName.trim() !== oldName) {
                await fetch('/api/groups/rename', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({group_id: grpId, name: newName.trim()})
                });
                loadGroups();
            }
        }

        async function deleteGroup(grpId, name) {
            if(confirm(`Xác nhận xóa hoàn toàn nhóm [${name}] và tất cả source thuộc nhóm này?`)) {
                await fetch('/api/groups/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({group_id: grpId})
                });
                loadGroups();
            }
        }

        async function openSourceModal(grpId) {
            currentTargetGroupIdForAdd = grpId;
            const modal = document.getElementById('source-modal');
            const select = document.getElementById('obs-source-select');
            
            modal.classList.remove('hidden');
            select.innerHTML = '<option value="">Đang tải danh sách source từ OBS...</option>';

            try {
                const res = await fetch('/api/obs/sources');
                const data = await res.json();
                if (data.success && data.sources.length > 0) {
                    select.innerHTML = '<option value="">-- Chọn 1 source từ OBS --</option>' + 
                        data.sources.map(s => `<option value="${s}">${s}</option>`).join('');
                } else {
                    select.innerHTML = '<option value="">Không tìm thấy source nào khả dụng trên OBS!</option>';
                }
            } catch (err) {
                select.innerHTML = '<option value="">Lỗi kết nối OBS để lấy source!</option>';
            }
        }

        function closeSourceModal() {
            document.getElementById('source-modal').classList.add('hidden');
            currentTargetGroupIdForAdd = null;
        }

        async function submitSelectSource() {
            const select = document.getElementById('obs-source-select');
            const selectedSource = select.value.trim();

            if (!selectedSource) {
                alert("Vui lòng chọn 1 source trong danh sách!");
                return;
            }

            const res = await fetch('/api/groups/source/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({group_id: currentTargetGroupIdForAdd, name: selectedSource})
            });
            const d = await res.json();
            if (!d.success) alert(d.message);
            closeSourceModal();
            loadGroups();
        }

        async function deleteSource(grpId, name) {
            if(confirm(`Xác nhận xóa source [${name}] khỏi nhóm này?`)) {
                await fetch('/api/groups/source/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({group_id: grpId, name: name})
                });
                loadGroups();
            }
        }

        async function toggleGroupSource(grpId, name) {
            await fetch('/api/groups/source/toggle', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({group_id: grpId, name: name})
            });
            loadGroups();
        }

        function triggerUpload(grpId, srcName) {
            currentUploadTargetGroup = grpId;
            currentUploadTargetSource = srcName;
            document.getElementById('scheme-file-input').click();
        }

        function handleImageSelected(event) {
            const file = event.target.files[0];
            if(!file || !currentUploadTargetGroup || !currentUploadTargetSource) return;

            const reader = new FileReader();
            reader.onload = async function(e) {
                const img = new Image();
                img.src = e.target.result;
                img.onload = async function() {
                    const canvas = document.createElement('canvas');
                    const MAX_WIDTH = 320;
                    const scale = MAX_WIDTH / img.width;
                    canvas.width = MAX_WIDTH;
                    canvas.height = img.height * scale;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    
                    const compressedBase64 = canvas.toDataURL('image/jpeg', 0.75);

                    await fetch('/api/groups/source/upload_thumb', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            group_id: currentUploadTargetGroup, 
                            name: currentUploadTargetSource, 
                            thumb: compressedBase64
                        })
                    });
                    
                    document.getElementById('scheme-file-input').value = '';
                    loadGroups();
                };
            };
            reader.readAsDataURL(file);
        }

        function terminate() {
            if(confirm("XÁC NHẬN: Tắt hoàn toàn tiến trình ngầm và giải phóng OBS?")) {
                fetch('/api/terminate', {method:'POST'}).then(() => {
                    document.body.innerHTML = "<div class='h-screen flex items-center justify-center'><h1 class='text-red-500 font-bold text-3xl tracking-widest'>CORE TERMINATED.</h1></div>";
                    setTimeout(() => window.close(), 1000);
                });
            }
        }
        
        async function updateCycle() {
            try {
                const res = await fetch('/api/state');
                const d = await res.json();
                
                document.getElementById('vid').innerText = d.current_video;
                document.getElementById('timer').innerText = d.remaining + 's';
                document.getElementById('bar').style.width = d.progress + '%';
                document.getElementById('cloud-quota').innerText = d.quota_remaining + ' Credits';
                
                // Render Dynamic Matrix Grid tùy theo số lượng base nhận được từ server
                const matrixGrid = document.getElementById('base-matrix-grid');
                if (matrixGrid && d.total_bases) {
                    document.getElementById('matrix-title').innerText = `VIDEO MATRIX GRID (1-${d.total_bases}: AUTO-LOOP)`;
                    if(matrixGrid.children.length !== d.total_bases) {
                        let html = '';
                        for(let i=1; i<=d.total_bases; i++) {
                            html += `<div class="theme-base-node text-xs" data-name="${d.prefix}${i}${d.suffix}" onclick="order('${i}')">${i}</div>`;
                        }
                        matrixGrid.innerHTML = html;
                    }
                }
                
                document.getElementById('ql').innerHTML = d.queue.length > 0 ? d.queue.map((i, idx) => `
                    <div class="bg-blue-600/10 text-blue-700 dark:text-blue-300 p-2 rounded-lg border border-blue-500/20 text-[11px] font-bold flex justify-between items-center">
                        <span>Base ${i}</span>
                        <div class="flex items-center gap-2">
                            <span class='opacity-50 text-[10px]'>#${idx+1}</span>
                            <button onclick="removeQueueItem(${idx})" class="text-red-500 hover:text-red-700 font-black px-1 rounded cursor-pointer" title="Xóa khỏi hàng đợi">✕</button>
                        </div>
                    </div>
                `).join('') : "<div class='theme-queue-empty text-xs italic p-1'>Auto-Loop Active</div>";
                
                const logBox = document.getElementById('log-box');
                if (d.logs.length > 0) {
                    logBox.innerHTML = d.logs.map(log => {
                        let cls = "text-emerald-400";
                        if(log.includes("[QUEUE]")) cls = "text-amber-400";
                        if(log.includes("[OBS]")) cls = "text-fuchsia-400";
                        if(log.includes("[GROUP]")) cls = "text-sky-400";
                        return `<div class="${cls}">${log}</div>`;
                    }).join('');
                    logBox.scrollTop = logBox.scrollHeight;
                }

                document.querySelectorAll('.theme-base-node').forEach(n => {
                    if (n.getAttribute('data-name') === d.current_video) {
                        n.classList.add('theme-base-active');
                    } else {
                        n.classList.remove('theme-base-active');
                    }
                });
            } catch(e) {}
        }

        setInterval(updateCycle, 500);
    </script>
</body>
</html>"""

@app.route('/')
def index(): 
    return render_template_string(HTML_TEMPLATE, is_authorized=state["is_authorized"])

@app.route('/api/login', methods=['POST'])
def login():
    api_key = request.json.get('api_key', '').strip()
    if not api_key: return {"success": False, "message": "Vui lòng nhập API Key"}
    key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    supabase_api_url = f"{SUPABASE_URL}/rest/v1/api_keys?key_hash=eq.{key_hash}&select=*"
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    try:
        response = requests.get(supabase_api_url, headers=headers)
        if response.status_code == 200 and len(response.json()) > 0:
            key_data = response.json()[0]
            if key_data.get('status') != 'active': return {"success": False, "message": "API Key đã bị khoá!"}
            if key_data.get('quota_remaining', 0) <= 0: return {"success": False, "message": "Hết Quota/Credits hạn mức!"}
            state["is_authorized"] = True
            state["api_key_id"] = key_data.get('id')
            state["quota_remaining"] = key_data.get('quota_remaining', 0)
            
            if global_engine:
                global_engine.hide_all_base_sources()
                
            return {"success": True, "quota": state["quota_remaining"]}
        return {"success": False, "message": "Khóa API Key không chính xác!"}
    except Exception as e: return {"success": False, "message": f"Cloud Error: {str(e)}"}

@app.route('/api/order', methods=['POST'])
def order():
    raw_val = request.json.get('val')
    is_ft = request.json.get('ft', False)
    _, _, total_bases, prefix, suffix = get_current_base_setup()
    
    if str(raw_val).isdigit():
        idx = int(raw_val)
        if 1 <= idx <= total_bases: 
            target_name = f"{prefix}{idx}{suffix}"
            if is_ft: 
                state["task_queue"].appendleft(idx)
                add_web_log("QUEUE", f"⚡ [FAST TRACK] Đẩy gấp {target_name} lên đầu hàng đợi")
            else: 
                state["task_queue"].append(idx)
                add_web_log("QUEUE", f"📥 Đã xếp {target_name} vào cuối hàng chờ")
            return {"success": True, "target": target_name}
        
    return {"success": False, "reason": "invalid_id"}

@app.route('/api/queue/remove', methods=['POST'])
def queue_remove():
    index = request.json.get('index')
    prefix, suffix = get_current_base_setup()[3], get_current_base_setup()[4]
    if index is not None and 0 <= index < len(state["task_queue"]):
        temp = list(state["task_queue"])
        removed = temp.pop(index)
        state["task_queue"] = deque(temp, maxlen=30)
        add_web_log("QUEUE", f"🗑️ Đã xóa {prefix}{removed}{suffix} khỏi hàng đợi")
        return {"success": True}
    return {"success": False}

@app.route('/api/queue/clear', methods=['POST'])
def queue_clear():
    state["task_queue"].clear()
    add_web_log("QUEUE", "🧹 Đã xóa sạch toàn bộ hàng chờ")
    return {"success": True}

# =========================================================================
# API CONFIG & SCAN DURATION (TÍCH HỢP mp4_duration_v7)
# =========================================================================
@app.route('/api/config/get', methods=['GET'])
def get_config_api():
    cfg = load_dynamic_config()
    return {"success": True, **cfg}

@app.route('/api/config/scan', methods=['POST'])
def scan_durations_api():
    folder = request.json.get('folder_path', '').strip()
    if not folder or not os.path.exists(folder):
        return {"success": False, "message": "Thư mục không tồn tại!"}
    
    try:
        from pymediainfo import MediaInfo
        valid_extensions = ('.mp4', '.mov', '.mkv', '.avi', '.flv')
        files = [f for f in os.listdir(folder) if f.lower().endswith(valid_extensions)]
        files.sort(key=lambda var: [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', var)])
        
        if not files:
            return {"success": False, "message": "Không tìm thấy file video nào trong thư mục."}
            
        durations = []
        for filename in files:
            file_path = os.path.join(folder, filename)
            dur = 30.0
            try:
                media_info = MediaInfo.parse(file_path)
                for track in media_info.tracks:
                    if track.track_type == 'Video' and track.duration:
                        dur = round(float(track.duration) / 1000.0, 2)
                        break
            except Exception:
                pass
            durations.append(dur)
            
        cfg = load_dynamic_config()
        cfg["durations"] = durations
        save_dynamic_config(cfg)
        add_web_log("SETUP", f"⚡ Đã quét và cập nhật thành công {len(durations)} video durations!")
        return {"success": True, "message": f"Đã quét thành công {len(durations)} video!"}
    except Exception as e:
        return {"success": False, "message": f"Lỗi quét MediaInfo: {str(e)} (Đảm bảo đã cài pymediainfo)"}

# =========================================================================
# API OBS BULK CREATOR & RENAME (TÍCH HỢP obs_bulk_creator_v3)
# =========================================================================
@app.route('/api/obs/bulk_create', methods=['POST'])
def api_bulk_create():
    if not global_engine:
        return {"success": False, "message": "OBS chưa được kết nối!"}
    
    req = request.json
    folder_path = req.get('folder_path', '').strip()
    source_type = req.get('source_type', 'ffmpeg_source')
    file_pattern = req.get('file_pattern', '')
    name_pattern = req.get('name_pattern', '')
    looping = req.get('looping', True)
    visible = req.get('visible', True)
    
    if not os.path.exists(folder_path):
        return {"success": False, "message": "Thư mục không tồn tại!"}
        
    match_file = re.search(r'\[(\d+)-(\d+)\]', file_pattern)
    match_name = re.search(r'\[(\d+)-(\d+)\]', name_pattern)
    if not match_file or not match_name:
        return {"success": False, "message": "Sai định dạng khoảng [đầu-cuối]!"}
        
    f_start, f_end = int(match_file.group(1)), int(match_file.group(2))
    n_start, n_end = int(match_name.group(1)), int(match_name.group(2))
    steps = f_end - f_start + 1
    
    success_count = 0
    for i in range(steps):
        cur_f = f_start + i
        cur_n = n_start + i
        actual_file = re.sub(r'\[\d+-\d+\]', str(cur_f), file_pattern) + ".mp4"
        actual_name = re.sub(r'\[\d+-\d+\]', str(cur_n), name_pattern)
        full_path = os.path.join(folder_path, actual_file)
        
        if not os.path.exists(full_path):
            continue
            
        try:
            settings = {"local_file": full_path, "looping": looping, "restart_on_activate": True} if source_type == "ffmpeg_source" else {"file": full_path}
            global_engine.cl.create_input(
                sceneName=TARGET_SCENE,
                inputName=actual_name,
                inputKind=source_type,
                inputSettings=settings,
                sceneItemEnabled=visible
            )
            success_count += 1
        except Exception:
            pass
            
    add_web_log("OBS", f"🚀 Đã tạo hàng loạt thành công {success_count} sources vào OBS.")
    return {"success": True, "message": f"Đã tạo thành công {success_count} sources vào Scene {TARGET_SCENE}!"}

@app.route('/api/obs/rename', methods=['POST'])
def api_obs_rename():
    if not global_engine:
        return {"success": False, "message": "OBS chưa kết nối!"}
    find_str = request.json.get('find', '')
    replace_str = request.json.get('replace', '')
    if not find_str:
        return {"success": False, "message": "Thiếu chuỗi cần tìm!"}
    try:
        items = global_engine.cl.get_scene_item_list(TARGET_SCENE).scene_items
        count = 0
        for item in items:
            old_name = item.get('sourceName', '')
            if find_str in old_name:
                new_name = old_name.replace(find_str, replace_str)
                global_engine.cl.set_input_name(inputName=old_name, newInputName=new_name)
                count += 1
        add_web_log("OBS", f"✏️ Đã đổi tên hàng loạt {count} sources.")
        return {"success": True, "message": f"Đã đổi tên thành công {count} sources!"}
    except Exception as e:
        return {"success": False, "message": f"Lỗi đổi tên OBS: {str(e)}"}

@app.route('/api/obs/sources', methods=['GET'])
def get_obs_sources():
    if not global_engine:
        return {"success": False, "sources": []}
    try:
        items = global_engine.cl.get_scene_item_list(TARGET_SCENE).scene_items
        sources = [item.get('sourceName', '') for item in items if item.get('sourceName', '')]
        return {"success": True, "sources": sources}
    except Exception as e:
        return {"success": False, "sources": []}

# =========================================================================
# API QUẢN LÝ CÁC NHÓM SOURCE (MULTI-GROUP SOURCE CONTROLLER)
# =========================================================================
@app.route('/api/groups', methods=['GET'])
def get_groups():
    data = read_groups_data()
    return {"groups": data.get("groups", []), "active_sources": state["active_sources_by_group"]}

@app.route('/api/groups/add', methods=['POST'])
def add_group():
    name = request.json.get('name', '').strip()
    if not name: return {"success": False, "message": "Tên nhóm không được để trống"}
    data = read_groups_data()
    grp_id = f"group_{int(time.time()*1000)}"
    data["groups"].append({"id": grp_id, "name": name, "sources": []})
    write_groups_data(data)
    add_web_log("GROUP", f"📁 Đã tạo nhóm mới: {name}")
    return {"success": True}

@app.route('/api/groups/rename', methods=['POST'])
def rename_group():
    grp_id = request.json.get('group_id')
    name = request.json.get('name', '').strip()
    if not name: return {"success": False, "message": "Tên không hợp lệ"}
    data = read_groups_data()
    for g in data.get("groups", []):
        if g["id"] == grp_id:
            old = g["name"]
            g["name"] = name
            write_groups_data(data)
            add_web_log("GROUP", f"✏️ Đổi tên nhóm: {old} -> {name}")
            return {"success": True}
    return {"success": False, "message": "Không tìm thấy nhóm"}

@app.route('/api/groups/delete', methods=['POST'])
def delete_group():
    grp_id = request.json.get('group_id')
    data = read_groups_data()
    target_grp = next((g for g in data.get("groups", []) if g["id"] == grp_id), None)
    if target_grp:
        active_src = state["active_sources_by_group"].get(grp_id)
        if active_src and global_engine:
            global_engine.set_source_enabled(active_src, False)
            state["active_sources_by_group"].pop(grp_id, None)

        data["groups"] = [g for g in data["groups"] if g["id"] != grp_id]
        write_groups_data(data)
        add_web_log("GROUP", f"🗑️ Đã xóa nhóm: {target_grp['name']}")
        return {"success": True}
    return {"success": False, "message": "Không tìm thấy nhóm"}

@app.route('/api/groups/source/add', methods=['POST'])
def add_source_to_group():
    grp_id = request.json.get('group_id')
    name = request.json.get('name', '').strip()
    if not name: return {"success": False, "message": "Tên source không được để trống"}
    data = read_groups_data()
    for g in data.get("groups", []):
        if g["id"] == grp_id:
            if any(s["name"] == name for s in g["sources"]):
                return {"success": False, "message": "Source này đã có trong nhóm"}
            g["sources"].append({"name": name, "thumb": ""})
            write_groups_data(data)
            add_web_log("GROUP", f"➕ Đã thêm [{name}] vào nhóm [{g['name']}]")
            return {"success": True}
    return {"success": False, "message": "Không tìm thấy nhóm"}

@app.route('/api/groups/source/delete', methods=['POST'])
def delete_source_from_group():
    grp_id = request.json.get('group_id')
    name = request.json.get('name', '').strip()
    data = read_groups_data()
    for g in data.get("groups", []):
        if g["id"] == grp_id:
            g["sources"] = [s for s in g["sources"] if s["name"] != name]
            write_groups_data(data)
            if state["active_sources_by_group"].get(grp_id) == name:
                if global_engine: global_engine.set_source_enabled(name, False)
                state["active_sources_by_group"].pop(grp_id, None)
            add_web_log("GROUP", f"🗑️ Đã xóa source [{name}] khỏi nhóm [{g['name']}]")
            return {"success": True}
    return {"success": False, "message": "Không tìm thấy source"}

@app.route('/api/groups/source/upload_thumb', methods=['POST'])
def upload_group_source_thumb():
    grp_id = request.json.get('group_id')
    name = request.json.get('name')
    thumb = request.json.get('thumb')
    if not grp_id or not name or not thumb: return {"success": False}
    data = read_groups_data()
    for g in data.get("groups", []):
        if g["id"] == grp_id:
            for s in g["sources"]:
                if s["name"] == name:
                    s["thumb"] = thumb
                    write_groups_data(data)
                    add_web_log("GROUP", f"🖼️ Đã lưu ảnh cho [{name}] trong nhóm [{g['name']}]")
                    return {"success": True}
    return {"success": False}

@app.route('/api/groups/source/toggle', methods=['POST'])
def toggle_group_source():
    grp_id = request.json.get('group_id')
    name = request.json.get('name')
    if not grp_id or not name or not global_engine: return {"success": False}

    data = read_groups_data()
    target_grp = next((g for g in data.get("groups", []) if g["id"] == grp_id), None)
    if not target_grp: return {"success": False}

    current_active = state["active_sources_by_group"].get(grp_id, "")
    
    if current_active == name:
        global_engine.set_source_enabled(name, False)
        state["active_sources_by_group"].pop(grp_id, None)
        add_web_log("GROUP", f"⚪ Đã tắt: [{name}] ({target_grp['name']})")
    else:
        for s in target_grp["sources"]:
            if s["name"] != name:
                global_engine.set_source_enabled(s["name"], False)
        success = global_engine.set_source_enabled(name, True)
        if success:
            state["active_sources_by_group"][grp_id] = name
            add_web_log("GROUP", f"🎯 Đã kích hoạt: [{name}] ({target_grp['name']})")
        else:
            add_web_log("OBS", f"⚠️ Không tìm thấy source [{name}] trên OBS để kích hoạt")

    return {"success": True, "active": state["active_sources_by_group"]}

@app.route('/api/state')
def get_state():
    _, durations_map, total_bases, prefix, suffix = get_current_base_setup()
    current_dur = durations_map.get(state['current_video'], 30.0)
    progress = (1 - (float(state['remaining']) / current_dur)) * 100 if current_dur > 0 else 0
    return {
        "authorized": state["is_authorized"],
        "current_video": state["current_video"], 
        "remaining": round(state["remaining"], 1), 
        "progress": min(100, progress),
        "queue": [f"{i}{suffix}" for i in state["task_queue"]],
        "quota_remaining": state["quota_remaining"],
        "logs": list(web_logs),
        "active_sources": state["active_sources_by_group"],
        "total_bases": total_bases,
        "prefix": prefix,
        "suffix": suffix
    }

@app.route('/api/terminate', methods=['POST'])
def terminate(): os.kill(os.getpid(), signal.SIGTERM); return {"success": True}


class HLCEngine:
    def __init__(self):
        try: self.cl = obs.ReqClient(host=OBS_HOST, port=OBS_PORT)
        except Exception: print("❌ Lỗi: OBS chưa mở!"); sys.exit()
        
    def play_video(self, v_name):
        try:
            items = self.cl.get_scene_item_list(TARGET_SCENE).scene_items
            nid = next((i['sceneItemId'] for i in items if i['sourceName'] in [v_name, f"{v_name}.mp4"]), None)
            if nid:
                self.cl.set_scene_item_enabled(TARGET_SCENE, nid, True)
                time.sleep(OVERLAP_TIME)
                if self.last_video and self.last_video != v_name:
                    oid = next((i['sceneItemId'] for i in items if i['sourceName'] in [self.last_video, f"{self.last_video}.mp4"]), None)
                    if oid: self.cl.set_scene_item_enabled(TARGET_SCENE, oid, False)
                self.last_video = v_name
                state["current_video"] = v_name
                return True
        except Exception as e:
            add_web_log("OBS", f"Lỗi chuyển video {v_name}: {str(e)}")
        return False

    def set_source_enabled(self, source_name, enabled):
        try:
            items = self.cl.get_scene_item_list(TARGET_SCENE).scene_items
            target = next((i for i in items if i['sourceName'] in [source_name, f"{source_name}.png", f"{source_name}.jpg", f"{source_name}.mp4"]), None)
            if target:
                self.cl.set_scene_item_enabled(TARGET_SCENE, target['sceneItemId'], enabled)
                return True
            return False
        except Exception as e:
            add_web_log("OBS", f"Lỗi đổi trạng thái source [{source_name}]: {str(e)}")
            return False

    def hide_all_base_sources(self):
        try:
            items = self.cl.get_scene_item_list(TARGET_SCENE).scene_items
            hidden_count = 0
            for item in items:
                source_name = item['sourceName']
                if source_name.startswith("base_") or "ip" in source_name:
                    self.cl.set_scene_item_enabled(TARGET_SCENE, item['sceneItemId'], False)
                    hidden_count += 1
            add_web_log("OBS", f"👁️ [AUTO-HIDE] Đã ẩn thành công {hidden_count} nguồn video base.")
            return True
        except Exception as e:
            add_web_log("OBS", f"❌ Lỗi ẩn source trên OBS: {str(e)}")
            return False

    def deduct_cloud_quota(self, amount=1):
        if not state["api_key_id"]: return
        new_quota = max(0, state["quota_remaining"] - amount)
        url = f"{SUPABASE_URL}/rest/v1/api_keys?id=eq.{state['api_key_id']}"
        headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}", "Content-Type": "application/json"}
        try:
            res = requests.patch(url, headers=headers, json={"quota_remaining": new_quota})
            if res.status_code in [200, 204]: state["quota_remaining"] = new_quota
        except Exception: pass

    def start(self):
        self.last_video = None
        accumulated_seconds = 0.0
        
        threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False), daemon=True).start()
        threading.Timer(2.0, lambda: webbrowser.open("http://localhost:5000")).start()
        
        while True:
            if not state["is_authorized"]: 
                time.sleep(1)
                continue
            if state["quota_remaining"] <= 0:
                state["is_authorized"] = False
                state["current_video"] = "System Locked"
                time.sleep(1)
                continue
            
            base_list, durations_map, total_bases, prefix, suffix = get_current_base_setup()
            if total_bases == 0:
                time.sleep(1)
                continue
            
            if state["task_queue"]:
                next_idx = state["task_queue"].popleft()
                current_name = f"{prefix}{next_idx}{suffix}"
            else:
                current_name = random.choice(list(durations_map.keys()))
            
            if current_name == self.last_video: 
                continue

            if self.play_video(current_name):
                wait_time = max(0.1, durations_map.get(current_name, 30.0) - OVERLAP_TIME)
                start_p = time.time()
                while (time.time() - start_p) < wait_time:
                    state["remaining"] = max(0, wait_time - (time.time() - start_p))
                    time.sleep(0.1)
                
                accumulated_seconds += durations_map.get(current_name, 30.0)
                if accumulated_seconds >= 60.0:
                    mins = int(accumulated_seconds // 60)
                    self.deduct_cloud_quota(amount=mins)
                    accumulated_seconds -= (mins * 60)

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    
    global_engine = HLCEngine()
    global_engine.start()