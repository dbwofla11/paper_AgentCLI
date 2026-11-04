"""Connect the user's installed, authenticated CLI without copying credentials."""
from __future__ import annotations
import json
import platform
import re
import shutil
import subprocess
from pathlib import Path

from harness_common import omp_model_roles

CONFIG = '.research-harness-agent.json'
AGENTS = ('codex', 'claude', 'omp')
RUNNERS = {'codex': 'codex-cli', 'claude': 'claude-cli', 'omp': 'omp-cli'}
SANDBOX_SETTINGS = {'sandbox': {'enabled': True, 'autoAllowBashIfSandboxed': True, 'allowUnsandboxedCommands': False}}
VERIFY_TOOLS = {'claude': 'Read,Glob,Grep,Bash', 'omp': 'read,grep,glob,bash'}
READER_TOOLS = {'claude': 'Read,Grep,Glob', 'omp': 'read,grep,glob'}
# Reader codex runs: plugins and apps bring their own MCP servers/tools, hooks run user commands
# outside the sandbox. All are off; configured MCP servers are disabled by name (codex_mcp_servers).
CODEX_READER_DISABLED_FEATURES = ('plugins', 'apps', 'hooks')


def _claude_model(model: str | None, effort: str | None) -> list[str]:
    return [*(['--model', model] if model else []), *(['--effort', effort] if effort else [])]


def _codex_model(model: str | None, effort: str | None) -> list[str]:
    return [*(['-m', model] if model else []),
            *(['-c', f'model_reasoning_effort="{effort}"'] if effort else [])]


def command(agent: str, stage: Path, last_message: Path, prompt: str, *,
            timeout_seconds: int | None = None, root: Path | None = None,
            model: str | None = None, effort: str | None = None) -> list[str]:
    """Staged review command. `model`/`effort` come from a resolved role candidate; omp's `model`
    is a full `provider/model-id[:effort]` selector that already carries its effort."""
    executable = shutil.which(agent)
    if not executable:
        raise ValueError(f'{agent} CLI를 PATH에서 찾을 수 없습니다.')
    if agent == 'codex':
        return [executable, 'exec', '--skip-git-repo-check', '--cd', str(stage),
                '--sandbox', 'workspace-write', '-c', 'approval_policy="never"',
                *_codex_model(model, effort), '--output-last-message', str(last_message), prompt]
    if agent == 'claude':
        settings = json.dumps(SANDBOX_SETTINGS)
        tools = 'Read,Edit,Write,Bash,Glob,Grep,WebSearch,WebFetch'
        # `--mcp-config` is variadic; the non-variadic `--settings` must precede the prompt so the
        # prompt is not swallowed as another MCP config and probe()'s trailing `--help` still parses.
        return [executable, '--print', '--output-format', 'text', '--restricted',
                '--permission-mode', 'dontAsk', '--tools', tools, '--allowedTools', tools,
                *_claude_model(model, effort),
                '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--settings', settings, prompt]
    if agent == 'omp':
        if model:
            selected = ['--model', model]
        else:
            selected = ['--model', '@paper-analysis'] if 'paper-analysis' in omp_model_roles(root or stage) else []
        limit = ['--max-time', str(timeout_seconds)] if timeout_seconds else []
        return [executable, '-p', '--no-session', '--no-title', '--no-extensions',
                *selected, '--approval-mode', 'yolo', '--tools', 'read,grep,glob,bash,edit,write,web_search',
                *limit, f'@{stage}/.agents/skills/paper-review/SKILL.md', '--', prompt]
    raise ValueError('지원하는 에이전트는 codex, claude, omp입니다.')


