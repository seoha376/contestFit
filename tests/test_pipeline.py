from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path

from posting_validation.collector import BudgetExceeded, PoliteClient, is_linkareer_url, is_open_posting, select_recent_activity_sitemaps
from posting_validation.diagnosis import classify_null_cause
from posting_validation.evaluator import evidence_matches, evaluate, render_report
from posting_validation.extractor import classify_domain, extract_posting
from posting_validation.parser import html_to_text, parse_deadline


class PipelineTests(unittest.TestCase):
 def test_null_cause_classification_distinguishes_failure_absence_and_uncertainty(self) -> None:
    before = {"value": None, "evidence": None}
    recovered = {"value": "서울", "evidence": "활동지역\n서울"}
    self.assertEqual(classify_null_cause("region", before, recovered, "활동지역\n서울")["classification"], "본문에 정보 존재 + 추출 실패")
    self.assertEqual(classify_null_cause("region", before, before, "상세내용 없음")["classification"], "본문에 정보 없음(진짜 미기재)")
    uncertain = classify_null_cause("organizer", before, before, "주최·운영 부서 직원은 참가할 수 없습니다")
    self.assertEqual(uncertain["classification"], "판단 불가")
    self.assertEqual(uncertain["evidence"], ["주최·운영 부서 직원은 참가할 수 없습니다"])

 def test_null_diagnosis_ignores_unrelated_region_and_team_words(self) -> None:
    empty = {"value": None, "evidence": None}
    region = classify_null_cause("region", empty, empty, "관광/지역강제")
    team = classify_null_cause("team_size", empty, empty, "정책개발팀(070-7707-0507)")
    self.assertEqual(region["classification"], "본문에 정보 없음(진짜 미기재)")
    self.assertEqual(team["classification"], "본문에 정보 없음(진짜 미기재)")

 def test_polite_client_enforces_delay_budget_and_robots(self) -> None:
    clock = FakeClock()
    calls: list[str] = []

    def transport(url: str, headers: dict[str, str]) -> bytes:
        calls.append(url)
        assert headers["User-Agent"].startswith("ContestFitResearchBot/")
        return b"ok"

    client = PoliteClient(
        user_agent="ContestFitResearchBot/1.0 contact=local-validation",
        min_delay=2.0,
        max_requests=2,
        allowed=lambda url: "/blocked" not in url,
        transport=transport,
        clock=clock,
    )
    client.get("https://example.com/a")
    client.get("https://example.com/b")
    self.assertEqual(clock.sleeps, [2.0])
    self.assertEqual(calls, ["https://example.com/a", "https://example.com/b"])
    with self.assertRaises(PermissionError):
        client.get("https://example.com/blocked/1")
    with self.assertRaises(BudgetExceeded):
        client.get("https://example.com/c")

 def test_failed_request_consumes_budget_and_delay(self) -> None:
    clock = FakeClock()
    attempts = 0

    def flaky(url: str, headers: dict[str, str]) -> bytes:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("network failure")
        return b"ok"

    client = PoliteClient(max_requests=2, min_delay=2.0, transport=flaky, clock=clock)
    with self.assertRaises(OSError):
        client.get("https://example.com/first")
    self.assertEqual(client.request_count, 1)
    client.get("https://example.com/second")
    self.assertEqual(clock.sleeps, [2.0])
    self.assertEqual(client.request_count, 2)


 def test_selects_at_most_four_recent_activity_sitemaps(self) -> None:
    now = datetime(2026, 10, 27, tzinfo=UTC)
    xml = """<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://linkareer.com/sitemap/activities/1.xml</loc><lastmod>2026-10-26</lastmod></sitemap>
      <sitemap><loc>https://linkareer.com/sitemap/activities/2.xml</loc><lastmod>2026-10-25</lastmod></sitemap>
      <sitemap><loc>https://linkareer.com/sitemap/activities/3.xml</loc><lastmod>2026-10-24</lastmod></sitemap>
      <sitemap><loc>https://linkareer.com/sitemap/activities/4.xml</loc><lastmod>2026-10-23</lastmod></sitemap>
      <sitemap><loc>https://linkareer.com/sitemap/activities/old.xml</loc><lastmod>2026-09-01</lastmod></sitemap>
      <sitemap><loc>https://linkareer.com/sitemap/jobs-1.xml</loc><lastmod>2026-10-26</lastmod></sitemap>
    </sitemapindex>"""
    selected = select_recent_activity_sitemaps(xml, now=now, limit=4)
    self.assertEqual(selected, [
        "https://linkareer.com/sitemap/activities/1.xml",
        "https://linkareer.com/sitemap/activities/2.xml",
        "https://linkareer.com/sitemap/activities/3.xml",
        "https://linkareer.com/sitemap/activities/4.xml",
    ])


 def test_html_text_and_extraction_keep_verbatim_evidence(self) -> None:
    html = """<html><head><title>환경 아이디어 공모전</title></head><body>
    <h1>환경 아이디어 공모전</h1><p>주최: 푸른재단</p><p>접수기간: 2026.10.01 ~ 2026.11.30</p>
    <p>지원자격: 전국 대학생 누구나</p><p>개인 또는 4인 이내 팀</p><p>총 상금 500만원</p>
    <p>제출물: 아이디어 기획서 PDF</p><p>참가비 무료</p></body></html>"""
    text = html_to_text(html)
    item = extract_posting("https://linkareer.com/activity/1", html, text)
    self.assertEqual(item["type"]["value"], "공모전")
    self.assertEqual(item["organizer"], {"value": "푸른재단", "evidence": "주최: 푸른재단"})
    self.assertEqual(item["participation_form"]["value"], "둘다")
    self.assertEqual(item["team_size"]["value"], {"min": None, "max": 4})
    self.assertEqual(item["entry_fee"]["value"], "무료")
    self.assertTrue(evidence_matches(item["organizer"]["evidence"], text))

 def test_navigation_and_scripts_do_not_override_breadcrumb_type(self) -> None:
    html = '''<html><head><title>마케팅 동아리 모집</title><style>.x{content:"인턴"}</style>
    <script type="application/ld+json">{"itemListElement":[{"item":{"@id":"https://linkareer.com/list/club","name":"동아리"}}]}</script>
    </head><body><nav>채용/인턴 공모전 대외활동</nav><main><h1>마케팅 동아리 모집</h1></main></body></html>'''
    text = html_to_text(html)
    item = extract_posting("https://linkareer.com/activity/1", html, text)
    self.assertNotIn(".x{content", text)
    self.assertEqual(item["type"]["value"], "기타")
    self.assertEqual(item["title"]["value"], "마케팅 동아리 모집")

 def test_generic_recruit_is_not_intern_without_explicit_title_signal(self) -> None:
    generic = '<title>생산관리 채용 | 공모전 대외활동-링커리어</title><script>{"@id":"https://linkareer.com/list/recruit","name":"채용"}</script><h1>생산관리 채용</h1>'
    explicit = '<title>브랜드 마케팅 인턴 | 공모전 대외활동-링커리어</title><script>{"@id":"https://linkareer.com/list/recruit","name":"채용"}</script><h1>브랜드 마케팅 인턴</h1>'
    self.assertEqual(extract_posting("https://example/a", generic, html_to_text(generic))["type"]["value"], "기타")
    self.assertEqual(extract_posting("https://example/b", explicit, html_to_text(explicit))["type"]["value"], "인턴")

 def test_open_posting_requires_future_date_or_always_open_signal(self) -> None:
    now = datetime(2026, 10, 27, tzinfo=UTC)
    self.assertTrue(is_open_posting("마감일2026.11.30", now))
    self.assertTrue(is_open_posting("상시모집", now))
    self.assertFalse(is_open_posting("일정은 추후 공지", now))
    self.assertFalse(is_open_posting("마감일2026.10.01", now))

 def test_extraction_ignores_recommendations_after_report_marker(self) -> None:
    html = '<title>서포터즈 모집</title><script>{"@id":"https://linkareer.com/list/activity","name":"대외활동"}</script><h1>서포터즈 모집</h1><p>마감일2026.11.30</p><p>허위·과장·오류 내용이 있다면 신고해주세요.</p><p>[추천] 여행지원금 지급, 오프라인 영업 매니저</p>'
    text = html_to_text(html)
    item = extract_posting("https://example/a", html, text)
    self.assertIsNone(item["stipend"]["value"])
    self.assertIsNone(item["onsite_required"]["value"])

 def test_only_expected_linkareer_urls_are_accepted(self) -> None:
    self.assertTrue(is_linkareer_url("https://linkareer.com/activity/123", "/activity/"))
    self.assertTrue(is_linkareer_url("https://linkareer.com/sitemap/activities/138.xml", "/sitemap/activities/"))
    self.assertFalse(is_linkareer_url("https://evil.example/activity/123", "/activity/"))
    self.assertFalse(is_linkareer_url("http://linkareer.com/activity/123", "/activity/"))
    self.assertFalse(is_linkareer_url("https://linkareer.com/other/123", "/activity/"))
    self.assertFalse(is_linkareer_url("https://linkareer.com:8443/activity/123", "/activity/"))
    self.assertFalse(is_linkareer_url("https://linkareer.com/activity/../login", "/activity/"))
    self.assertFalse(is_linkareer_url("https://linkareer.com/sitemap/activities/latest.xml", "/sitemap/activities/"))


 def test_deadline_parser_rejects_expired_and_accepts_d_day(self) -> None:
    now = datetime(2026, 10, 27, tzinfo=UTC)
    self.assertEqual(parse_deadline("접수 마감 2026.11.30", now=now).date().isoformat(), "2026-11-30")
    self.assertEqual(parse_deadline("접수 마감 D-5", now=now).date().isoformat(), "2026-11-01")
    self.assertLess(parse_deadline("접수 마감 2026.09.30", now=now), now)
    self.assertEqual(parse_deadline("마감일2025.12.29\n추천 공고 D-8", now=now).date().isoformat(), "2025-12-29")

 def test_extractor_uses_dated_deadline_line_after_plain_label(self) -> None:
    html = "<title>데이터 공모전</title><h1>데이터 공모전</h1><p>접수기간</p><p>시작일2026.10.01</p><p>마감일2026.11.30</p>"
    text = html_to_text(html)
    item = extract_posting("https://example/1", html, text)
    self.assertEqual(item["deadline"], {"value": "2026-11-30", "evidence": "마감일2026.11.30"})

 def test_extractor_uses_end_of_range_when_year_is_omitted(self) -> None:
    text = "서울특별시 행정서식 개선 아이디어 공모전\n접수기간: 2026. 10. 13. ~ 11. 20. (마감일 23:59)"
    item = extract_posting("https://example.org/contest", "", text)
    self.assertEqual(item["deadline"], {
        "value": "2026-11-20",
        "evidence": "접수기간: 2026. 10. 13. ~ 11. 20. (마감일 23:59)",
    })

 def test_extractor_does_not_guess_year_for_cross_year_short_range(self) -> None:
    text = "예시 공모전\n접수기간: 2026. 12. 20. ~ 01. 15."
    item = extract_posting("https://example.org/contest", "", text)
    self.assertIsNone(item["deadline"]["value"])

 def test_structured_linkareer_labels_fill_common_attributes(self) -> None:
    html = '<title>지역 콘텐츠 서포터즈</title><script>{"@id":"https://linkareer.com/list/activity","name":"대외활동"}</script>'
    text = """지역 콘텐츠 서포터즈
주식회사 예시
팀원 모집글 보기
기업형태스타트업참여대상대학생, 직장인/일반인접수기간
시작일2026.10.19
마감일2026.11.30활동기간26.10 ~ 26.12모집인원0명활동지역
서울
상세내용"""
    item = extract_posting("https://example/a", html, text)
    self.assertEqual(item["organizer"]["value"], "주식회사 예시")
    self.assertEqual(item["eligibility"]["value"], "대학생, 직장인/일반인")
    self.assertEqual(item["region"]["value"], "서울")
    self.assertEqual(item["period"]["value"], "2026.10.19 ~ 2026.11.30")
    self.assertEqual(item["activity_period"]["value"], "26.10 ~ 26.12")

 def test_structured_contest_category_does_not_fill_submission_format(self) -> None:
    html = "<title>영상 공모전</title>"
    text = """영상 공모전
광양시
팀원 모집글 보기
기업형태공공기관/공기업참여대상대상 제한 없음시상규모270만 원접수기간
시작일2026.10.26
마감일2026.11.06홈페이지-활동혜택상장 수여공모분야
사진/영상/UCC
캐릭터/만화/게임
추가혜택-"""
    item = extract_posting("https://example/b", html, text)
    self.assertIsNone(item["deliverable_type"]["value"])
    self.assertIsNone(item["submission_format"]["value"])

 def test_deadline_is_null_when_only_d_day_is_present(self) -> None:
    html = '<title>마케팅 인턴</title><script>{"@id":"https://linkareer.com/list/recruit","name":"채용"}</script>'
    text = "마케팅 인턴\n회사\n채용 시 마감 (D-76)\n마감일채용 시 마감"
    item = extract_posting("https://example/c", html, text)
    self.assertEqual(item["deadline"], {"value": None, "evidence": None})
    self.assertEqual(item["period"], {"value": None, "evidence": None})

 def test_deadline_uses_explicit_end_date_from_labeled_application_range(self) -> None:
    html = '<title>상시 서포터즈</title><script>{"@id":"https://linkareer.com/list/activity","name":"대외활동"}</script>'
    text = "상시 서포터즈\n기관\n팀원 모집글 보기\n마감일상시모집\n[접수기간]\n2026년 10월 18일 ~ 2027년 01월 18일"
    item = extract_posting("https://example/range", html, text)
    self.assertEqual(item["deadline"]["value"], "2027-01-18")
    self.assertEqual(item["deadline"]["evidence"], "[접수기간]\n2026년 10월 18일 ~ 2027년 01월 18일")

 def test_natural_language_individual_or_two_person_team_is_extracted(self) -> None:
    html = '<title>지역 서포터즈</title><script>{"@id":"https://linkareer.com/list/activity","name":"대외활동"}</script>'
    text = "지역 서포터즈\n주식회사 예시\n팀원 모집글 보기\n혼자도, 친구와 둘이 한 팀으로도 지원할 수 있습니다"
    item = extract_posting("https://example/d", html, text)
    self.assertEqual(item["participation_form"]["value"], "둘다")
    self.assertEqual(item["team_size"]["value"], "2인")

 def test_domain_classification_supports_balanced_sampling(self) -> None:
    self.assertEqual(classify_domain("AI 데이터 분석 해커톤"), "IT/데이터")
    self.assertEqual(classify_domain("환경 보호 ESG 캠페인"), "환경/사회")
    self.assertEqual(classify_domain("브랜드 콘텐츠 마케팅"), "마케팅/콘텐츠")


 def test_evaluation_reports_evidence_rule_and_fill_metrics(self) -> None:
    import tempfile
    temp = tempfile.TemporaryDirectory(dir=Path.cwd())
    self.addCleanup(temp.cleanup)
    tmp_path = Path(temp.name)
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.txt").write_text("환경 공모전\n마감 2026.11.30\n참가비 무료\n개인 또는 팀", encoding="utf-8")
    records = [{
        "id": "a", "source_url": "https://example/a", "raw_text_file": "raw/a.txt",
        "type": {"value": "공모전", "evidence": "환경 공모전"},
        "title": {"value": "환경 공모전", "evidence": "환경 공모전"},
        "organizer": {"value": None, "evidence": None},
        "deadline": {"value": "2026-11-30", "evidence": "마감 2026.11.30"},
        "region": {"value": None, "evidence": None}, "eligibility": {"value": None, "evidence": None},
        "participation_form": {"value": "둘다", "evidence": "개인 또는 팀"},
        "team_size": {"value": None, "evidence": None},
        "onsite_required": {"value": None, "evidence": None}, "reward": {"value": None, "evidence": None},
        "period": {"value": None, "evidence": None}, "deliverable_type": {"value": None, "evidence": None},
        "rights_clause": {"value": None, "evidence": None}, "entry_fee": {"value": "무료", "evidence": "참가비 무료"},
    }]
    result = evaluate(records, tmp_path)
    self.assertEqual(result["evidence"]["overall"]["rate"], 1.0)
    self.assertEqual(result["rules"]["deadline"]["match_rate"], 1.0)
    self.assertEqual(result["rules"]["entry_fee"]["match_rate"], 1.0)
    self.assertEqual(result["fill"]["by_type"]["공모전"]["title"]["null_rate"], 0.0)
    self.assertEqual(result["evidence"]["by_field"]["organizer"], {"matched": 0, "checked": 0, "rate": None})

 def test_rule_miss_is_reported_when_extraction_has_value(self) -> None:
    import tempfile
    temp = tempfile.TemporaryDirectory(dir=Path.cwd())
    self.addCleanup(temp.cleanup)
    root = Path(temp.name)
    (root / "raw").mkdir()
    (root / "raw" / "a.txt").write_text("공모전\n참가 비용 없음", encoding="utf-8")
    record = {"id": "a", "source_url": "https://example/a", "raw_text_file": "raw/a.txt"}
    for name in ["type", "title", "organizer", "deadline", "region", "eligibility", "participation_form", "team_size", "onsite_required", "reward", "period", "deliverable_type", "rights_clause", "entry_fee"]:
        record[name] = {"value": None, "evidence": None}
    record["type"] = {"value": "공모전", "evidence": "공모전"}
    record["entry_fee"] = {"value": "무료", "evidence": "참가 비용 없음"}
    metrics = evaluate([record], root)
    self.assertEqual(metrics["rules"]["entry_fee"], {"matched": 0, "checked": 1, "match_rate": 0.0})
    report = render_report(metrics, {"request_count": 1, "request_limit": 150, "min_delay_seconds": 2.0, "counts": {"공모전": 1}, "notes": []})
    self.assertIn("### entry_fee", report)
    self.assertIn("추출값 `무료`", report)
    self.assertIn("본문 위치", report)
    self.assertNotIn("정확도", report)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds
