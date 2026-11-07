#!/usr/bin/env bash
# Start the local Research WebUI server from any working directory.
#   .scripts/bin/research_webui.sh [--restart] [serve options...]
# --restart stops a research_webui.py server already listening on the chosen port first.
# Other options pass through to `research_webui.py serve` (--port, --agent, --timeout, --no-browser).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
restart=0
if [[ "${1:-}" == "--restart" ]]; then
  restart=1
  shift
fi

port=8765
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  case "${args[i]}" in
    --port) port="${args[i + 1]:-$port}" ;;
    --port=*) port="${args[i]#--port=}" ;;
  esac
done

if ((restart)); then
  for pid in $(lsof -nP -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true); do
    if ps -o command= -p "$pid" | grep -q "research_webui.py serve"; then
      echo "기존 서버 종료: pid $pid (포트 $port)"
      kill "$pid"
      for _ in {1..50}; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.1
      done
    else
      echo "포트 $port를 다른 프로그램(pid $pid)이 쓰고 있어 종료하지 않습니다." >&2
      exit 1
    fi
  done
fi

cd "$root"
exec python3 .scripts/bin/research_webui.py serve "$@"
