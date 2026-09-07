#!/usr/bin/env python3
import http.server
import socketserver
import webbrowser
import sys
import os

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3000

os.chdir(os.path.dirname(os.path.abspath(__file__)))

Handler = http.server.SimpleHTTPRequestHandler

try:
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}/index.html"
        print(f"🚀 VocabMaster server is running at {url}")
        print("Press Ctrl+C to stop the server.")
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\nServer stopped.")
