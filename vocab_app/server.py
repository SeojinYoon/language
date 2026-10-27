#!/usr/bin/env python3
import http.server
import socketserver
import webbrowser
import sys
import os
import csv
import json
import urllib.request
import urllib.error
import glob
import threading
import time
import subprocess
import shutil

# ==============================================================================
# ⚙️ CORE CONFIGURATION & PARAMETERS (핵심 파라미터 연동: config.py)
# 모든 핵심 파라미터와 기본 경로는 config.py 파일에서 일괄 관리됩니다.
# ==============================================================================
try:
    import config
    DEFAULT_DIARY_CSV_PATH = config.DEFAULT_DIARY_CSV_PATH
    LOCAL_GEMMA_URL = config.LOCAL_GEMMA_URL
    LOCAL_GEMMA_MODEL = config.LOCAL_GEMMA_MODEL
    DEFAULT_PORT = config.DEFAULT_PORT
    USE_LITERT = getattr(config, 'USE_LITERT', False)
    AUTO_START_OLLAMA = getattr(config, 'AUTO_START_OLLAMA', True)
    AUTO_STOP_OLLAMA_ON_EXIT = getattr(config, 'AUTO_STOP_OLLAMA_ON_EXIT', False)
except ImportError:
    DEFAULT_DIARY_CSV_PATH = "/Users/seojin/mind.csv"
    LOCAL_GEMMA_URL = os.environ.get("LOCAL_GEMMA_URL", "http://localhost:11434/api/generate")
    LOCAL_GEMMA_MODEL = os.environ.get("LOCAL_GEMMA_MODEL", "gemma2:2b")
    DEFAULT_PORT = 3000
    USE_LITERT = False
    AUTO_START_OLLAMA = True
    AUTO_STOP_OLLAMA_ON_EXIT = False

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT

VOCAB_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(VOCAB_DIR)

# Auto-create symlink to English directory if not already present
english_link = os.path.join(VOCAB_DIR, "English")
english_target = os.path.join(PROJECT_ROOT, "English")
if not os.path.exists(english_link) and os.path.exists(english_target):
    try:
        os.symlink("../English", english_link)
        print("🔗 Symlink created: vocab_app/English -> ../English")
    except Exception as e:
        print(f"⚠️ Could not create symlink: {e}")

os.chdir(VOCAB_DIR)

def parse_diary_entries(csv_path):
    if not os.path.exists(csv_path):
        return []
    entries = []
    try:
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = [r for r in reader]

        header_idx = -1
        for i, r in enumerate(rows[:5]):
            if len(r) >= 6 and "날짜" in r[0] and "내용" in r[4]:
                header_idx = i
                break

        if header_idx != -1:
            for idx, r in enumerate(rows[header_idx + 1:], start=1):
                if len(r) >= 6 and (r[4].strip() or r[5].strip()):
                    entries.append({
                        "id": f"diary_{idx}",
                        "date": r[0].strip(),
                        "weather": r[1].strip(),
                        "type": r[2].strip() or "일기",
                        "mood": r[3].strip(),
                        "korean": r[4].strip(),
                        "english": r[5].strip(),
                        "reference": r[6].strip() if len(r) > 6 else ""
                    })
    except Exception as e:
        print(f"⚠️ CSV parsing error: {e}")
    return entries

def sync_local_diary_cache():
    csv_path = os.path.expanduser(DEFAULT_DIARY_CSV_PATH)
    entries = parse_diary_entries(csv_path)
    if entries:
        try:
            cache_file = os.path.join(VOCAB_DIR, "local_diary.js")
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write("// Auto-generated local cache for offline/file:// support (Git ignored)\n")
                f.write("window.LOCAL_DIARY_DATA = " + json.dumps(entries, ensure_ascii=False) + ";\n")
            print(f"📔 Local diary cache updated: {len(entries)} entries -> local_diary.js")
        except Exception as e:
            print(f"⚠️ Could not update local_diary.js: {e}")

_LITERT_ENGINE = None
_LITERT_LOCK = threading.Lock()
_LITERT_FAILED = False
_OLLAMA_PROCESS = None

