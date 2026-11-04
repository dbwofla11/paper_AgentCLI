#!/usr/bin/env python3
"""Run the Research Harness localhost WebUI (serve) or report its readiness (check)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import webbrowser

import research_agent
from webui import reviews
from webui.server import WEBUI_HOME, make_server, serve_until_stopped

FRONTEND_INDEX = "100-views/webui/index.html"
BUILD_HINT = "cd .scripts/webui && npm install && npm run build"


def readiness(requested: str | None = None) -> dict:
    agent = research_agent.resolve(reviews.ROOT, requested)
    pdf_reader_ready = bool(shutil.which("pdftotext"))
    frontend_ready = (reviews.ROOT / FRONTEND_INDEX).is_file()
    return {"ready": bool(agent.get("ready")) and pdf_reader_ready and frontend_ready,
            "agent": agent, "pdf_reader_ready": pdf_reader_ready,
            "frontend_ready": frontend_ready, "frontend_index": FRONTEND_INDEX}


def check() -> int:
    report = readiness()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready"] else 1


def serve(args: argparse.Namespace) -> int:
    agent_status = None
    if args.agent:
        agent_status = research_agent.resolve(reviews.ROOT, args.agent)
        if not agent_status.get("ready"):
            print(f"에이전트 준비 안 됨: {agent_status.get('reason')}", file=sys.stderr)
    try:
        server = make_server(args.port, agent_status=agent_status, review_timeout=args.timeout)
    except OSError as exc:
        print(f"포트 {args.port}에서 서버를 시작하지 못했습니다: {exc}. --port로 다른 포트를 지정하세요.",
              file=sys.stderr)
        return 1
    if not (reviews.ROOT / FRONTEND_INDEX).is_file():
        print(f"프런트엔드 빌드가 없습니다({FRONTEND_INDEX}). 빌드: {BUILD_HINT}", file=sys.stderr)
    url = f"http://127.0.0.1:{server.server_port}{WEBUI_HOME}"
    print(url, flush=True)
    print("127.0.0.1에만 바인딩합니다. Ctrl+C로 종료합니다.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    serve_until_stopped(server)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    serve_parser = commands.add_parser("serve", help="start the WebUI server on 127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.add_argument("--agent", choices=("auto", *research_agent.AGENTS), default=None,
                              help="pin the agent for this server; default reads the saved connection")
    serve_parser.add_argument("--timeout", type=int, default=3600, help="per-review timeout in seconds")
    serve_parser.add_argument("--no-browser", action="store_true")
    commands.add_parser("check", help="print readiness JSON; exit 0 only when everything is ready")
    args = parser.parse_args()
    if args.command == "check":
        return check()
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    return serve(args)


if __name__ == "__main__":
    sys.exit(main())
