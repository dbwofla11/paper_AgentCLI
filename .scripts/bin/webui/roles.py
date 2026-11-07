"""Harness paper-review roles, resolved from the effective omp config at run time.

The WebUI follows the harness review agents instead of keeping its own model settings:
`paper-analyst` generates a review and `paper-verifier` checks it. Their settings come from omp's
merged config (project `.omp/config.yml` over global), read with `omp config get <key> --json`:

  task.agentModelOverrides[agent]  "@role" or a comma list of selectors; absent -> unconfigured
  modelRoles[role]                 comma list of primary candidates, in order
  retry.fallbackChains[role]       further candidates (ignored when retry.modelFallback is false)

A selector is `provider/model-id[:effort]` (a bare omp model pattern is accepted and runs on omp).
Runner per provider: anthropic -> claude CLI, openai-codex -> codex CLI, anything else -> omp CLI.
Settings and runner probes are cached per repository root for CACHE_TTL_S, so a config edit takes
effect without a restart. Unconfigured `paper-analyst` means the connected agent generates reviews
(pre-existing behavior); unconfigured `paper-verifier` means no verification. A configured role
without a ready candidate is unavailable: nothing is substituted.

"Unconfigured" requires a successful read. When omp cannot report the settings (timeout, non-zero
exit, malformed JSON or wrongly typed values) both resolutions are `configured: None` with an
`error`, and every consumer fails closed: no connected-agent generation, no skipped verification.
A missing omp CLI counts as unconfigured only while the repository has no `.omp/config.yml`.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Iterable, Iterator

import harness_common
import research_agent

GENERATION = "paper-analyst"
VERIFICATION = "paper-verifier"
READER = "paper-reader"  # WebUI paper reader answers; resolved on demand, not part of review_roles()
SEARCHER = "paper-searcher"  # WebUI paper discovery (논문 탐색) runs; resolved on demand like READER
ROLE_AGENTS = {"generation": GENERATION, "verification": VERIFICATION}
SOURCE = "omp-config"
CACHE_TTL_S = 5.0
CONFIG_KEYS = ("task.agentModelOverrides", "modelRoles", "retry.fallbackChains", "retry.modelFallback")
EFFORTS = frozenset({"off", "minimal", "low", "medium", "high", "xhigh", "max", "auto", "inherit"})
PROVIDER_RUNNERS = {"anthropic": "claude", "openai-codex": "codex"}
# Effort values each CLI accepts. claude 2.1.311 `--help`: "--effort <level> (low, medium, high,
# xhigh, max)". codex-cli 0.162.1 `model_reasoning_effort` values from its config enum (the binary
# lists none|minimal|low|medium|high|xhigh|max|...); omp's `off`/`auto`/`inherit` have no literal
# codex equivalent, so the flag is omitted. omp takes the whole selector, effort included.
CLI_EFFORTS = {
    "claude": frozenset({"low", "medium", "high", "xhigh", "max"}),
    "codex": frozenset({"minimal", "low", "medium", "high", "xhigh", "max"}),
}
OUTPUT_EVENTS = frozenset({"text_delta", "message"})

_lock = threading.Lock()
_cache: dict[str, dict] = {}


class RoleUnavailable(RuntimeError):
    """A configured role has no ready candidate, or an unconfigured role cannot run."""


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _setting(key: str, root: Path, kind: type, empty: object) -> object:
    value = harness_common.omp_config_value(key, root)
    if value is None:
        return empty
    if not isinstance(value, kind):
        raise harness_common.OmpConfigError(f"omp 설정 {key}의 형식이 {kind.__name__}이 아닙니다.")
    return value


def read_settings(root: Path) -> dict:
    """The four omp settings the roles depend on. Raises OmpConfigError when any cannot be read."""
    try:
        return {"overrides": _setting("task.agentModelOverrides", root, dict, {}),
                "roles": _setting("modelRoles", root, dict, {}),
                "fallback_chains": _setting("retry.fallbackChains", root, dict, {}),
                "model_fallback": _setting("retry.modelFallback", root, bool, True)}
    except harness_common.OmpMissing:
        if (root / ".omp/config.yml").exists():
            raise harness_common.OmpConfigError(
                "omp CLI가 없어 .omp/config.yml의 리뷰 역할 설정을 읽을 수 없습니다.") from None
        return {"overrides": {}, "roles": {}, "fallback_chains": {}, "model_fallback": True, "omp_missing": True}


def _entry(root: Path) -> dict:
    key = str(root)
    with _lock:
        entry = _cache.get(key)
        if entry is not None and entry["expires"] > time.monotonic():
            return entry
    try:
        settings, error = read_settings(root), None
    except harness_common.OmpConfigError as exc:
        settings, error = None, str(exc) or type(exc).__name__
    # The TTL starts after the (slow, synchronous) reads so a fresh entry is never already stale.
    entry = {"expires": time.monotonic() + CACHE_TTL_S, "settings": settings, "error": error, "probes": {}}
    with _lock:
        _cache[key] = entry
    return entry


def _probe(entry: dict, runner: str) -> dict:
    with _lock:
        cached = entry["probes"].get(runner)
    if cached is None:
        cached = research_agent.probe(runner)
        with _lock:
            entry["probes"][runner] = cached
    return cached


def parse_selector(text: str) -> dict:
    """Split `provider/model-id[:effort]`; a trailing `:x` is an effort only when x is known."""
    selector = text.strip()
    provider, slash, rest = selector.partition("/")
    if not slash:
        provider, rest = None, selector
    model, effort = rest, None
    head, colon, tail = rest.rpartition(":")
    if colon and head and tail in EFFORTS:
        model, effort = head, tail
    return {"selector": selector, "provider": provider or None, "model": model, "effort": effort}


def runner_for(provider: str | None) -> str:
    return PROVIDER_RUNNERS.get(provider or "", "omp")


def cli_effort(runner: str, effort: str | None) -> str | None:
    """Effort flag value for the runner's CLI; None omits the flag (omp keeps it in the selector)."""
    if runner == "omp" or effort is None:
        return None
    return effort if effort in CLI_EFFORTS.get(runner, ()) else None


