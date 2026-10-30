# 공고 속성 추출 검증 보고서

## 수집 요약

- 총 요청: 150 / 150 (요청 간격 최소 2.0초, 직렬 실행)
- 유형별 수집: {'공모전': 7, '대외활동': 3, '인턴': 2}
- 참고: activities 사이트맵에서 공모전 표본을 목표 20건 중 7건만 찾았습니다.
- 참고: activities 사이트맵에서 대외활동 표본을 목표 10건 중 3건만 찾았습니다.
- 참고: activities 사이트맵에서 인턴 표본을 목표 10건 중 2건만 찾았습니다.

## A. 근거 일치율

전체: {'matched': 104, 'checked': 104, 'rate': 1.0}

### 필드별

- activity_period: {'matched': 3, 'checked': 3, 'rate': 1.0}
- deadline: {'matched': 11, 'checked': 11, 'rate': 1.0}
- deliverable_type: {'matched': 7, 'checked': 7, 'rate': 1.0}
- eligibility: {'matched': 10, 'checked': 10, 'rate': 1.0}
- employment_type: {'matched': 1, 'checked': 1, 'rate': 1.0}
- entry_fee: {'matched': 1, 'checked': 1, 'rate': 1.0}
- job_role: {'matched': 0, 'checked': 0, 'rate': None}
- onsite_required: {'matched': 1, 'checked': 1, 'rate': 1.0}
- organizer: {'matched': 12, 'checked': 12, 'rate': 1.0}
- participation_form: {'matched': 3, 'checked': 3, 'rate': 1.0}
- pay: {'matched': 0, 'checked': 0, 'rate': None}
- period: {'matched': 11, 'checked': 11, 'rate': 1.0}
- region: {'matched': 5, 'checked': 5, 'rate': 1.0}
- reward: {'matched': 10, 'checked': 10, 'rate': 1.0}
- rights_clause: {'matched': 1, 'checked': 1, 'rate': 1.0}
- stipend: {'matched': 1, 'checked': 1, 'rate': 1.0}
- team_size: {'matched': 2, 'checked': 2, 'rate': 1.0}
- title: {'matched': 12, 'checked': 12, 'rate': 1.0}
- type: {'matched': 12, 'checked': 12, 'rate': 1.0}
- weekly_hours: {'matched': 1, 'checked': 1, 'rate': 1.0}
- workplace: {'matched': 0, 'checked': 0, 'rate': None}

### 유형별

- 공모전: {'matched': 62, 'checked': 62, 'rate': 1.0}
- 대외활동: {'matched': 31, 'checked': 31, 'rate': 1.0}
- 인턴: {'matched': 11, 'checked': 11, 'rate': 1.0}

## B. 규칙 기반 대조

- deadline: {'matched': 10, 'checked': 11, 'match_rate': 0.9091}
- entry_fee: {'matched': 1, 'checked': 1, 'match_rate': 1.0}
- participation_form: {'matched': 1, 'checked': 3, 'match_rate': 0.3333}
- onsite_required: {'matched': 1, 'checked': 1, 'match_rate': 1.0}

## C. 채움률

- 공통 필드 수: 11
- 유형 전용 필드 수/공통 필드 수: {'공모전': 0.2727, '대외활동': 0.2727, '인턴': 0.3636}

### 공모전

공통 필드 평균 채움률: 0.6883
- type: {'null': 0, 'total': 7, 'null_rate': 0.0, 'fill_rate': 1.0}
- title: {'null': 0, 'total': 7, 'null_rate': 0.0, 'fill_rate': 1.0}
- organizer: {'null': 0, 'total': 7, 'null_rate': 0.0, 'fill_rate': 1.0}
- deadline: {'null': 0, 'total': 7, 'null_rate': 0.0, 'fill_rate': 1.0}
- region: {'null': 7, 'total': 7, 'null_rate': 1.0, 'fill_rate': 0.0}
- eligibility: {'null': 0, 'total': 7, 'null_rate': 0.0, 'fill_rate': 1.0}
- participation_form: {'null': 5, 'total': 7, 'null_rate': 0.7143, 'fill_rate': 0.2857}
- team_size: {'null': 6, 'total': 7, 'null_rate': 0.8571, 'fill_rate': 0.1429}
- onsite_required: {'null': 6, 'total': 7, 'null_rate': 0.8571, 'fill_rate': 0.1429}
- reward: {'null': 0, 'total': 7, 'null_rate': 0.0, 'fill_rate': 1.0}
- period: {'null': 0, 'total': 7, 'null_rate': 0.0, 'fill_rate': 1.0}
- deliverable_type: {'null': 0, 'total': 7, 'null_rate': 0.0, 'fill_rate': 1.0}
- rights_clause: {'null': 6, 'total': 7, 'null_rate': 0.8571, 'fill_rate': 0.1429}
- entry_fee: {'null': 6, 'total': 7, 'null_rate': 0.8571, 'fill_rate': 0.1429}

