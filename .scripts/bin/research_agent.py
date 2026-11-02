"""Connect the user's installed, authenticated CLI without copying credentials."""
from __future__ import annotations
import json
import platform
import shutil
import subprocess
from pathlib import Path

from harness_common import omp_model_roles

CONFIG = '.research-harness-agent.json'
AGENTS = ('codex', 'claude', 'omp')
RUNNERS = {'codex': 'codex-cli', 'claude': 'claude-cli', 'omp': 'omp-cli'}


def command(agent: str, stage: Path, last_message: Path, prompt: str, *,
            timeout_seconds: int | None = None, root: Path | None = None) -> list[str]:
    executable = shutil.which(agent)
    if not executable:
        raise ValueError(f'{agent} CLI를 PATH에서 찾을 수 없습니다.')
    if agent == 'codex':
        return [executable, 'exec', '--skip-git-repo-check', '--cd', str(stage),
                '--sandbox', 'workspace-write', '-c', 'approval_policy="never"',
                '--output-last-message', str(last_message), prompt]
    if agent == 'claude':
        settings = json.dumps({'sandbox': {'enabled': True, 'autoAllowBashIfSandboxed': True,
                                          'allowUnsandboxedCommands': False}})
        tools = 'Read,Edit,Write,Bash,Glob,Grep,WebSearch,WebFetch'
        return [executable, '--print', '--output-format', 'text', '--restricted',
                '--permission-mode', 'dontAsk', '--tools', tools, '--allowedTools', tools,
                '--settings', settings, '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', prompt]
    if agent == 'omp':
        model = ['--model', '@paper-analysis'] if 'paper-analysis' in omp_model_roles(root or stage) else []
        limit = ['--max-time', str(timeout_seconds)] if timeout_seconds else []
        return [executable, '-p', '--no-session', '--no-title', '--no-extensions',
                *model, '--approval-mode', 'yolo', '--tools', 'read,grep,glob,bash,edit,write,web_search',
                *limit, f'@{stage}/.agents/skills/paper-review/SKILL.md', '--', prompt]
    raise ValueError('지원하는 에이전트는 codex, claude, omp입니다.')


def probe(agent: str) -> dict:
    result = {'agent': agent, 'installed': bool(shutil.which(agent)), 'authenticated': False,
              'compatible': False, 'ready': False,
              'login_command': {'codex': 'codex login', 'claude': 'claude auth login', 'omp': 'omp login'}.get(agent, '')}
    if not result['installed']:
        result['reason'] = f'{agent} CLI 설치가 필요합니다.'; return result
    try:
        if agent == 'omp':
            version = subprocess.run([shutil.which(agent), '--version'],
                                     capture_output=True, text=True, timeout=15, check=False)
            models = subprocess.run([shutil.which(agent), 'models', '--json'],
                                    capture_output=True, text=True, timeout=15, check=False)
            try:
                entries = json.loads(models.stdout) if models.returncode == 0 else []
            except (ValueError, TypeError):
                entries = []
            if isinstance(entries, dict):
                entries = entries.get('models', [])
            result['compatible'] = version.returncode == 0
            result['authenticated'] = isinstance(entries, list) and any(
                isinstance(entry, dict) and entry.get('selector') for entry in entries)
            result['ready'] = result['compatible'] and result['authenticated']
            result['reason'] = ('연결 준비 완료' if result['ready'] else
                                'CLI 버전 확인에 실패했습니다.' if not result['compatible'] else
                                '사용 가능한 모델이 없습니다. 로그인 확인: ' + result['login_command'])
            return result
        auth = subprocess.run([shutil.which(agent), *(['login', 'status'] if agent == 'codex' else ['auth', 'status'])],
                              capture_output=True, text=True, timeout=15, check=False)
        result['authenticated'] = auth.returncode == 0
        cli = command(agent, Path.cwd(), Path('/tmp/research-agent-check.md'), 'connection check')
        help_result = subprocess.run(cli + ['--help'], capture_output=True, text=True, timeout=15, check=False)
        result['compatible'] = help_result.returncode == 0
        if agent == 'claude':
            result['compatible'] = result['compatible'] and '--restricted' in help_result.stdout
            system = platform.system()
            sandbox_ok = ((system == 'Linux' and bool(shutil.which('bwrap')) and bool(shutil.which('socat')))
                          or (system == 'Darwin' and bool(shutil.which('sandbox-exec'))))
            if not sandbox_ok:
                result['reason'] = 'Claude 작업 격리에 Linux/WSL의 bubblewrap·socat 또는 macOS sandbox-exec가 필요합니다.'
                return result
        result['ready'] = result['authenticated'] and result['compatible']
        result['reason'] = ('연결 준비 완료' if result['ready'] else
                            'CLI 버전이 실행 옵션을 지원하지 않습니다. 업데이트하세요.' if not result['compatible'] else
                            '본인 계정 로그인 필요: ' + result['login_command'])
    except (OSError, subprocess.TimeoutExpired):
        result['reason'] = 'CLI 상태 검사 실패 또는 시간 초과. 터미널에서 로그인 상태를 확인하세요.'
    return result


def resolve(root: Path, requested: str | None = None) -> dict:
    if requested is None:
        path = root / CONFIG
        try:
            requested = json.loads(path.read_text()).get('agent', 'auto') if path.exists() else 'auto'
        except (OSError, ValueError, AttributeError):
            return {'ready': False, 'agent': None, 'reason': '연결 설정을 읽지 못했습니다. 온보딩을 다시 실행하세요.', 'candidates': []}
    if requested not in ('auto', *AGENTS):
        return {'ready': False, 'agent': None, 'reason': '지원하지 않는 에이전트 설정입니다.', 'candidates': []}
    candidates = [probe(name) for name in (AGENTS if requested == 'auto' else (requested,))]
    selected = next((p for p in candidates if p['ready']), next((p for p in candidates if p['installed']), candidates[0]))
    return {**selected, 'candidates': candidates}


def connect(root: Path, requested: str | None = None) -> dict:
    result = resolve(root, requested)
    if result['ready']:
        destination = root / CONFIG
        temporary = destination.with_suffix('.tmp')
        try:
            settings = json.loads(destination.read_text(encoding='utf-8')) if destination.exists() else {}
            if not isinstance(settings, dict):
                raise ValueError('settings must be an object')
        except (OSError, ValueError):
            return {**result, 'ready': False, 'reason': '연결 설정을 읽지 못했습니다. 온보딩을 다시 실행하세요.'}
        settings.update({'schema_version': '1.1', 'agent': result['agent']})
        temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(destination)
    return result
