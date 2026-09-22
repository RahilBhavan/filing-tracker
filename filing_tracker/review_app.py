"""Loopback-only review UI with atomic state, revision checks, and audit history."""

import copy
import json
import mimetypes
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .core import TrackerError, compare, load_pair
from .report import write_report
from .thesis import validate_assumptions


def now():
    return datetime.now(timezone.utc).isoformat()


class ReviewStore:
    def __init__(self, manifest, directory, assumptions=None):
        self.pair = load_pair(manifest)
        self.directory = Path(directory).resolve()
        for side in ("old", "new"):
            raw = Path(self.pair[side]["raw_path"])
            if self.directory == raw.parent or self.directory in raw.parents:
                raise TrackerError("Review directory must be separate from source documents")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "review-state.json"
        self.lock = threading.RLock()
        self.token = secrets.token_urlsafe(32)
        self.state = {"pair_fingerprint": self.pair["fingerprint"], "revision": 0,
            "review": {"pair_fingerprint": self.pair["fingerprint"], "alignments": [], "reviews": {}},
            "assumptions": validate_assumptions(assumptions), "history": [], "sessions": []}
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
            if self.state["pair_fingerprint"] != self.pair["fingerprint"]:
                raise TrackerError("Saved review belongs to another source pair")
        self.result = compare(self.pair, self.state["review"], assumptions=self.state["assumptions"])
        write_report(self.pair, self.result, self.directory / "report")
        self.save()

    def save(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)

    def snapshot(self):
        with self.lock:
            return {"token": self.token, "revision": self.state["revision"], "comparison": self.result,
                    "blocks": {side: self.pair[side]["blocks"] for side in ("old", "new")},
                    "assumptions": self.state["assumptions"], "history": self.state["history"],
                    "sessions": self.state["sessions"], "review": self.state["review"]}

    def update(self, request):
        with self.lock:
            if request.get("revision") != self.state["revision"]:
                raise TrackerError("Stale review revision; reload before saving")
            action = request.get("action")
            next_state = copy.deepcopy(self.state)
            detail = {}
            if action == "decision":
                identifier = request.get("id")
                if identifier not in {c["id"] for c in self.result["changes"]}:
                    raise TrackerError("Unknown change ID")
                decision = request.get("decision")
                next_state["review"]["reviews"][identifier] = decision
                detail = {"id": identifier, "before": self.state["review"]["reviews"].get(identifier), "after": decision}
            elif action == "alignment":
                from .alignment import ids
                old, new = ids(request.get("old")), ids(request.get("new"))
                touched_old, touched_new = set(old), set(new)
                retained = [a for a in next_state["review"]["alignments"] if not (set(ids(a["old"])) & touched_old or set(ids(a["new"])) & touched_new)]
                override = {"old": old, "new": new}
                retained.append(override)
                next_state["review"]["alignments"] = retained
                # Keep stale decisions in history; only remove ones invalidated by new matching.
                trial_review = dict(next_state["review"], reviews={})
                trial = compare(self.pair, trial_review, assumptions=next_state["assumptions"])
                valid = {c["id"] for c in trial["changes"]}
                invalid = {key: value for key, value in next_state["review"]["reviews"].items() if key not in valid}
                next_state["review"]["reviews"] = {key: value for key, value in next_state["review"]["reviews"].items() if key in valid}
                detail = {"override": override, "invalidated_decisions": invalid,
                          "previous_alignments": self.state["review"]["alignments"]}
            elif action == "assumptions":
                next_state["assumptions"] = validate_assumptions(request.get("assumptions"))
                detail = {"before": self.state["assumptions"], "after": next_state["assumptions"]}
            elif action == "start_session":
                mode = request.get("mode")
                reviewer = request.get("reviewer", "").strip()
                if mode not in {"manual", "assisted"} or not reviewer or len(reviewer) > 100:
                    raise TrackerError("A session needs mode manual/assisted and a reviewer name")
                if any(s.get("ended") is None for s in next_state["sessions"]):
                    raise TrackerError("Finish the active session first")
                session = {"id": secrets.token_hex(8), "mode": mode, "reviewer": reviewer,
                           "started": now(), "ended": None, "elapsed_seconds": None,
                           "start_revision": self.state["revision"], "measurement": "human elapsed wall time; includes idle time"}
                next_state["sessions"].append(session)
                detail = session
            elif action == "stop_session":
                active = next((s for s in next_state["sessions"] if s.get("ended") is None), None)
                if active is None:
                    raise TrackerError("No active review session")
                active["ended"] = now()
                active["elapsed_seconds"] = round((datetime.fromisoformat(active["ended"]) - datetime.fromisoformat(active["started"])).total_seconds(), 3)
                active["decisions"] = sum(h["action"] == "decision" for h in next_state["history"] if h["revision"] > active["start_revision"])
                active["alignment_corrections"] = sum(h["action"] == "alignment" for h in next_state["history"] if h["revision"] > active["start_revision"])
                detail = copy.deepcopy(active)
            else:
                raise TrackerError("Unknown review action")
            result = compare(self.pair, next_state["review"], assumptions=next_state["assumptions"])
            next_state["revision"] += 1
            next_state["history"].append({"revision": next_state["revision"], "at": now(), "action": action, "detail": detail})
            # Reports are derived; the atomic state file is the authoritative review record.
            write_report(self.pair, result, self.directory / "report")
            self.state, self.result = next_state, result
            self.save()
            return self.snapshot()


