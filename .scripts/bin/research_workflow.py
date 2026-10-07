#!/usr/bin/env python3
"""Return the next installed research skill for a declared workflow stage."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKFLOW = {
    "capture": {"next": "paper-search", "reason": "질문을 논문·주제 후보로 확정한다."},
    "upload": {"next": "paper-search", "reason": "업로드 논문의 메타데이터를 확인하고 Keep·JSON에 등록한다."},
    "collect": {"next": "paper-search", "reason": "메타데이터를 확정하고 원문을 수집한다."},
    "triage": {"next": "paper-review", "reason": "트리아지 통과 논문을 3패스 심층 리뷰로 넘긴다."},
    "review": {"next": "review-index", "reason": "완료 리뷰와 라이브러리 인덱스를 동기화한다."},
    "context": {"next": "related-work", "reason": "앵커 논문의 전후 인용 흐름을 확인한다."},
    "relations": {"next": "paper-relations", "reason": "저장소 내 논문 관계를 Graphify로 검증한다."},
    "visualize": {"next": "graphify", "reason": "논문 JSON과 지식 그래프의 관계를 탐색한다."},
    "concept": {"next": "thought-experiment-critique", "reason": "공부·문헌 결과를 반증 가능한 가설로 점검한다."},
    "study-note": {"next": "concept-note", "reason": "사용자가 요청한 개념 공부노트를 생성·수정한다."},
    "concept-note": {"next": "concept-note", "reason": "사용자가 요청한 개념 공부노트를 생성·수정한다."},
    "idea": {"next": "critical-validation", "reason": "아이디어의 방법·재현성·새로움을 독립 심사한다."},
    "experiment": {"next": "thought-experiment-runner", "reason": "승인된 가설을 작은 manifest 기반 실행으로 전환한다."},
    "draft": {"next": "paper-draft-logic-review", "reason": "논문 초안의 주장·근거·한계 연결을 검토한다."},
    "daily": {"next": "daily-digest-loop", "reason": "CV·멀티모달·관심 분야에서 학회 게재 논문 후보 3편을 채팅으로 제시한다."},
    "trend": {"next": "daily-digest-loop", "reason": "daily와 같은 일일 논문 후보 검색을 실행한다."},
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=sorted(WORKFLOW), nargs="?", help="현재 연구 단계")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()
    if args.stage is None:
        path_map = Path(__file__).resolve().parents[1] / "docs/research-workflow-map.json"
        paths = json.loads(path_map.read_text(encoding="utf-8"))["paths"]
        payload = {"stages": WORKFLOW, "paths": paths}
    else:
        payload = {"stage": args.stage, **WORKFLOW[args.stage]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.stage is None:
        for stage, detail in WORKFLOW.items():
            print(f"{stage:10} -> {detail['next']:30} {detail['reason']}")
    else:
        print(f"next: {payload['next']}\nreason: {payload['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
