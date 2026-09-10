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

# ==============================================================================
# ⚙️ USER CONFIGURATION: DIARY CSV FILE PATH (기본 일기 CSV 경로)
# 여기에서 일기 CSV 파일의 기본 경로를 직접 지정하고 변경할 수 있습니다.
# (개인정보 보호를 위해 Git 저장소 외부 경로를 지정하는 것을 권장합니다)
# ==============================================================================
DEFAULT_DIARY_CSV_PATH = "/Users/seojin/mind.csv"

# ==============================================================================
# 🤖 LOCAL GEMMA AI CONFIGURATION (로컬 Gemma API 설정)
# Ollama 기본 엔드포인트: http://localhost:11434/api/generate
# 모델명: gemma2:2b (또는 gemma2, gemma:2b 등 로컬에 설치된 모델 지정 가능)
# ==============================================================================
LOCAL_GEMMA_URL = os.environ.get("LOCAL_GEMMA_URL", "http://localhost:11434/api/generate")
LOCAL_GEMMA_MODEL = os.environ.get("LOCAL_GEMMA_MODEL", "gemma2:2b")

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3000

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

def find_edge_gallery_gemma_model():
    patterns = [
        os.path.expanduser("~/Library/Containers/*/Data/Documents/Gemma_4_E2B_it/v0/*.litertlm"),
        os.path.expanduser("~/Library/Containers/F45A43A5-0F15-4C50-9D8A-998CB9F1B7CE/Data/Documents/Gemma_4_E2B_it/v0/gemma4_2b_v09_obfus_fix_all_modalities_thinking.litertlm")
    ]
    for p in patterns:
        matches = glob.glob(p)
        if matches and os.path.exists(matches[0]):
            return matches[0]
    return None

def get_litert_engine():
    global _LITERT_ENGINE
    if _LITERT_ENGINE is not None:
        return _LITERT_ENGINE

    with _LITERT_LOCK:
        if _LITERT_ENGINE is not None:
            return _LITERT_ENGINE

        model_path = find_edge_gallery_gemma_model()
        if not model_path:
            return None

        try:
            import litert_lm
            print(f"🚀 Loading Gemma-4-E2B-it from Edge Gallery with Apple Metal GPU acceleration...")
            _LITERT_ENGINE = litert_lm.Engine(model_path, backend=litert_lm.Backend.GPU())
            print(f"✨ Gemma-4-E2B-it Engine successfully initialized on M3 Pro GPU!")
            return _LITERT_ENGINE
        except Exception as e:
            print(f"⚠️ LiteRT GPU load error: {e}")
            try:
                import litert_lm
                _LITERT_ENGINE = litert_lm.Engine(model_path, backend=litert_lm.Backend.CPU())
                print(f"✨ Gemma-4-E2B-it Engine loaded with CPU fallback.")
                return _LITERT_ENGINE
            except Exception as e2:
                print(f"⚠️ LiteRT CPU fallback failed: {e2}")
                return None

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
        if clean_path == '/api/diary':
            self.handle_diary_api()
            return
        super().do_GET()

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
        # Prevent browser caching of markdown files so edits are instantly visible
        clean_path = self.path.split('?', 1)[0]
        if clean_path.endswith('.md') or clean_path.endswith('.json'):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        super().end_headers()

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
    with socketserver.TCPServer(("", PORT), VocabRequestHandler) as httpd:
        url = f"http://localhost:{PORT}/index.html"
        print("=" * 60)
        print(f"🚀 VocabMaster server is running at {url}")
        print("📖 Live Markdown Sync: English/dissimilarities.md & Words_organized.md")
        print("💡 You can edit markdown files and refresh the browser instantly!")
        print("Press Ctrl+C to stop the server.")
        print("=" * 60)
        try:
            webbrowser.open(url)
        except Exception:
            pass
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\nServer stopped.")

