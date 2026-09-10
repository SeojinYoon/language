#!/usr/bin/env python3
import http.server
import socketserver
import webbrowser
import sys
import os
import csv
import json

# ==============================================================================
# ⚙️ USER CONFIGURATION: DIARY CSV FILE PATH (기본 일기 CSV 경로)
# 여기에서 일기 CSV 파일의 기본 경로를 직접 지정하고 변경할 수 있습니다.
# (개인정보 보호를 위해 Git 저장소 외부 경로를 지정하는 것을 권장합니다)
# ==============================================================================
DEFAULT_DIARY_CSV_PATH = "/Users/seojin/mind.csv"

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

class VocabRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=VOCAB_DIR, **kwargs)

    def do_GET(self):
        clean_path = self.path.split('?', 1)[0].split('#', 1)[0]
        if clean_path == '/api/diary':
            self.handle_diary_api()
            return
        super().do_GET()

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
            entries = []
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