def invocation(candidate: dict) -> dict:
    """Runner, model argument and effort flag that run one candidate."""
    runner = candidate["runner"]
    if runner == "omp":
        return {"runner": runner, "model": candidate["selector"], "effort": None}
    return {"runner": runner, "model": candidate["model"], "effort": cli_effort(runner, candidate["effort"])}


def _split(value: object) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [part.strip() for part in value if isinstance(part, str) and part.strip()]
    return []


def resolve(agent_name: str, root: Path) -> dict:
    """JSON-serializable resolution of one harness agent (see the module docstring).

    `configured` is True/False after a successful settings read and None when the read failed;
    `error` is then a non-empty reason, and None otherwise.
    """
    entry = _entry(root)
    resolution = {"agent_name": agent_name, "configured": False, "source": SOURCE, "role": None,
                  "candidates": [], "selected": None, "notes": [], "error": None}
    if entry["error"] is not None:
        resolution.update(configured=None, error=f"리뷰 역할 설정(omp config)을 읽지 못했습니다: {entry['error']}")
        resolution["notes"].append("설정을 확인할 수 없어 연결 에이전트로 대체하거나 검증을 건너뛰지 않습니다. "
                                   "`omp config get task.agentModelOverrides --json`을 저장소에서 실행해 확인하세요.")
        return resolution
    settings = entry["settings"]
    override = settings["overrides"].get(agent_name)
    if not isinstance(override, str) or not override.strip():
        if settings.get("omp_missing"):
            resolution["notes"].append("omp CLI가 없고 .omp/config.yml도 없어 역할 미설정으로 봅니다.")
        resolution["notes"].append(
            "미설정: 연결된 에이전트(.research-harness-agent.json)로 리뷰를 생성합니다." if agent_name == GENERATION
            else "미설정: 리뷰 독립 검증을 수행하지 않습니다." if agent_name == VERIFICATION
            else "미설정: 연결된 에이전트(.research-harness-agent.json)의 기본 모델로 답합니다." if agent_name == READER
            else "미설정: 연결된 에이전트(.research-harness-agent.json)의 기본 모델로 검색합니다." if agent_name == SEARCHER
            else "미설정")
        return resolution
    resolution["configured"] = True
    override = override.strip()
    if override.startswith("@"):
        role = override[1:]
        resolution["role"] = role
        selectors = _split(settings["roles"].get(role))
        if not selectors:
            resolution["notes"].append(f"modelRoles.{role}가 비어 있거나 없습니다.")
        chain = _split(settings["fallback_chains"].get(role))
        if chain and not settings["model_fallback"]:
            resolution["notes"].append(f"retry.modelFallback=false: retry.fallbackChains.{role}를 사용하지 않습니다.")
        elif chain:
            selectors += chain
    else:
        selectors = _split(override)
    seen: set[str] = set()
    for selector in selectors:
        if selector in seen:
            continue
        seen.add(selector)
        candidate = parse_selector(selector)
        runner = runner_for(candidate["provider"])
        candidate["runner"] = runner
        if "*" in candidate["model"]:
            candidate.update(ready=False, reason="와일드카드 선택자는 직접 실행할 수 없습니다.")
        else:
            probe = _probe(entry, runner)
            candidate.update(ready=bool(probe.get("ready")),
                             reason=probe.get("reason") or ("" if probe.get("ready") else f"{runner} CLI가 준비되지 않았습니다."))
        if candidate["effort"] is not None and runner != "omp" and cli_effort(runner, candidate["effort"]) is None:
            resolution["notes"].append(
                f"{selector}: {runner} CLI는 effort '{candidate['effort']}'를 받지 않아 플래그를 생략합니다(CLI 기본값).")
        resolution["candidates"].append(candidate)
    resolution["selected"] = next((index for index, c in enumerate(resolution["candidates"]) if c["ready"]), None)
    return resolution


