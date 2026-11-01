#!/usr/bin/env python3
"""SPM Local Siax Executor — thin outlet for Grok dialogue / MCP / tunnel.

Tools: local_pc_status · spm_local_execute · spm_local_result

Modes:
  cli    direct commands
  stdio  JSON-RPC lines (experiments / some local CLI bridges)
  http   localhost server:
           REST:  GET /health /tools /local_pc_status
                  POST /tools/call /spm_local_execute /spm_local_result
           MCP:   POST /mcp  (initialize · tools/list · tools/call) for Grok custom connector

Env:
  SPM_LOCAL_TOKEN  if set, require Authorization: Bearer <token> on all non-health routes

Does NOT implement ComfyUI, rewrite SPM, or start S3 scheduler.
"""
from __future__ import annotations

import argparse
import json
import os
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
            "Not Grok Imagine cloud. Not ComfyUI. Requires confirm_model_license_review=true."
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


def mcp_dispatch(req: dict) -> dict:
    """Handle one JSON-RPC MCP request body; return JSON-RPC response object."""
    rid = req.get("id")
    method = req.get("method") or ""
    params = req.get("params") or {}
    # notifications have no id
    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "ige-spm-local-siax", "version": "0.1.1"},
                "capabilities": {"tools": {"listChanged": False}},
            }
        elif method == "notifications/initialized":
            return {"jsonrpc": "2.0", "result": {}}  # may be ignored if no id
        elif method in ("tools/list", "list_tools"):
            result = {"tools": TOOLS}
        elif method in ("tools/call", "call_tool"):
            name = params.get("name") or params.get("tool")
            arguments = params.get("arguments") or params.get("args") or {}
            payload = handle_tool(name, arguments)
            result = {
                "content": [
                    {"type": "text", "text": json.dumps(payload, ensure_ascii=False)}
                ],
                "isError": False,
            }
        elif method == "ping":
            result = {}
        else:
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
        resp = {"jsonrpc": "2.0", "result": result}
        if rid is not None:
            resp["id"] = rid
        return resp
    except Exception as exc:
        resp = {
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": str(exc)},
        }
        if rid is not None:
            resp["id"] = rid
        return resp


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
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            print(json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": str(exc)}}), flush=True)
            continue
        print(json.dumps(mcp_dispatch(req), ensure_ascii=False), flush=True)
    return 0


def cmd_http(host: str, port: int) -> int:
    token = os.environ.get("SPM_LOCAL_TOKEN") or ""

    class H(BaseHTTPRequestHandler):
        def _check_auth(self) -> bool:
            if not token:
                return True
            auth = self.headers.get("Authorization") or ""
            if auth == f"Bearer {token}":
                return True
            self._json(401, {"ok": False, "error": "unauthorized"})
            return False

        def _json(self, code: int, body: dict) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            # CORS not required for Grok server-side; keep simple
            self.end_headers()
            self.wfile.write(data)

        def _read_json(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            return json.loads(raw.decode("utf-8") or "{}")

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in ("/", "/health"):
                self._json(
                    200,
                    {
                        "ok": True,
                        "service": "ige-spm-local-siax",
                        "mcp": "/mcp",
                        "tools": [t["name"] for t in TOOLS],
                        "auth_required": bool(token),
                    },
                )
                return
            if not self._check_auth():
                return
            if path == "/tools":
                self._json(200, {"tools": TOOLS})
            elif path == "/local_pc_status":
                try:
                    self._json(200, handle_tool("local_pc_status", {}))
                except Exception as exc:
                    self._json(500, {"ok": False, "error": str(exc)})
            else:
                self._json(404, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path not in ("/", "/health") and not self._check_auth():
                return
            try:
                body = self._read_json()
            except json.JSONDecodeError:
                self._json(400, {"ok": False, "error": "invalid_json"})
                return
            try:
                if path in ("/mcp", "/mcp/"):
                    # Single JSON-RPC object or batch
                    if isinstance(body, list):
                        out = [mcp_dispatch(x) for x in body]
                    else:
                        out = mcp_dispatch(body)
                    self._json(200, out)
                elif path == "/tools/call":
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
    sys.stderr.write(f"spm_local_executor http://{host}:{port}\n")
    sys.stderr.write(f"  health: GET  /health\n")
    sys.stderr.write(f"  MCP:    POST /mcp   (initialize / tools/list / tools/call)\n")
    sys.stderr.write(f"  REST:   GET  /local_pc_status\n")
    if token:
        sys.stderr.write("  auth:   Bearer SPM_LOCAL_TOKEN required\n")
    else:
        sys.stderr.write("  auth:   SPM_LOCAL_TOKEN not set (open) — set before public tunnel\n")
    sys.stderr.write("PATH1: tunnel this host, then grok.com/connectors → Custom → https://…/mcp\n")
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

    sub.add_parser("stdio", help="JSON-RPC stdio bridge")
    p_http = sub.add_parser("http", help="HTTP + MCP /mcp for tunnel / Grok connector")
    p_http.add_argument("--host", default="127.0.0.1")
    p_http.add_argument("--port", type=int, default=8765)

    sub.add_parser("list-tools")
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