def create_server(store, port=8765):
    static = Path(__file__).parent / "static"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send(self, content, mime="application/json", status=200, attachment=False):
            if not isinstance(content, bytes):
                content = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            if attachment:
                self.send_header("Content-Disposition", "attachment")
            self.end_headers()
            self.wfile.write(content)

        def host_ok(self):
            return self.headers.get("Host") in {"127.0.0.1:%d" % self.server.server_port, "localhost:%d" % self.server.server_port}

        def do_GET(self):
            if not self.host_ok():
                return self.send('{"error":"Invalid host"}', status=403)
            path = unquote(urlsplit(self.path).path)
            if path == "/api/state":
                return self.send(json.dumps(store.snapshot(), ensure_ascii=False))
            if path in {"/", "/manual", "/app.js", "/style.css"}:
                target = static / ("index.html" if path in {"/", "/manual"} else path[1:])
            elif path.startswith("/report/"):
                base = (store.directory / "report").resolve()
                target = (base / path[len("/report/"):]).resolve()
                if base not in target.parents:
                    return self.send('{"error":"Invalid report path"}', status=403)
            else:
                return self.send('{"error":"Not found"}', status=404)
            if not target.is_file():
                return self.send('{"error":"Not found"}', status=404)
            self.send(target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream",
                      attachment=target.name.endswith(".original.html"))

        def do_POST(self):
            if not self.host_ok() or self.headers.get("X-Tracker-Token") != store.token:
                return self.send('{"error":"Invalid local request token"}', status=403)
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                return self.send('{"error":"Invalid origin"}', status=403)
            if self.path != "/api/update":
                return self.send('{"error":"Not found"}', status=404)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1_000_000 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise TrackerError("Expected JSON request up to 1 MB")
                request = json.loads(self.rfile.read(length))
                if not isinstance(request, dict):
                    raise TrackerError("Expected a JSON object")
                self.send(json.dumps(store.update(request), ensure_ascii=False))
            except (TrackerError, ValueError, KeyError, TypeError, AttributeError) as exc:
                self.send(json.dumps({"error": str(exc)}), status=409 if "Stale" in str(exc) else 400)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(manifest, directory, port=8765, assumptions=None):
    store = ReviewStore(manifest, directory, assumptions)
    server = create_server(store, port)
    print("Review locally at http://127.0.0.1:%d (Ctrl-C to stop)" % server.server_port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
