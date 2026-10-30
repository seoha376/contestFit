## 변경 목적

<!-- 무엇을 왜 변경했는지 적어 주세요. -->

## 주요 변경사항

- 

## 영향 범위

- [ ] Python 추출·평가
- [ ] 웹 판정 엔진
- [ ] 웹 UI
- [ ] 데이터·스키마
- [ ] 테스트
- [ ] 문서·협업 설정

## 검증

- [ ] `PYTHONPATH=src python -m unittest discover -s tests -v`
- [ ] `node --test tests/web/decision-engine.test.mjs`
- [ ] Python compileall과 JavaScript syntax check
- [ ] 필요한 경우 브라우저 수동 확인

실행 결과 또는 확인하지 못한 항목:

<!-- 결과를 적어 주세요. -->

## 데이터 및 보안

- [ ] `raw/`, `raw2/`, `.env` 및 비밀정보를 포함하지 않음
- [ ] 데이터 변경이 있다면 출처와 생성 방법을 설명함
- [ ] 기존 회귀 테스트 기대값을 임의로 변경하지 않음

## 리뷰 참고사항

<!-- 집중해서 확인할 부분, 후속 작업, 아직 결정하지 않은 사항을 적어 주세요. -->