def stream_command(agent: str, prompt: str, *, cwd: Path, system: str | None = None,
                   tools: tuple[str, ...] = (), model: str | None = None,
                   timeout_seconds: int | None = None, root: Path | None = None,
                   effort: str | None = None) -> list[str]:
    """Build a JSONL-streaming, session-less command; `--` keeps the prompt out of variadic options."""
    executable = shutil.which(agent)
    if not executable:
        raise ValueError(f'{agent} CLI를 PATH에서 찾을 수 없습니다.')
    if agent == 'claude':
        settings = json.dumps(SANDBOX_SETTINGS)
        allowed = ','.join(tools)
        return [executable, '--print', '--output-format', 'stream-json', '--verbose',
                '--include-partial-messages', '--restricted', '--permission-mode', 'dontAsk',
                '--tools', allowed, *(['--allowedTools', allowed] if tools else []),
                '--no-session-persistence', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                '--settings', settings, *(['--append-system-prompt', system] if system else []),
                *_claude_model(model, effort), '--', prompt]
    if agent == 'codex':
        # codex exec has no system-prompt or tool-selection flag: the system text is prepended to the
        # prompt, and the read-only sandbox bounds what its shell can do.
        text = f'{system}\n\n---\n\n{prompt}' if system else prompt
        return [executable, 'exec', '--json', '--skip-git-repo-check', '--ephemeral', '--cd', str(cwd),
                '--sandbox', 'read-only', '-c', 'approval_policy="never"',
                *_codex_model(model, effort), '--', text]
    if agent == 'omp':
        if model:
            selected = ['--model', model]
        else:
            selected = ['--model', '@paper-analysis'] if 'paper-analysis' in omp_model_roles(root or cwd) else []
        # Tool-less runs carry their own instructions: skip skills, rules, context files and LSP to
        # keep the prompt (and its cost) small. omp has no CLI switch that disables MCP discovery.
        toolset = (['--tools', ','.join(tools), '--approval-mode', 'yolo'] if tools else
                   ['--no-tools', '--no-skills', '--no-rules', '--no-context-files', '--no-lsp'])
        return [executable, '-p', '--mode', 'json', '--no-session', '--no-title', '--no-extensions',
                '--cwd', str(cwd), *selected, *toolset,
                *(['--append-system-prompt', system] if system else []),
                *(['--max-time', str(timeout_seconds)] if timeout_seconds else []), '--', prompt]
    raise ValueError('지원하는 에이전트는 codex, claude, omp입니다.')


