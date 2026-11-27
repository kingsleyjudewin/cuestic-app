"""Cache-bust a Flutter web build so browsers that cached an older bundle load the new one.

Appends a content hash of main.dart.js to the bootstrap and entrypoint URLs. Idempotent. Usage: postbuild_web.py <dir>
"""
import hashlib
import re
import shutil
import sys
from pathlib import Path

web = Path(sys.argv[1])
version = hashlib.sha256((web / "main.dart.js").read_bytes()).hexdigest()[:12]

index = web / "index.html"
html = re.sub(r'flutter_bootstrap\.js(\?v=\w+)?', f"flutter_bootstrap.js?v={version}", index.read_text())
index.write_text(html)

boot = web / "flutter_bootstrap.js"
js = re.sub(r'"mainJsPath":"main\.dart\.js(\?v=\w+)?"', f'"mainJsPath":"main.dart.js?v={version}"', boot.read_text())
boot.write_text(js)

# replace Flutter's caching service worker with a self-removing one
shutil.copy(Path(__file__).with_name("kill_stale_service_worker.js"), web / "flutter_service_worker.js")
print(f"web build cache-busted: v={version}")