def find_edge_gallery_gemma_model():
    if not USE_LITERT:
        return None
    patterns = getattr(config, 'LITERT_MODEL_SEARCH_PATTERNS', [
        os.path.expanduser("~/Library/Containers/*/Data/Documents/Gemma_4_E2B_it/v0/*.litertlm"),
        os.path.expanduser("~/Library/Containers/F45A43A5-0F15-4C50-9D8A-998CB9F1B7CE/Data/Documents/Gemma_4_E2B_it/v0/gemma4_2b_v09_obfus_fix_all_modalities_thinking.litertlm")
    ])
    for p in patterns:
        matches = glob.glob(p)
        for m in matches:
            if os.path.isfile(m):
                return m
    return None

def get_litert_engine():
    global _LITERT_ENGINE, _LITERT_FAILED
    if not USE_LITERT or _LITERT_FAILED:
        return None
    if _LITERT_ENGINE is not None:
        return _LITERT_ENGINE

    with _LITERT_LOCK:
        if not USE_LITERT or _LITERT_FAILED or _LITERT_ENGINE is not None:
            return _LITERT_ENGINE

        model_path = find_edge_gallery_gemma_model()
        if not model_path:
            return None

        try:
            import litert_lm
            try:
                litert_lm.set_min_log_severity(litert_lm.LogSeverity.ERROR)
            except Exception:
                pass
            print(f"🚀 Edge Gallery Gemma-4-E2B-it 온디바이스 모델 로딩 중 (Apple Metal GPU)...")
            _LITERT_ENGINE = litert_lm.Engine(model_path, backend=litert_lm.Backend.GPU())
            print(f"✨ Gemma-4-E2B-it 온디바이스 엔진 초기화 성공 (Apple Metal GPU 가속)!")
            return _LITERT_ENGINE
        except Exception as e:
            print(f"⚠️ LiteRT GPU 로드 오류: {e}")
            try:
                import litert_lm
                _LITERT_ENGINE = litert_lm.Engine(model_path, backend=litert_lm.Backend.CPU())
                print(f"✨ Gemma-4-E2B-it CPU fallback 로드 성공.")
                return _LITERT_ENGINE
            except Exception as e2:
                print(f"⚠️ LiteRT CPU fallback 실패: {e2}")
                _LITERT_FAILED = True
                return None

def check_ollama_status(base_url=None):
    """Ollama 서버 구동 여부 및 사용 가능한 모델 목록을 확인합니다."""
    if base_url is None:
        base_url = LOCAL_GEMMA_URL.rsplit('/', 2)[0] if '/api/' in LOCAL_GEMMA_URL else "http://localhost:11434"
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", headers={"User-Agent": "VocabMaster"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                models = [m.get("name", "") for m in data.get("models", [])]
                return True, models
    except Exception:
        pass
    return False, []

def find_ollama_binary():
    """시스템 내 Ollama 실행 파일 경로를 탐색합니다."""
    cmd = shutil.which("ollama")
    if cmd and os.path.isfile(cmd) and os.access(cmd, os.X_OK):
        return cmd
    candidates = [
        "/usr/local/bin/ollama",
        "/opt/homebrew/bin/ollama",
        os.path.expanduser("~/.local/bin/ollama"),
        os.path.expanduser("~/bin/ollama"),
        "/Applications/Ollama.app/Contents/Resources/ollama"
    ]
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None

