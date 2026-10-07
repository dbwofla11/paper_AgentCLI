# 독립 심사 페르소나

세 심사자는 각자의 관점만 적용한다. 모든 심사자는 같은 `evidence-bundle-vN-<hash>.json`과 그 안에 고정된 파일 해시를 받는다. 심사자는 다른 심사자의 결과나 주 에이전트의 종합을 보지 않으며, 새 문헌 검색이나 파일 수정도 하지 않는다.

각 결과는 `analysis.json`의 해당 역할 객체로 옮긴다. `evidence_bundle_sha256`는 입력 bundle의 `sha256`와 정확히 같아야 한다. 완료 결과는 치명적 결함, 근거 참조, 요청 사항, 권고를 명시한다. 세 역할 결과가 다 모인 뒤에만 종합한다.

- [Method critic](method-critic.md)
- [Reproducibility critic](repro-critic.md)
- [Novelty critic](novelty-critic.md)
- [공통 출력 계약](../critic-output.schema.json)
