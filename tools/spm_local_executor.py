#!/usr/bin/env python3
"""SPM Local Siax Executor — thin outlet for Grok Canvas / MCP / tunnel.

Tools:
  local_pc_status
  spm_local_execute
  spm_local_result

Modes:
  cli   — direct commands
  stdio — JSON-RPC lines (MCP-compatible tool/call surface, minimal)
  http  — localhost HTTP for tunnel (ngrok/cloudflared) experiments

Does NOT implement ComfyUI, rewrite SPM, or start S3 scheduler.
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse


def _bootstrap() -> None:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))


def handle_tool(name: str, arguments: dict) -> dict:
    from ige.spm_local import JobStore, local_pc_status, spm_local_execute, spm_local_result

    store = JobStore(Path(arguments.get("job_store") or "runs/spm_local"))
    if name == "local_pc_status":
        return local_pc_status()
    if name == "spm_local_execute":
        return spm_local_execute(
            input_path=arguments["input_path"],
            output_path=arguments.get("output_path"),
            checkpoint=arguments.get("checkpoint") or "models/4x_NMKD-Siax_200k.pth",
            device=arguments.get("device") or "auto",
            tile_size=int(arguments.get("tile_size") or 128),
            tile_pad=int(arguments.get("tile_pad") or 8),
            confirm_model_license_review=bool(
                arguments.get("confirm_model_license_review")
            ),
            job_store=store,
            job_id=arguments.get("job_id"),
        )
    if name == "spm_local_result":
        return spm_local_result(str(arguments["job_id"]), job_store=store)
    raise ValueError(f"unknown tool: {name}")


TOOLS = [
    {
        "name": "local_pc_status",
        "description": "Report local CPU, RAM, GPU, VRAM. Does not run models.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "spm_local_execute",
        "description": (
            "Run native Siax 4x on an input image on this PC (GPU/CPU/RAM). "
            "Not Grok Imagine cloud. Not ComfyUI. Requires confirm_model_license_review."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["input_path", "confirm_model_license_review"],
            "properties": {
                "input_path": {"type": "string"},
                "output_path": {"type": "string"},
                "checkpoint": {"type": "string"},
                "device": {"type": "string", "enum": ["auto", "cpu", "cuda"]},
                "tile_size": {"type": "integer"},
                "tile_pad": {"type": "integer"},
                "confirm_model_license_review": {"type": "boolean"},
                "job_id": {"type": "string"},
                "job_store": {"type": "string"},
            },
        },
    },
    {
        "name": "spm_local_result",
        "description": "Fetch prior local Siax job output path, size, SHA-256.",
        "inputSchema": {
            "type": "object",
            "required": ["job_id"],
            "properties": {
                "job_id": {"type": "string"},
                "job_store": {"type": "string"},
            },
        },
    },
]


def cmd_cli(args: argparse.Namespace) -> int:
    if args.tool == "local_pc_status":
        print(json.dumps(handle_tool("local_pc_status", {}), indent=2, ensure_ascii=False))
        return 0
    if args.tool == "spm_local_execute":
        if not args.confirm_model_license_review:
            raise SystemExit("pass --confirm-model-license-review")
        out = handle_tool(
            "spm_local_execute",
            {
                "input_path": args.input,
                "output_path": args.output,
                "checkpoint": args.checkpoint,
                "device": args.device,
                "tile_size": args.tile_size,
                "tile_pad": args.tile_pad,
                "confirm_model_license_review": True,
                "job_id": args.job_id,
                "job_store": args.job_store,
            },
        )
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0 if out.get("ok") else 2
    if args.tool == "spm_local_result":
        out = handle_tool(
            "spm_local_result",
            {"job_id": args.job_id, "job_store": args.job_store},
        )
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0 if out.get("ok") else 2
    return 1


def cmd_stdio() -> int:
    """Minimal JSON-RPC 2.0 over stdin/stdout for MCP tool bridge experiments."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            print(json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": str(exc)}}))
            continue
        rid = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}
        try:
            if method in ("tools/list", "list_tools"):
                result = {"tools": TOOLS}
            elif method in ("tools/call", "call_tool"):
                name = params.get("name") or params.get("tool")
                arguments = params.get("arguments") or params.get("args") or {}
                result = {"content": [{"type": "text", "text": json.dumps(handle_tool(name, arguments))}]}
            elif method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "ige-spm-local-siax", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                }
            else:
                raise ValueError(f"unknown method {method}")
            print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}), flush=True)
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": rid,
                        "error": {"code": -32000, "message": str(exc)},
                    }
                ),
                flush=True,
            )
    return 0


def cmd_http(host: str, port: int) -> int:
    class H(BaseHTTPRequestHandler):
        def _json(self, code: int, body: dict) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in ("/", "/health"):
                self._json(200, {"ok": True, "service": "ige-spm-local-siax", "tools": [t["name"] for t in TOOLS]})
            elif path == "/tools":
                self._json(200, {"tools": TOOLS})
            elif path == "/local_pc_status":
                try:
                    self._json(200, handle_tool("local_pc_status", {}))
                except Exception as exc:
                    self._json(500, {"ok": False, "error": str(exc)})
            else:
                self._json(404, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._json(400, {"ok": False, "error": "invalid_json"})
                return
            path = urlparse(self.path).path
            try:
                if path == "/tools/call":
                    name = body.get("name")
                    arguments = body.get("arguments") or {}
                    self._json(200, handle_tool(name, arguments))
                elif path == "/spm_local_execute":
                    self._json(200, handle_tool("spm_local_execute", body))
                elif path == "/spm_local_result":
                    self._json(200, handle_tool("spm_local_result", body))
                else:
                    self._json(404, {"ok": False, "error": "not_found"})
            except Exception as exc:
                self._json(500, {"ok": False, "error": str(exc)})

        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write("http: " + (fmt % args) + "\n")

    httpd = HTTPServer((host, port), H)
    sys.stderr.write(f"spm_local_executor http://{host}:{port}  (tunnel this for MCP/connector tests)\n")
    sys.stderr.write("Canvas MCP support is NOT assumed — run a real call test first.\n")
    httpd.serve_forever()
    return 0


def main() -> int:
    _bootstrap()
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_cli = sub.add_parser("cli")
    p_cli.add_argument("tool", choices=["local_pc_status", "spm_local_execute", "spm_local_result"])
    p_cli.add_argument("--input", default="")
    p_cli.add_argument("--output", default="")
    p_cli.add_argument("--checkpoint", default="models/4x_NMKD-Siax_200k.pth")
    p_cli.add_argument("--device", default="auto")
    p_cli.add_argument("--tile-size", type=int, default=128)
    p_cli.add_argument("--tile-pad", type=int, default=8)
    p_cli.add_argument("--job-id", default="")
    p_cli.add_argument("--job-store", default="runs/spm_local")
    p_cli.add_argument("--confirm-model-license-review", action="store_true")

    sub.add_parser("stdio", help="JSON-RPC stdio bridge for MCP experiments")
    p_http = sub.add_parser("http", help="localhost HTTP for tunnel tests")
    p_http.add_argument("--host", default="127.0.0.1")
    p_http.add_argument("--port", type=int, default=8765)

    p_list = sub.add_parser("list-tools")
    args = ap.parse_args()

    if args.cmd == "list-tools":
        print(json.dumps(TOOLS, indent=2))
        return 0
    if args.cmd == "cli":
        return cmd_cli(args)
    if args.cmd == "stdio":
        return cmd_stdio()
    if args.cmd == "http":
        return cmd_http(args.host, args.port)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