def auto_start_ollama_backend():
    """Ollama AI 서버가 실행되어 있지 않으면 백그라운드에서 자동으로 시작합니다."""
    global _OLLAMA_PROCESS
    base_url = LOCAL_GEMMA_URL.rsplit('/', 2)[0] if '/api/' in LOCAL_GEMMA_URL else "http://localhost:11434"

    is_running, models = check_ollama_status(base_url)
    if is_running:
        print(f"🦙 Ollama AI 백엔드가 이미 실행 중입니다 ({base_url}).")
        _check_model_availability(models)
        return True

    print("🤖 로컬 AI 백엔드(Ollama)가 꺼져 있습니다. 백그라운드 자동 구동을 시작합니다...")
    ollama_bin = find_ollama_binary()
    started = False

    if ollama_bin:
        try:
            print(f"🚀 Ollama 데몬 백그라운드 시작 중: {ollama_bin} serve")
            _OLLAMA_PROCESS = subprocess.Popen(
                [ollama_bin, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            started = True
        except Exception as e:
            print(f"⚠️ Ollama 바이너리 실행 오류: {e}")

    if not started and sys.platform == "darwin" and os.path.exists("/Applications/Ollama.app"):
        try:
            print("🚀 macOS Ollama.app을 백그라운드로 실행합니다...")
            subprocess.Popen(["open", "-a", "Ollama", "--background"])
            started = True
        except Exception as e:
            print(f"⚠️ Ollama.app 실행 오류: {e}")

    if not started:
        print("⚠️ Ollama 실행 파일을 찾을 수 없습니다. (공식 사이트: https://ollama.com)")
        return False

    # 최대 8초간 준비 대기 (0.5초 간격 폴링)
    for _ in range(16):
        time.sleep(0.5)
        is_running, models = check_ollama_status(base_url)
        if is_running:
            print(f"✨ Ollama AI 서비스 자동 실행 및 연결 성공! ({base_url})")
            _check_model_availability(models)
            return True

    print("⏳ Ollama 서비스가 시작 중입니다. 잠시 후 연결됩니다.")
    return False

def _check_model_availability(models):
    target = LOCAL_GEMMA_MODEL.lower()
    has_target = any(target in m.lower() for m in models)
    if not has_target and models:
        print(f"ℹ️ 현재 Ollama 설치 모델 목록: {', '.join(models)}")
        print(f"💡 권장 모델('{LOCAL_GEMMA_MODEL}') 설치 명령어: 터미널에서 'ollama pull {LOCAL_GEMMA_MODEL}'")
    elif not models:
        print(f"💡 모델이 설치되어 있지 않을 경우: 터미널에서 'ollama pull {LOCAL_GEMMA_MODEL}' 실행")

def ensure_ai_backend():
    """서버 구동 시 필요한 로컬 AI 백엔드를 점검하고 자동 시작합니다."""
    # 1. Edge Gallery 온디바이스 LiteRT 모델 확인 및 사전 로드
    model_path = find_edge_gallery_gemma_model()
    if model_path:
        print(f"✨ Edge Gallery 온디바이스 모델 감지: {os.path.basename(model_path)}")
        eng = get_litert_engine()
        if eng is not None:
            return

    # 2. Ollama 백엔드 자동 시작 (설정 시)
    if AUTO_START_OLLAMA:
        threading.Thread(target=auto_start_ollama_backend, daemon=True).start()

def query_local_gemma(korean, user_trans, ref_trans):
    prompt = f"""당신은 영작 첨삭 코치입니다.
인사말, 서론, 원문 반복을 일체 생략하고, 기존 영문과의 차이점을 중심으로 아래 2가지 항목만 한국어로 명쾌하게 답변해주세요.
기존 영문에 대한 조언은 하지 말고, 사용자 영작에 대한 조언만 해주세요. 그리고 또, 한국어 원문, 사용자 영작, 기존 영문 전체 문단을 언급하지 마세요.

[한국어 원문] {korean}
[사용자 영작] {user_trans}
[기존 영문] {ref_trans}

1. 💡 기존 영문과의 뉘앙스 차이 (사용자 문장과 기존 영문의 핵심 어감/표현 차이)
2. 🚀 영어 실력 향상을 위한 조언 (더 자연스러운 영작을 위한 1~2가지 핵심 실전 팁)
"""

    # 1. Edge Gallery Gemma-4-E2B-it 온디바이스 LiteRT 엔진 최우선 구동
    engine = get_litert_engine()
    if engine is not None:
        try:
            thinking_cfg = None
            try:
                import litert_lm
                thinking_cfg = litert_lm.ThinkingConfig(enable_thinking=False, thinking_token_budget=0)
            except Exception:
                pass

            with engine.create_conversation() as conv:
                chunks = []
                for chunk in conv.send_message_async(prompt, max_output_tokens=900, thinking_config=thinking_cfg):
                    content = chunk.get("content", [])
                    if content and "text" in content[0]:
                        chunks.append(content[0]["text"])
                feedback = "".join(chunks).strip()
                if feedback:
                    print("✅ Gemma-4-E2B-it 첨삭 생성 완료!")
                    return {
                        "status": "success",
                        "feedback": feedback,
                        "model": "Gemma-4-E2B-it (Edge Gallery 온디바이스 Metal 가속)"
                    }
        except Exception as e:
            print(f"⚠️ Gemma-4-E2B-it 추론 중 오류: {e}")

    # 2. Ollama Fallback
    req_data = {
        "model": LOCAL_GEMMA_MODEL,
        "prompt": prompt,
        "stream": False
    }

    try:
        data_bytes = json.dumps(req_data).encode('utf-8')
        req = urllib.request.Request(
            LOCAL_GEMMA_URL,
            data=data_bytes,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=40) as resp:
            resp_body = resp.read().decode('utf-8')
            res_json = json.loads(resp_body)
            feedback = res_json.get("response", "")
            return {
                "status": "success",
                "feedback": feedback,
                "model": f"{LOCAL_GEMMA_MODEL} (Ollama)"
            }
    except urllib.error.URLError as e:
        return {
            "status": "offline",
            "message": "로컬 Gemma AI 모델을 로드할 수 없습니다.",
            "guide": "Edge Gallery에 Gemma-4-E2B-it 모델이 다운로드되어 있거나, 터미널에서 'ollama run gemma2:2b'가 실행되어 있어야 합니다.",
            "model": "Gemma-4-E2B-it",
            "error_detail": str(e)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"AI 피드백 요청 중 오류가 발생했습니다: {str(e)}",
            "model": "Gemma-4-E2B-it"
        }

def stream_local_gemma(korean, user_trans, ref_trans, send_event):
    prompt = f"""당신은 영작 첨삭 코치입니다.
인사말, 서론, 원문 반복을 일체 생략하고, 기존 영문과의 차이점을 중심으로 아래 2가지 항목만 한국어로 명쾌하게 답변해주세요.
기존 영문에 대한 조언은 하지 말고, 사용자 영작에 대한 조언만 해주세요. 그리고 또, 한국어 원문, 사용자 영작, 기존 영문 전체 문단을 언급하지 마세요.

[한국어 원문] {korean}
[사용자 영작] {user_trans}
[기존 영문] {ref_trans}

1. 💡 기존 영문과의 뉘앙스 차이 (사용자 문장과 기존 영문의 핵심 어감/표현 차이)
2. 🚀 영어 실력 향상을 위한 조언 (더 자연스러운 영작을 위한 1~2가지 핵심 실전 팁)
"""

    model_name = "Gemma-4-E2B-it (Edge Gallery 온디바이스 Metal 가속)"
    send_event({"type": "start", "model": model_name})

    # 1. Edge Gallery Gemma-4-E2B-it 온디바이스 LiteRT 엔진 스트리밍
    engine = get_litert_engine()
    if engine is not None:
        try:
            thinking_cfg = None
            try:
                import litert_lm
                thinking_cfg = litert_lm.ThinkingConfig(enable_thinking=False, thinking_token_budget=0)
            except Exception:
                pass

            print("🤖 Gemma-4-E2B-it 실시간 스트리밍 생성 시작...")
            with engine.create_conversation() as conv:
                for chunk in conv.send_message_async(prompt, max_output_tokens=900, thinking_config=thinking_cfg):
                    content = chunk.get("content", [])
                    if content and "text" in content[0]:
                        send_event({"token": content[0]["text"]})
                print("✅ Gemma-4-E2B-it 실시간 스트리밍 전송 완료!")
                send_event({"done": True, "model": model_name})
                return
        except Exception as e:
            print(f"⚠️ Gemma-4-E2B-it 스트리밍 추론 중 오류: {e}")

    # 2. Ollama Fallback Streaming
    try:
        req_data = {
            "model": LOCAL_GEMMA_MODEL,
            "prompt": prompt,
            "stream": True
        }
        data_bytes = json.dumps(req_data).encode('utf-8')
        req = urllib.request.Request(
            LOCAL_GEMMA_URL,
            data=data_bytes,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=40) as resp:
            for raw_line in resp:
                if raw_line:
                    line_str = raw_line.decode('utf-8').strip()
                    if line_str:
                        item = json.loads(line_str)
                        tok = item.get("response", "")
                        if tok:
                            send_event({"token": tok})
                        if item.get("done", False):
                            send_event({"done": True, "model": f"{LOCAL_GEMMA_MODEL} (Ollama)"})
                            return
    except Exception as e:
        send_event({
            "error": True,
            "message": "로컬 Gemma AI 모델을 로드할 수 없습니다.",
            "guide": "Edge Gallery에 Gemma-4-E2B-it 모델이 다운로드되어 있거나, server.py 실행 상태를 확인해주세요.",
            "model": "Gemma-4-E2B-it",
            "error_detail": str(e)
        })

class VocabRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=VOCAB_DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        clean_path = self.path.split('?', 1)[0].split('#', 1)[0]
        if clean_path == '/api/config':
            self.handle_config_api()
            return
        if clean_path == '/api/diary':
            self.handle_diary_api()
            return
        super().do_GET()

    def handle_config_api(self):
        try:
            import config
            summary = config.get_config_summary()
        except Exception:
            summary = {
                "quiz_parameters": {"quiz_goal_target": 20}
            }
        payload = json.dumps(summary, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        clean_path = self.path.split('?', 1)[0].split('#', 1)[0]
        if clean_path == '/api/ai-feedback':
            self.handle_ai_feedback_api()
            return
        self.send_response(404)
        self.end_headers()

    def handle_diary_api(self):
        csv_path = os.path.expanduser(DEFAULT_DIARY_CSV_PATH)
        if not os.path.exists(csv_path):
            self.send_response(404)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            err_payload = json.dumps({
                "error": f"일기 CSV 파일을 찾을 수 없습니다: {csv_path}",
                "configured_path": DEFAULT_DIARY_CSV_PATH,
                "entries": []
            }, ensure_ascii=False).encode('utf-8')
            self.wfile.write(err_payload)
            return

        try:
            entries = parse_diary_entries(csv_path)
            payload = json.dumps(entries, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e), "entries": []}).encode('utf-8'))

    def handle_ai_feedback_api(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        korean = data.get('korean', '')
        user_trans = data.get('userTranslation', '')
        ref_trans = data.get('referenceTranslation', '')
        wants_stream = data.get('stream', True)

        if not wants_stream:
            result = query_local_gemma(korean, user_trans, ref_trans)
            payload = json.dumps(result, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        # SSE Streaming Response
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-transform')
        self.send_header('Connection', 'close')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('X-Accel-Buffering', 'no')
        self.end_headers()

        def send_event(data_dict):
            try:
                line = f"data: {json.dumps(data_dict, ensure_ascii=False)}\n\n"
                self.wfile.write(line.encode('utf-8'))
                self.wfile.flush()
            except Exception:
                pass

        try:
            stream_local_gemma(korean, user_trans, ref_trans, send_event)
        finally:
            self.close_connection = True

    def translate_path(self, path):
        clean_path = path.split('?', 1)[0].split('#', 1)[0]
        # Route requests starting with /English/ directly to project root
        if clean_path.startswith('/English/'):
            return os.path.join(PROJECT_ROOT, clean_path.lstrip('/'))
        return super().translate_path(path)

    def end_headers(self):
        # Prevent browser from aggressively caching HTML, JS, CSS, JSON, MD so code edits are immediately fresh
        clean_path = self.path.split('?', 1)[0].lower()
        if (clean_path.endswith('.html') or 
            clean_path.endswith('.js') or 
            clean_path.endswith('.css') or 
            clean_path.endswith('.json') or 
            clean_path.endswith('.md') or 
            clean_path == '/' or 
            clean_path == ''):
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        super().end_headers()

if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True

    try:
        import build_data
        build_data.build(PROJECT_ROOT, os.path.join(VOCAB_DIR, "data.js"))
    except Exception as e:
        print(f"⚠️ Could not auto-build data.js: {e}")

    try:
        sync_local_diary_cache()
    except Exception as e:
        print(f"⚠️ Could not sync local diary cache: {e}")

    try:
        ensure_ai_backend()
    except Exception as e:
        print(f"⚠️ Could not initialize AI backend: {e}")

    try:
        with socketserver.TCPServer(("", PORT), VocabRequestHandler) as httpd:
            url = f"http://localhost:{PORT}/index.html?t={int(time.time())}"
            print("=" * 60)
            print(f"🚀 VocabMaster server is running at http://localhost:{PORT}")
            print("📖 Live Markdown Sync: English/dissimilarities.md & Words_organized.md")
            print("⚡ Cache-busting enabled: Code edits reflect immediately!")
            print("Press Ctrl+C to stop the server.")
            print("=" * 60)
            try:
                webbrowser.open(url)
            except Exception:
                pass
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        if AUTO_STOP_OLLAMA_ON_EXIT and _OLLAMA_PROCESS is not None:
            try:
                print("🛑 Ollama 백그라운드 프로세스를 정리합니다...")
                _OLLAMA_PROCESS.terminate()
                _OLLAMA_PROCESS.wait(timeout=2)
            except Exception:
                pass
        elif _OLLAMA_PROCESS is not None:
            print("🦙 Ollama 백그라운드 서버는 계속 유지됩니다. (수동 종료: killall ollama)")

