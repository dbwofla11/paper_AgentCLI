# 04-Projects — 실행 단위

아이디어가 아니라 **실제로 수행할 실험·구현·스터디**를 관리한다. 프로젝트 하나는 목표, 입력, 산출물, 다음 행동, 관련 근거를 가져야 한다.

## WAVEVERSE forward simulation 검증

아직 프로젝트 노트는 만들지 않았다. 시작 시 `waveverse-forward-simulation.md`를 만들고 다음을 기록한다.

- 목표: 환경·대역폭·Tx/Rx 배치 변화가 CSI와 reconstruction 가능성에 미치는 영향을 측정
- 입력: 방 geometry, material/multipath 설정, Tx/Rx geometry, bandwidth, 물체 배치
- 출력: synthetic CSI, reconstruction/localization 지표, 조건별 오차 표
- 연결: `05-ideas/thought-experiments/2026-09-07-room-aware-distributed-rf-configuration.md`
- 종료 조건: 어떤 요인이 오차를 지배하는지 구분 가능한 실험 설계 확보

연구 가설 자체는 [05-ideas](../05-ideas/README.md)에, 재사용 가능한 이해는 [02-Concepts](../02-Concepts/README.md)에 둔다.