### 대외활동

공통 필드 평균 채움률: 0.7879
- type: {'null': 0, 'total': 3, 'null_rate': 0.0, 'fill_rate': 1.0}
- title: {'null': 0, 'total': 3, 'null_rate': 0.0, 'fill_rate': 1.0}
- organizer: {'null': 0, 'total': 3, 'null_rate': 0.0, 'fill_rate': 1.0}
- deadline: {'null': 0, 'total': 3, 'null_rate': 0.0, 'fill_rate': 1.0}
- region: {'null': 0, 'total': 3, 'null_rate': 0.0, 'fill_rate': 1.0}
- eligibility: {'null': 0, 'total': 3, 'null_rate': 0.0, 'fill_rate': 1.0}
- participation_form: {'null': 2, 'total': 3, 'null_rate': 0.6667, 'fill_rate': 0.3333}
- team_size: {'null': 2, 'total': 3, 'null_rate': 0.6667, 'fill_rate': 0.3333}
- onsite_required: {'null': 3, 'total': 3, 'null_rate': 1.0, 'fill_rate': 0.0}
- reward: {'null': 0, 'total': 3, 'null_rate': 0.0, 'fill_rate': 1.0}
- period: {'null': 0, 'total': 3, 'null_rate': 0.0, 'fill_rate': 1.0}
- activity_period: {'null': 0, 'total': 3, 'null_rate': 0.0, 'fill_rate': 1.0}
- weekly_hours: {'null': 2, 'total': 3, 'null_rate': 0.6667, 'fill_rate': 0.3333}
- stipend: {'null': 2, 'total': 3, 'null_rate': 0.6667, 'fill_rate': 0.3333}

### 인턴

공통 필드 평균 채움률: 0.4545
- type: {'null': 0, 'total': 2, 'null_rate': 0.0, 'fill_rate': 1.0}
- title: {'null': 0, 'total': 2, 'null_rate': 0.0, 'fill_rate': 1.0}
- organizer: {'null': 0, 'total': 2, 'null_rate': 0.0, 'fill_rate': 1.0}
- deadline: {'null': 1, 'total': 2, 'null_rate': 0.5, 'fill_rate': 0.5}
- region: {'null': 0, 'total': 2, 'null_rate': 0.0, 'fill_rate': 1.0}
- eligibility: {'null': 2, 'total': 2, 'null_rate': 1.0, 'fill_rate': 0.0}
- participation_form: {'null': 2, 'total': 2, 'null_rate': 1.0, 'fill_rate': 0.0}
- team_size: {'null': 2, 'total': 2, 'null_rate': 1.0, 'fill_rate': 0.0}
- onsite_required: {'null': 2, 'total': 2, 'null_rate': 1.0, 'fill_rate': 0.0}
- reward: {'null': 2, 'total': 2, 'null_rate': 1.0, 'fill_rate': 0.0}
- period: {'null': 1, 'total': 2, 'null_rate': 0.5, 'fill_rate': 0.5}
- job_role: {'null': 2, 'total': 2, 'null_rate': 1.0, 'fill_rate': 0.0}
- employment_type: {'null': 1, 'total': 2, 'null_rate': 0.5, 'fill_rate': 0.5}
- workplace: {'null': 2, 'total': 2, 'null_rate': 1.0, 'fill_rate': 0.0}
- pay: {'null': 2, 'total': 2, 'null_rate': 1.0, 'fill_rate': 0.0}

## 불일치 사례 (필드별 최대 5개)


### participation_form

- 추출값 `개인` / 규칙값 `None` / 근거 `- 국민 누구나 개인 자격으로 참가 가능, 법인·단체·사업자 명의 불가` / 본문 위치 `824` / id `50bee33adad9109e`
- 추출값 `둘다` / 규칙값 `None` / 근거 `- 혼자도, 친구와 둘이 한 팀으로도 지원할 수 있습니다` / 본문 위치 `1201` / id `03a90df742d14a86`

### deadline

- 추출값 `2027-01-18` / 규칙값 `None` / 근거 `[접수기간]
2026년 10월 18일 ~ 2027년 01월 18일` / 본문 위치 `895` / id `03a90df742d14a86`

## 해석상 주의

정답표 없이 수행한 내부 일관성 평가다. 근거 존재, 독립 규칙과의 합치, null 채움 정도를 측정하며 의미적 정답 여부를 보장하지 않는다.
