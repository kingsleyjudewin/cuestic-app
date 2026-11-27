"""Static server for the Flutter web build that tells browsers never to reuse cached files.

`python -m http.server` sends no Cache-Control header, so Chrome keeps serving an old main.dart.js for hours
after a rebuild (stale app code, e.g. old save payloads). Usage: serve_web.py <directory> <port>
"""
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    directory, port = sys.argv[1], int(sys.argv[2])
    ThreadingHTTPServer(("0.0.0.0", port), partial(NoCacheHandler, directory=directory)).serve_forever()
