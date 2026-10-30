from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from posting_validation.collector import PoliteClient, collect_contests, contest_list_url, contest_urls_from_list_html
from posting_validation.eligibility import PROFILES, decide_eligibility
from posting_validation.evaluator import evidence_matches, evaluate, render_eligibility_report
from posting_validation.extractor import extract_posting
from posting_validation.parser import html_to_text


class EligibilityTests(unittest.TestCase):
    def test_contest_list_source_keeps_existing_items_and_obeys_request_budget(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            (root / "raw").mkdir()
            (root / "raw" / "old.html").write_text("<title>기존 공모전</title>", encoding="utf-8")
            (root / "raw" / "old.txt").write_text("기존 공모전\n마감일2026.12.01", encoding="utf-8")
            existing = {
                "items": [{
                    "id": "old", "source_url": "https://linkareer.com/activity/1", "type": "공모전",
                    "raw_html_file": "raw/old.html", "raw_text_file": "raw/old.txt",
                }]
            }
            list_url = contest_list_url(1)
            activity_url = "https://linkareer.com/activity/999"
            responses = {
                "https://linkareer.com/robots.txt": b"User-agent: *\nAllow: /\n",
                list_url: f'<a href="/activity/999">new</a><a href="/activity/999">duplicate</a>'.encode(),
                activity_url: (
                    '<title>새 공모전 | 공모전 대외활동-링커리어</title>'
                    '<script>{"@id":"https://linkareer.com/list/contest","name":"공모전"}</script>'
                    '<h1>새 공모전</h1><p>마감일2026.11.30</p>'
                ).encode(),
            }
            clock = FakeClock()
            client = PoliteClient(
                max_requests=80, min_delay=2.0, clock=clock,
                transport=lambda url, _headers: responses[url],
            )

            manifest = collect_contests(root, existing, target_total=2, now=datetime(2026, 10, 28, tzinfo=UTC), client=client)

            self.assertEqual(manifest["counts"], {"공모전": 2})
            self.assertEqual(manifest["existing_count"], 1)
            self.assertEqual(manifest["new_count"], 1)
            self.assertEqual(manifest["request_count"], 3)
            self.assertLessEqual(manifest["request_limit"], 80)
            self.assertEqual(clock.sleeps, [2.0, 2.0])
            self.assertEqual([item["source_url"] for item in manifest["items"]], [
                "https://linkareer.com/activity/1", activity_url,
            ])

    def test_contest_list_url_and_candidate_parser_reject_unexpected_urls(self) -> None:
        self.assertEqual(contest_list_url(3), "https://linkareer.com/list/contest?page=3")
        html = '''
        <a href="/activity/123">one</a>
        <a href="https://linkareer.com/activity/456">two</a>
        <a href="https://evil.example/activity/789">evil</a>
        <a href="/activity/123?from=list">query</a>
        '''
        self.assertEqual(contest_urls_from_list_html(html), [
            "https://linkareer.com/activity/123", "https://linkareer.com/activity/456",
        ])

    def test_extractor_adds_eligibility_fields_with_verbatim_evidence(self) -> None:
        html = '<title>서울 청년 기획 공모전</title>'
        text = """서울 청년 기획 공모전
참가 자격
- 만 18세 이상 만 29세 이하
- 서울특별시 거주자
- 대학 재학생 및 휴학생
- 사업자 등록이 없는 자
- 개인 또는 3인 이내 팀
- 수상자는 시상식 참석 필수
제출 형식
- PDF, A4 10쪽 이내, 20MB 이하
접수 방법
- 이메일 제출"""

        item = extract_posting("https://linkareer.com/activity/2", html, text)

        self.assertEqual(item["age"], {"value": {"min": 18, "max": 29}, "evidence": "- 만 18세 이상 만 29세 이하"})
        self.assertEqual(item["student_status"]["value"], ["재학생", "휴학생"])
        self.assertEqual(item["student_status"]["evidence"], "- 대학 재학생 및 휴학생")
        self.assertEqual(item["region_restriction"]["value"], {"regions": ["서울"], "basis": "residence"})
        self.assertEqual(item["region_restriction"]["evidence"], "- 서울특별시 거주자")
        self.assertEqual(item["business_registration"]["value"], "불가")
        self.assertEqual(item["business_registration"]["evidence"], "- 사업자 등록이 없는 자")
        self.assertEqual(item["team_policy"]["value"], "둘다")
        self.assertEqual(item["team_policy"]["evidence"], "- 개인 또는 3인 이내 팀")
        self.assertEqual(item["other_conditions"]["value"], ["수상자는 시상식 참석 필수"])
        self.assertEqual(item["other_conditions"]["evidence"], "- 수상자는 시상식 참석 필수")
        self.assertEqual(item["submission_format"], {
            "value": "PDF, A4 10쪽 이내, 20MB 이하",
            "evidence": "- PDF, A4 10쪽 이내, 20MB 이하",
        })

    def test_category_chips_do_not_fill_deliverable_or_submission_format(self) -> None:
        html = "<title>영상 공모전</title>"
        text = "공모분야\n사진/영상/UCC\n캐릭터/만화/게임\n추가혜택-"
        item = extract_posting("https://linkareer.com/activity/3", html, text)
        self.assertIsNone(item["deliverable_type"]["value"])
        self.assertIsNone(item["submission_format"]["value"])

    def test_submission_format_keeps_each_noncontiguous_evidence_sentence(self) -> None:
        html = "<title>AI 영상 공모전</title>"
        text = "AI 영상 공모전\n제출 형식\n- 영상 길이: 30초~120초\n- 화면 비율: 16:9\n- 해상도: HD(720p) 이상\n- 제작 가이드 준수"
        item = extract_posting("https://linkareer.com/activity/4", html, text)
        self.assertEqual(item["submission_format"]["value"], "영상 길이: 30초~120초; 화면 비율: 16:9; 해상도: HD(720p) 이상")
        self.assertEqual(item["submission_format"]["evidence"], [
            "- 영상 길이: 30초~120초", "- 화면 비율: 16:9", "- 해상도: HD(720p) 이상",
        ])
        self.assertTrue(evidence_matches(item["submission_format"]["evidence"], text))

    def test_minor_guardian_consent_is_not_an_age_ceiling(self) -> None:
        html = "<title>서비스 공모전</title>"
        text = "서비스 공모전\n- 만 14세 미만은 개인정보·저작권 동의서에 법정대리인 동의·서명 필요"
        item = extract_posting("https://linkareer.com/activity/5", html, text)
        self.assertIsNone(item["age"]["value"])
        self.assertIn("만 14세 미만은 개인정보·저작권 동의서에 법정대리인 동의·서명 필요", item["other_conditions"]["value"])

    def test_detailed_student_status_beats_compact_metadata(self) -> None:
        html = "<title>대학생 공모전</title>"
        text = "기업형태기타참여대상대학생시상규모100만원\n대학생 공모전\n전국 대학생·대학원생 (휴학생·수료생 포함)"
        item = extract_posting("https://linkareer.com/activity/6", html, text)
        self.assertEqual(item["student_status"]["value"], ["재학생", "휴학생", "대학원생", "수료생"])
        self.assertEqual(item["student_status"]["evidence"], "전국 대학생·대학원생 (휴학생·수료생 포함)")

    def test_contest_conditions_use_body_not_linkareer_target_chip(self) -> None:
        html = "<title>대학 공모전</title>"
        text = "기업형태기타참여대상대상 제한 없음시상규모100만원\n대학 공모전\n지원자격\n- 국내 대학(원)생만 참가 가능"
        item = extract_posting("https://linkareer.com/activity/body-first", html, text)

        self.assertEqual(item["student_status"]["value"], ["재학생", "대학원생"])
        self.assertEqual(item["student_status"]["evidence"], "- 국내 대학(원)생만 참가 가능")
        self.assertTrue(item["student_status"]["chip_mismatch"])
        self.assertEqual(item["student_status"]["chip_evidence"], "기업형태기타참여대상대상 제한 없음시상규모100만원")

    def test_region_requires_specific_place_and_records_basis(self) -> None:
        unrestricted = extract_posting(
            "https://linkareer.com/activity/region-open", "<title>전국 공모전</title>",
            "전국 공모전\n참가자격\n- 전국 누구나 참여 가능",
        )
        residence = extract_posting(
            "https://linkareer.com/activity/region-home", "<title>서울 공모전</title>",
            "서울 공모전\n참가자격\n- 서울특별시 거주자",
        )
        school = extract_posting(
            "https://linkareer.com/activity/region-school", "<title>부산 공모전</title>",
            "부산 공모전\n참가자격\n- 부산 소재 대학 재학생",
        )

        self.assertIsNone(unrestricted["region_restriction"]["value"])
        self.assertIsNone(unrestricted["region_restriction"]["evidence"])
        self.assertEqual(residence["region_restriction"]["value"], {"regions": ["서울"], "basis": "residence"})
        self.assertEqual(school["region_restriction"]["value"], {"regions": ["부산"], "basis": "school"})

    def test_team_maximum_does_not_invent_minimum_or_exact_size(self) -> None:
        maximum = extract_posting(
            "https://linkareer.com/activity/team-max", "<title>팀 공모전</title>",
            "팀 공모전\n- 개인 또는 팀(최대 4인) 참가 가능",
        )
        unknown = extract_posting(
            "https://linkareer.com/activity/team-unknown", "<title>팀 공모전</title>",
            "팀 공모전\n- 1인(또는 팀) 참가 가능",
        )

        self.assertEqual(maximum["team_policy"]["value"], "둘다")
        self.assertEqual(maximum["team_size"]["value"], {"min": None, "max": 4})
        self.assertIsNone(unknown["team_size"]["value"])

    def test_nationality_major_and_business_are_extracted_from_body(self) -> None:
        item = extract_posting(
            "https://linkareer.com/activity/conditions", "<title>창업 공모전</title>",
            "창업 공모전\n지원자격\n- 대한민국 국민\n- 디자인 관련 전공자\n- 창업 3년 미만 사업자",
        )
        name_only = extract_posting(
            "https://linkareer.com/activity/name-only", "<title>개인 공모전</title>",
            "개인 공모전\n- 개인 참가 가능, 법인·단체·사업자 명의 불가",
        )

        self.assertEqual(item["nationality"]["value"], "대한민국")
        self.assertEqual(item["major_scope"]["value"], "디자인 관련 전공")
        self.assertEqual(item["business_registration"]["value"], "연차")
        self.assertEqual(item["business_registration"]["years"], 3)
        self.assertFalse(item["business_registration"]["name_restriction"])
        self.assertEqual(name_only["business_registration"]["value"], "무관")
        self.assertTrue(name_only["business_registration"]["name_restriction"])

    def test_different_division_eligibility_creates_multiple_sections(self) -> None:
        item = extract_posting(
            "https://linkareer.com/activity/divisions", "<title>데이터 공모전</title>",
            "데이터 공모전\n- 문제발굴 부문: 문제 해결이 필요한 기관 또는 개인\n- 문제해결 부문: 데이터 분석에 관심 있는 개인 또는 최대 4인 팀",
        )

        self.assertEqual([section["name"] for section in item["sections"]], ["문제발굴 부문", "문제해결 부문"])
        self.assertEqual(item["sections"][0]["other_conditions"]["value"], ["문제 해결이 필요한 기관 또는 개인"])
        self.assertEqual(item["sections"][1]["team_size"]["value"], {"min": None, "max": 4})

    def test_team_size_bounds_are_enforced_even_when_other_conditions_are_unknown(self) -> None:
        fields = complete_conditions()
        fields["student_status"] = {"value": ["재학생", "휴학생"], "evidence": "대학생과 휴학생 지원 가능"}
        fields["team_policy"] = {"value": "둘다", "evidence": "개인 또는 2인 이하 팀"}
        fields["team_size"] = {"value": "2인 이하", "evidence": "개인 또는 2인 이하 팀"}
        decision = decide_eligibility(fields, PROFILES[2])
        self.assertEqual(decision["result"], "지원 불가")
        self.assertEqual(decision["reasons"][0]["evidence"], "개인 또는 2인 이하 팀")

        team_only = extract_posting(
            "https://linkareer.com/activity/7", "<title>팀 공모전</title>", "팀 공모전\n대학생 3~4인이 1팀으로 참가",
        )
        self.assertEqual(team_only["team_policy"]["value"], "팀만")

    def test_decision_uses_explicit_disqualification_before_unknowns(self) -> None:
        fields = complete_conditions()
        eligible = decide_eligibility(fields, PROFILES[0])
        worker = decide_eligibility(fields, PROFILES[1])
        self.assertEqual(eligible["result"], "지원 가능")
        self.assertEqual(worker["result"], "지원 불가")
        self.assertEqual(worker["reasons"][0]["evidence"], "대학 재학생만 지원 가능")

        fields["region_restriction"] = {"value": None, "evidence": None}
        self.assertEqual(decide_eligibility(fields, PROFILES[0])["result"], "확인 필요")

        fields = complete_conditions()
        fields["other_conditions"] = {"value": ["관련 전공 이수자"], "evidence": "관련 전공 이수자만 지원 가능"}
        decision = decide_eligibility(fields, PROFILES[0])
        self.assertEqual(decision["result"], "확인 필요")
        self.assertEqual(decision["reasons"][0]["evidence"], "관련 전공 이수자만 지원 가능")

    def test_evaluator_adds_condition_and_profile_sections_without_accuracy_term(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            (root / "raw").mkdir()
            (root / "raw" / "a.txt").write_text(
                "공모전 A\n만 18세 이상 30세 이하\n대학 재학생만 지원 가능\n서울 거주자\n사업자 등록 불가\n개인만 참가 가능",
                encoding="utf-8",
            )
            record = base_record("a", complete_conditions())
            metrics = evaluate([record], root)
            report = render_eligibility_report(metrics, {"counts": {"공모전": 1}, "existing_count": 1, "new_count": 0, "request_count": 0, "request_limit": 80})

            self.assertEqual(metrics["eligibility"]["nontrivial_conditions"]["rate"], 1.0)
            self.assertEqual(metrics["eligibility"]["profile_distribution"][PROFILES[0]["name"]]["지원 가능"], 1)
            self.assertEqual(metrics["eligibility"]["split_postings"]["rate"], 1.0)
            for distribution in metrics["eligibility"]["profile_distribution"].values():
                self.assertEqual(sum(distribution.values()), 1)
            self.assertLessEqual(len(metrics["eligibility"]["cases"]), 10)
            self.assertIn("정답표 없는 근거 기반 일관성 평가", report)
            self.assertIn("## D. 비자명 조건 비율", report)
            self.assertIn("프로필별 판정 분포", report)
            self.assertIn("## F. 확인 필요·지원 불가 사례 (최대 10건)", report)
            self.assertIn("근거 `", report)
            self.assertNotIn("정확도", report)


def complete_conditions() -> dict:
    return {
        "age": {"value": {"min": 18, "max": 30}, "evidence": "만 18세 이상 30세 이하"},
        "student_status": {"value": ["재학생"], "evidence": "대학 재학생만 지원 가능"},
        "region_restriction": {"value": "서울", "evidence": "서울 거주자"},
        "business_registration": {"value": "불가", "evidence": "사업자 등록 불가"},
        "team_policy": {"value": "개인만", "evidence": "개인만 참가 가능"},
        "other_conditions": {"value": None, "evidence": None},
    }


def base_record(item_id: str, conditions: dict) -> dict:
    record = {
        "id": item_id, "source_url": f"https://linkareer.com/activity/{item_id}", "raw_text_file": f"raw/{item_id}.txt",
        "type": {"value": "공모전", "evidence": "공모전 A"},
        "title": {"value": "공모전 A", "evidence": "공모전 A"},
    }
    for name in [
        "organizer", "deadline", "region", "eligibility", "participation_form", "team_size",
        "onsite_required", "reward", "period", "deliverable_type", "rights_clause", "entry_fee",
        "submission_format",
    ]:
        record[name] = {"value": None, "evidence": None}
    record.update(conditions)
    return record


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


if __name__ == "__main__":
    unittest.main()
