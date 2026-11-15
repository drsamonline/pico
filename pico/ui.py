"""pico local web UI — one file, no dependencies, 127.0.0.1 by default."""
import json
import pathlib
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = pathlib.Path(__file__).resolve().parent.parent / "web" / "index.html"


def token_for(engine):
    f = engine.home / "web.token"
    if f.exists():
        t = f.read_text("utf-8").strip()
        if t:
            return t
    t = secrets.token_urlsafe(24)
    f.write_text(t, "utf-8")
    try:
        f.chmod(0o600)
    except Exception:
        pass
    return t


def snapshot(engine):
    s = engine.S
    return {
        "tasks": s.get("tasks", []),
        "shop": s.get("shop", []),
        "spend": s.get("spend", []),
        "events": s.get("events", []),
        "notes": list(s.get("notes", {}).keys()),
        "aliases": len(s.get("aliases", {})),
        "catalog": engine.catalog,
        "mode": "engine",
    }


def make_handler(engine, token, page_html):
    class H(BaseHTTPRequestHandler):
        server_version = "pico"

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            # a cache-busting query string must not turn a known route into a 404
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html", "/app.html"):
                return self._send(200, page_html, "text/html")
            if path == "/api/state":
                return self._send(200, json.dumps(snapshot(engine)))
            if path == "/favicon.ico":
                return self._send(204, b"")
            for name, ctype in (("/manifest.webmanifest", "application/manifest+json"),
                                ("/sw.js", "application/javascript"),
                                ("/icon-192.png", "image/png"),
                                ("/icon-512.png", "image/png")):
                if path == name:
                    f = PAGE.parent / name.lstrip("/")
                    if f.exists():
                        return self._send(200, f.read_bytes(), ctype)
                    return self._send(404, b"")
            self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/cmd":
                return self._send(404, json.dumps({"error": "not found"}))
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > 64_000:
                    return self._send(413, json.dumps({"error": "too large"}))
                body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except Exception:
                return self._send(400, json.dumps({"error": "bad json"}))
            if not secrets.compare_digest(str(body.get("token", "")), token):
                return self._send(403, json.dumps({"error": "bad token"}))
            text = str(body.get("text", ""))[:2000]
            out = engine.handle(text)
            res = engine.resolve(text)
            self._send(200, json.dumps({
                "out": out,
                "resolved": res.get("cmd"),
                "src": res.get("src"),
                "tier": engine.risk_of(res.get("cmd") or text),
                "state": snapshot(engine),
            }))

    return H


def serve(engine, port=8765, lan=False, open_browser=True):
    token = token_for(engine)
    html = PAGE.read_text("utf-8").replace(
        "/*__PICO_TOKEN__*/null", json.dumps(token))
    host = "0.0.0.0" if lan else "127.0.0.1"
    if lan:
        print("!! LAN mode: anyone on this network can drive pico. Use only on a trusted network.")
    httpd = ThreadingHTTPServer((host, port), make_handler(engine, token, html))
    url = "http://127.0.0.1:%d/" % port
    print("pico ui: %s   (token in %s)" % (url, engine.home / "web.token"))
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        httpd.server_close()
    return 0
