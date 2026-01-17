import threading
import time
import urllib.request
import urllib.error
import json
from http.server import HTTPServer
from pathlib import Path

from helios_c2.http_api import HeliosAPIHandler


def start_server(tmp_path: Path) -> tuple[HTTPServer, int]:
    handler = HeliosAPIHandler
    handler.out_dir = tmp_path
    handler.config_path = tmp_path / "config.yaml"
    handler.config_path.write_text("pipeline: {}\n", encoding="utf-8")
    handler.suggestion_path = tmp_path / "action_suggestion.json"
    handler.casebook_path = tmp_path / "casebook.json"
    handler.cmds_path = tmp_path / "platform_commands.json"
    handler.assets_path = tmp_path / "assets.json"
    handler.intents_path = tmp_path / "intents.json"
    handler.playbook_path = tmp_path / "playbook_actions.json"
    handler.audit_cfg = {}

    server = HTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def stop_server(server: HTTPServer) -> None:
    server.shutdown()
    server.server_close()
    time.sleep(0.05)


def test_intents_and_commands_endpoints(tmp_path):
    # Seed artifacts
    (tmp_path / "intents.json").write_text(json.dumps([{"id": "i1", "text": "Hold position", "domain": "sea"}]), encoding="utf-8")
    (tmp_path / "playbook_actions.json").write_text(json.dumps([{"id": "pb1", "name": "hold_position"}]), encoding="utf-8")
    (tmp_path / "platform_commands.json").write_text(json.dumps([{"id": "c1", "command": "hold_position", "target": "sea_unit"}]), encoding="utf-8")

    server, port = start_server(tmp_path)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/intents") as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            assert data["intents"][0]["id"] == "i1"

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/playbook_actions") as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["actions"][0]["id"] == "pb1"

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/platform_commands") as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["commands"][0]["id"] == "c1"
    finally:
        stop_server(server)


def test_intents_endpoint_missing_returns_404(tmp_path):
    server, port = start_server(tmp_path)
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/intents")
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        stop_server(server)


def test_playbook_and_platform_missing_return_404(tmp_path):
    server, port = start_server(tmp_path)
    try:
        for endpoint in ("playbook_actions", "platform_commands"):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/{endpoint}")
                assert False, "expected HTTPError"
            except urllib.error.HTTPError as exc:
                assert exc.code == 404
    finally:
        stop_server(server)


def test_platform_command_post_enqueues_and_writes_queue(tmp_path):
    server, port = start_server(tmp_path)
    try:
        queue_path = tmp_path / "platform_commands.q.jsonl"
        # Update config to include queue path so the handler appends.
        handler_cfg = tmp_path / "config.yaml"
        handler_cfg.write_text(f"pipeline:\n  platform:\n    queue_path: {queue_path}\n", encoding="utf-8")

        payload = {"text": "Hold over Line Bravo", "target": "drone_alpha", "domain": "air"}
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/platform_commands",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            body = json.loads(resp.read().decode("utf-8"))
            cmd = body.get("command")
            assert cmd["target"] == "drone_alpha"
            assert cmd["command"] == "Hold over Line Bravo"

        cmds_path = tmp_path / "platform_commands.json"
        saved = json.loads(cmds_path.read_text(encoding="utf-8"))
        assert saved and saved[0]["target"] == "drone_alpha"
        assert queue_path.exists()
        assert queue_path.read_text(encoding="utf-8").strip() != ""
    finally:
        stop_server(server)


def test_platform_command_post_requires_text_and_target(tmp_path):
    server, port = start_server(tmp_path)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/platform_commands",
            data=json.dumps({"text": ""}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req)
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        stop_server(server)
