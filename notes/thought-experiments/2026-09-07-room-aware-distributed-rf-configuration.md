# 사고실험: 저가 분산 Wi-Fi CSI reconstruction 정확도의 영향 요인 분석

- 작성일: 2026-09-07
- 상태: 가설 단계
- 쉬운 버전: [Wi-Fi로 방 안을 볼 때, 정확도는 무엇이 결정할까?](./2026-09-07-rf-room-sensing-easy.md)

## 핵심 질문

저가·비동기 Wi-Fi CSI 시스템에서 reconstruction/localization 정확도는 무엇이 결정하는가? 방의 크기·형태·multipath 구조, bandwidth, Tx/Rx 개수·배치, 표적 특성, 시간·위상 동기화 오차의 개별 효과와 상호작용을 정량화할 수 있는가?

목표는 정확도를 높이는 새 알고리즘이나 단일 “최적 configuration”을 제안하는 것이 아니다. 어떤 조건에서 어떤 요인이 정확도를 지배하는지, 그리고 다른 sensing domain의 설계 원리가 Wi-Fi CSI에서 언제 유지·붕괴하는지 분석하는 것이다.

## 분석 대상과 출력

```text
room geometry / multipath complexity / target
bandwidth / Tx-Rx geometry / number of links / phase-time error
    -> controlled RF forward simulation and measurement
    -> localization/reconstruction accuracy, ghost, uncertainty
    -> 영향도, 상호작용, 적용 가능 조건
```

출력은 “이 방에는 이 배치가 정답”이 아니라 다음과 같은 설계 지침이다.

- 어떤 task에서 bandwidth보다 배치가 더 중요한가?
- Rx를 추가해도 phase error 때문에 이득이 사라지는 경계는 어디인가?
- room size, furniture, wall material 중 무엇이 multipath-induced error를 주도하는가?
- occupancy, large-object localization, coarse structure reconstruction은 각각 어느 조건에서 가능한가?

## 분석할 요인

| 요인 | 조작 변수 | 예상 영향 | 주의할 점 |
|---|---|---|---|
| 방 geometry | 크기, 종횡비, 복도/방 형태 | visibility와 경로 길이 분포 변화 | 방 크기만으로 효과를 설명하면 안 됨 |
| 구조 복잡도 | 벽, 가구 수·배치·재질 | multipath, clutter, ghost 변화 | 반사는 잡음일 수도 정보일 수도 있음 |
| bandwidth | 관측 주파수 폭 | 가까운 delay 경로의 분리 능력 변화 | SNR·Wi-Fi mode 변화와 분리해 비교 |
| Tx/Rx geometry | 위치, 방향, link diversity | 공간 모호성 및 coverage 변화 | 가까운 Rx는 독립 정보가 적을 수 있음 |
| Rx/Tx 수 | link 수 | 관측량과 spatial diversity 변화 | 단순 수 증가와 geometry 효과를 분리 |
| 동기화 품질 | CFO/SFO, phase drift, delay offset | coherent fusion 가능성 변화 | 독립 ESP32에서 가장 큰 교란 후보 |
| 표적 | 크기, 재질, 위치, 정적/동적 여부 | 산란 강도와 식별 가능성 변화 | 위치 검출과 모양 복원을 구분 |

## 다른 센서 도메인에서 가져올 검증 질문

LiDAR에서는 시야와 sensor pose, UWB에서는 bandwidth·NLOS·anchor geometry, coherent multistatic radar에서는 aperture·waveform·phase coherence가 성능 요인으로 다뤄진다 `[확인 필요: 원문 비교]`.

Wi-Fi CSI에서 검증할 것은 그 원리가 존재한다는 사실이 아니라 다음이다.

1. 같은 요인이 실제로 CSI accuracy를 설명하는가?
2. 영향의 크기와 우선순위가 다른가?
3. 독립 장치의 phase/time error가 그 원리를 무효화하는가?

## 식별가능성 점검

정적 방 구조, 고정 가구, device offset은 모두 static CSI에 섞인다. 하나의 CSI snapshot만으로 이들을 유일하게 분리하는 것은 일반적으로 어렵다 `[내 판단]`.

따라서 첫 분석 task는 빈 방 baseline에 대한 차분 CSI로 단일 이동 표적을 localization하는 것으로 제한한다. 정적 room/structure reconstruction은 calibrated phase와 물질·벽 prior가 추가된 별도 조건으로 분리한다. 이를 섞어 평가하면 환경 정보를 이미 알고 있는 simulator가 답을 알려주는 정보 누수가 생길 수 있다.

## 최소 실험 설계

### Stage 1: simulator 영향도 분석

1. WaveVerse에서 단순 방/긴 복도/가구가 많은 방을 만든다.
2. 단일 큰 표적을 같은 위치 집합에 놓는다.
3. bandwidth, Rx 수, 배치, phase drift를 한 번에 하나씩 바꾸고 이후에는 요인 쌍도 함께 바꾼다.
4. 위치 오차, ghost rate, uncertainty, 실패율을 기록한다.

### Stage 2: 상호작용 분석

다음 비교로 단순 상관관계를 피한다.

- 같은 Rx 수, 다른 geometry
- 같은 geometry, 다른 bandwidth
- 같은 모든 조건, 다른 phase/time error
- 같은 room size, 다른 furniture/material complexity

분산 분석(ANOVA) 또는 factorial regression으로 각 요인의 main effect와 interaction effect를 보고한다 `[방법 후보]`.

### Stage 3: 실제 장치 확인

ESP32에서 단순 방·단일 표적 조건부터 재현한다. simulator와 실제 장치의 차이는 실패가 아니라, antenna pattern·AGC·clock drift·재질 모델 불일치라는 새 영향 요인의 증거다.

## 비교 기준

- 고정된 기본 배치와 bandwidth
- 무작위 배치
- phase/time error를 무시한 이상적 coherent 조건
- 다른 요인은 고정하고 한 요인만 조작한 조건

정확도만 보지 않는다. 위치 오차, reconstruction IoU(가능한 경우), ghost rate, uncertainty calibration, 계산·설치 비용을 함께 기록한다.

## 반증 조건

- 조작한 요인들이 반복 측정에서도 정확도 차이를 만들지 않는다.
- phase error를 넣으면 geometry·bandwidth의 효과가 모든 조건에서 완전히 사라진다. 이 경우 연구의 핵심은 configuration 분석이 아니라 synchronization 한 요인으로 축소해야 한다.
- simulator에서 찾은 영향 순서가 실제 ESP32에서 재현되지 않으며, model mismatch로 설명할 수 없다.

## 현재 결론

**조건부 타당.** 센서 배치, bandwidth, multipath, synchronization을 각각 다룬 선행연구는 있지만, 저가·비동기 Wi-Fi CSI에서 이 요인들의 상대적 영향과 상호작용을 reconstruction task별로 정리한 분석은 부족한 것으로 보인다 `[확인 필요: 체계 문헌 조사]`.

따라서 연구의 주장은 다음으로 제한한다.

> 저가 분산 Wi-Fi CSI sensing에서 reconstruction accuracy를 좌우하는 환경·신호·센서·동기화 요인을 정량화하고, 다른 sensing domain의 설계 직관이 적용되는 범위를 밝힌다.

## 다음 행동

2026-09-08에 LiDAR, UWB, multistatic radar의 논문을 비교해 각 도메인의 정확도 영향 요인, 관측량, 동기화 가정, 실험 설계를 표로 정리한다.
