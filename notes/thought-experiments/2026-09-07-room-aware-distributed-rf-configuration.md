# 사고실험: 방 구조 인지형 분산 Wi-Fi CSI configuration 설계

- 작성일: 2026-09-07
- 상태: 가설 단계

## 핵심 질문

LiDAR·UWB·coherent multistatic radar에서 쓰이는 aperture·bandwidth·sensor geometry 설계 원리가, 저가·비동기 Wi-Fi CSI 노드에도 적용되는가? 적용된다면 방의 크기·구조적 복잡도·목표 task·동기화 품질로부터 최소 bandwidth와 Tx/Rx 배치를 선택할 수 있는가?

## 제안 파이프라인

```text
room geometry + material/multipath proxy + task + device phase-error model
    -> candidate bandwidth / Tx-Rx geometry / calibration level
    -> RF forward simulation
    -> reconstruction or localization uncertainty
    -> feasible configuration 및 최소 비용 선택
```

출력은 단일한 “최적 배치”가 아니라 task별 가능성 지도(feasibility map)다. 예: occupancy, large-object localization, coarse structure reconstruction, dense object shape reconstruction.

## 성립하는 이유

- 넓은 bandwidth는 경로 길이 차이를 더 잘 분리하고, 큰·다양한 aperture는 각도 및 공간 ambiguity를 줄이는 경향이 있다 `[일반 RF 원리]`.
- multistatic radar와 RTI에서는 배치가 sensing 성능을 바꾼다는 전례가 있다. 다만 radar는 coherent hardware를, RTI는 주로 RSS 기반 localization을 전제한다 `[확인 필요: 원문 정독]`.

## 전제와 취약점

| 전제 | 깨질 수 있는 이유 | 깨졌을 때의 결과 |
|---|---|---|
| 방 크기가 bandwidth를 결정한다 | 경로 간 delay 차이는 방 크기보다 재질·가구·배치에 좌우될 수 있다 | `room size only` 규칙은 성립하지 않음 |
| Rx를 멀리 벌리면 유효 aperture가 커진다 | 독립 ESP32의 phase/delay offset이 보정되지 않음 | coherent imaging 이득이 사라짐 |
| multipath는 reconstruction 정보다 | 벽·물체·장치 오차가 같은 CSI 변화를 만들 수 있음 | ghost 및 비식별성 발생 |
| simulation의 최적 배치가 실제 장치에도 맞는다 | antenna pattern, AGC, clock drift, 재질 모델 불일치 | sim-to-real failure |

## 식별가능성 점검

정적 방 구조와 정적 가구를 하나의 CSI snapshot만으로 분리하는 것은 일반적으로 식별 불가능하다 `[내 판단]`. 첫 단계의 target은 빈 방 baseline에 대한 차분 CSI로 검출되는 단일 이동 표적이어야 한다. 정적 structure reconstruction은 calibrated phase와 재질/벽 prior를 추가한 별도 단계로 취급한다.

## 최소 실험과 비교 기준

1. WaveVerse에서 단순 방·복잡한 방을 만들고, Rx 1/2/4/8개 및 세 배치(밀집, 한 벽, 사방)를 비교한다.
2. 각 설정에 coherent, fixed phase offset, time-varying phase drift를 독립적으로 주입한다.
3. bandwidth만 바꿀 때와 Rx 배치만 바꿀 때의 위치 오차·ghost rate·uncertainty를 비교한다.
4. baseline은 고정 configuration, 무작위 배치, phase error를 무시한 simulator-optimal 배치다.

## 반증 조건

- room structure를 넣어도 room size만으로 선택한 설정보다 일관되게 낫지 않다.
- phase drift를 포함하면 모든 분산 aperture의 이득이 사라지고 calibration 수준이 유일한 지배 변수다.
- simulator에서 선택한 configuration이 실제 ESP32 단일 표적 실험에서 재현되지 않는다.

## 현재 결론

**조건부 타당.** “방 크기별 최적 bandwidth” 단독 가설은 약하다. 대신 `room geometry + multipath complexity + task + synchronization quality -> configuration`은 검증 가치가 있다. 핵심 연구 공백 후보는 coherent radar의 설계 원리가 비동기 저가 Wi-Fi CSI에서 유지되는 범위와 붕괴 조건을 정량화하는 데 있다.

## 다음 행동

2026-09-08에 LiDAR, UWB, multistatic radar의 configuration 설계 논문을 비교해 각 도메인의 관측량·동기화 가정·배치 목적·bandwidth 역할을 정리한다.