def review_roles(root: Path) -> dict:
    return {key: resolve(name, root) for key, name in ROLE_AGENTS.items()}


def selected_candidate(resolution: dict) -> dict | None:
    index = resolution.get("selected")
    return resolution["candidates"][index] if index is not None else None


def unavailable_reason(resolution: dict) -> str | None:
    """Why a role cannot run: an unreadable config, or a configured role without a ready candidate
    (names the role and each runner). None when it can run or is genuinely unconfigured."""
    if resolution.get("configured") is None:
        return f"{resolution.get('agent_name')}: {resolution.get('error') or '리뷰 역할 설정을 읽지 못했습니다.'}"
    if not resolution["configured"] or resolution["selected"] is not None:
        return None
    name = resolution["agent_name"]
    details = "; ".join(f"{c['selector']} ({c['runner']}): {c['reason']}" for c in resolution["candidates"])
    return (f"{name} 역할을 실행할 수 없습니다 — {details}" if details else
            f"{name} 역할에 실행할 후보 모델이 없습니다(.omp/config.yml의 modelRoles 확인).")


def walk(resolution: dict, run: Callable[[dict], Iterable[dict]]) -> Iterator[dict]:
    """Run the first ready candidate; move on only after a usage limit that produced no output.

    `run(candidate)` returns normalized LLM events ending in one terminal event. A terminal
    `error` with `kind == "usage_limit"` and no earlier `text_delta`/`message` is replaced by a
    `retry` event naming the next ready candidate, which then runs. Anything else ends the walk.
    Raises RoleUnavailable at call time (not lazily) when nothing can run, including an
    unreadable config.
    """
    if resolution.get("configured") is None:
        raise RoleUnavailable(unavailable_reason(resolution))
    if not resolution["configured"]:
        raise RoleUnavailable(f"{resolution['agent_name']} 역할이 설정되지 않았습니다.")
    ready = [candidate for candidate in resolution["candidates"] if candidate["ready"]]
    if not ready:
        raise RoleUnavailable(unavailable_reason(resolution) or "실행할 후보가 없습니다.")
    return _walk(ready, run)