def verify_command(agent: str, stage: Path, prompt: str, *, schema_path: Path, model: str | None,
                   effort: str | None, timeout_seconds: int | None = None,
                   root: Path | None = None) -> list[str]:
    """Read-only, JSONL-streaming verifier command that answers with schema-shaped JSON.

    codex validates against `--output-schema <file>`; claude receives the same schema inline via
    `--json-schema`; omp has no schema flag, so the prompt carries the schema. omp's `model` is the
    full selector (its effort included)."""
    executable = shutil.which(agent)
    if not executable:
        raise ValueError(f'{agent} CLI를 PATH에서 찾을 수 없습니다.')
    if agent == 'codex':
        return [executable, 'exec', '--json', '--skip-git-repo-check', '--ephemeral', '--cd', str(stage),
                '--sandbox', 'read-only', '-c', 'approval_policy="never"',
                '--output-schema', str(schema_path), *_codex_model(model, effort), '--', prompt]
    if agent == 'claude':
        schema = json.dumps(json.loads(Path(schema_path).read_text(encoding='utf-8')), separators=(',', ':'))
        tools = VERIFY_TOOLS['claude']
        # `--settings` stays the last option before the prompt (see command()).
        return [executable, '--print', '--output-format', 'stream-json', '--verbose', '--restricted',
                '--permission-mode', 'dontAsk', '--tools', tools, '--allowedTools', tools,
                '--no-session-persistence', '--json-schema', schema, *_claude_model(model, effort),
                '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                '--settings', json.dumps(SANDBOX_SETTINGS), prompt]
    if agent == 'omp':
        return [executable, '-p', '--mode', 'json', '--no-session', '--no-title', '--no-extensions',
                '--cwd', str(stage), '--tools', VERIFY_TOOLS['omp'], '--approval-mode', 'yolo',
                *(['--model', model] if model else []),
                *(['--max-time', str(timeout_seconds)] if timeout_seconds else []), '--', prompt]
    raise ValueError('지원하는 에이전트는 codex, claude, omp입니다.')


def reader_command(agent: str, prompt: str, *, cwd: Path, system: str | None = None,
                   images: tuple[Path, ...] = (), model: str | None = None, effort: str | None = None,
                   timeout_seconds: int | None = None) -> list[str]:
    """Read-only, JSONL-streaming, session-less command for a WebUI paper reader answer.

    Runs in a throwaway workspace with read/grep/glob only (codex: read-only sandbox). `model=None`
    keeps the CLI's own default model (an unconfigured `paper-reader` never inherits omp's
    `@paper-analysis`). Images: claude reads `./region.png` with its Read tool as the prompt asks,
    codex gets `--image <abs>`, omp gets `@<abs>` attachments before `--`. `--` always comes right
    before the prompt so no variadic option swallows it."""
    executable = shutil.which(agent)
    if not executable:
        raise ValueError(f'{agent} CLI를 PATH에서 찾을 수 없습니다.')
    if agent == 'claude':
        tools = READER_TOOLS['claude']
        return [executable, '--print', '--output-format', 'stream-json', '--verbose',
                '--include-partial-messages', '--restricted', '--permission-mode', 'dontAsk',
                '--tools', tools, '--allowedTools', tools, '--no-session-persistence',
                '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                '--settings', json.dumps(SANDBOX_SETTINGS), *(['--append-system-prompt', system] if system else []),
                *_claude_model(model, effort), '--', prompt]
    if agent == 'codex':
        # codex exec has no system-prompt flag: the system text is prepended to the prompt.
        text = f'{system}\n\n---\n\n{prompt}' if system else prompt
        attached = [part for image in images for part in ('--image', str(Path(image).resolve()))]
        disabled = [part for feature in CODEX_READER_DISABLED_FEATURES for part in ('--disable', feature)]
        servers = [part for name in codex_mcp_servers(executable, cwd)
                   for part in ('-c', f'mcp_servers.{name}.enabled=false')]
        return [executable, 'exec', '--json', '--skip-git-repo-check', '--ephemeral', '--cd', str(cwd),
                '--sandbox', 'read-only', '-c', 'approval_policy="never"', *disabled, *servers, *attached,
                *_codex_model(model, effort), '--', text]
    if agent == 'omp':
        return [executable, '-p', '--mode', 'json', '--no-session', '--no-title', '--no-extensions',
                '--no-skills', '--no-rules', '--no-context-files', '--no-lsp', '--cwd', str(cwd),
                *(['--model', model] if model else []), '--tools', READER_TOOLS['omp'],
                '--approval-mode', 'yolo', *(['--append-system-prompt', system] if system else []),
                *(['--max-time', str(timeout_seconds)] if timeout_seconds else []),
                *(f'@{Path(image).resolve()}' for image in images), '--', prompt]
    raise ValueError('지원하는 에이전트는 codex, claude, omp입니다.')


def codex_mcp_servers(executable: str, cwd: Path) -> list[str]:
    """Names of the MCP servers a reader `codex exec` would inherit from the user's config.

    `-c mcp_servers={}` does not remove configured servers (codex merges config tables), so the
    reader disables each one by name. Listed with the same `--disable` features as the run, so
    plugin-provided servers (gone with `plugins` off) are not listed. Fails closed: a listing that
    cannot be read, or a name that is not a plain TOML key, raises ValueError."""
    disabled = [part for feature in CODEX_READER_DISABLED_FEATURES for part in ('--disable', feature)]
    failure = 'codex MCP 서버 목록을 확인하지 못해 읽기 전용 실행을 보장할 수 없습니다'
    try:
        result = subprocess.run([executable, *disabled, 'mcp', 'list', '--json'], cwd=str(cwd),
                                capture_output=True, text=True, timeout=30, check=False)
        entries = json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        raise ValueError(f'{failure}: {error}') from error
    if not isinstance(entries, list):
        raise ValueError(f'{failure}: {(result.stderr or result.stdout).strip()[-300:]}')
    names = []
    for entry in entries:
        name = entry.get('name') if isinstance(entry, dict) else None
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            raise ValueError(f'{failure}: 이름을 설정 키로 쓸 수 없는 서버 {name!r}')
        names.append(name)
    return names


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