def _walk(ready: list[dict], run: Callable[[dict], Iterable[dict]]) -> Iterator[dict]:
    for index, candidate in enumerate(ready):
        produced = advance = False
        for event in run(candidate):
            kind = event.get("type")
            if kind in OUTPUT_EVENTS:
                produced = True
            if (kind == "error" and event.get("kind") == "usage_limit" and not produced
                    and index + 1 < len(ready)):
                advance = True
                continue
            yield event
        if not advance:
            return
        yield {"type": "retry", "attempt": index + 1, "delay_ms": 0, "reason": "usage_limit",
               "next": ready[index + 1]["selector"]}


# ---- agent definitions (.omp/agents/<name>.md) -------------------------------------------------

def agent_definition(name: str, root: Path) -> tuple[dict, str]:
    """Frontmatter (a small YAML subset) and instruction body of a harness agent definition."""
    text = (root / ".omp/agents" / f"{name}.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text.strip()
    end = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
    if end is None:
        raise ValueError(f".omp/agents/{name}.md frontmatter is not closed")
    meta = _yaml_block(lines[1:end])
    return (meta if isinstance(meta, dict) else {}), "\n".join(lines[end + 1:]).strip()


def _yaml_block(lines: list[str]) -> object:
    items = [(len(line) - len(line.lstrip(" ")), line.strip()) for line in lines
             if line.strip() and not line.strip().startswith("#")]
    if not items:
        return {}
    value, _ = _block(items, 0, items[0][0])
    return value


def _block(items: list[tuple[int, str]], index: int, indent: int) -> tuple[object, int]:
    if items[index][1].startswith("-"):
        result: list = []
        while index < len(items) and items[index][0] == indent and items[index][1].startswith("-"):
            text = items[index][1][1:].strip()
            index += 1
            if text:
                result.append(_scalar(text))
            elif index < len(items) and items[index][0] > indent:
                value, index = _block(items, index, items[index][0])
                result.append(value)
            else:
                result.append(None)
        return result, index
    mapping: dict = {}
    while index < len(items) and items[index][0] == indent and not items[index][1].startswith("-"):
        key, _, rest = items[index][1].partition(":")
        key, rest = _unquote(key.strip()), rest.strip()
        index += 1
        if rest:
            mapping[key] = _scalar(rest)
        elif index < len(items) and (items[index][0] > indent or
                                     (items[index][0] == indent and items[index][1].startswith("-"))):
            mapping[key], index = _block(items, index, items[index][0])
        else:
            mapping[key] = None
    return mapping, index


def _unquote(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def _plain(text: str) -> object:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "~", ""}:
        return None
    try:
        return int(text)
    except ValueError:
        return text


def _scalar(text: str) -> object:
    if text[:1] in "[{":
        value, position = _flow(text, 0)
        if text[position:].strip():
            raise ValueError(f"unexpected YAML after flow value: {text!r}")
        return value
    return _plain(text)


def _flow(text: str, position: int) -> tuple[object, int]:
    def skip(at: int) -> int:
        while at < len(text) and text[at] in " \t":
            at += 1
        return at

    position = skip(position)
    opener = text[position:position + 1]
    if opener in "[{":
        closer = "]" if opener == "[" else "}"
        collection: list | dict = [] if opener == "[" else {}
        position += 1
        while True:
            position = skip(position)
            if position >= len(text):
                raise ValueError(f"unclosed YAML flow collection: {text!r}")
            if text[position] == closer:
                return collection, position + 1
            if isinstance(collection, dict):
                colon = text.index(":", position)
                key = _unquote(text[position:colon].strip())
                value, position = _flow(text, colon + 1)
                collection[key] = value
            else:
                value, position = _flow(text, position)
                collection.append(value)
            position = skip(position)
            if position < len(text) and text[position] == ",":
                position += 1
    if opener in "\"'":
        end = text.index(opener, position + 1)
        return text[position + 1:end], end + 1
    end = position
    while end < len(text) and text[end] not in ",]}":
        end += 1
    return _plain(text[position:end]), end
