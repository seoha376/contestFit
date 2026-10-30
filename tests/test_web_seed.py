from __future__ import annotations

import unittest

from posting_validation.web_seed import convert_records


class WebSeedTests(unittest.TestCase):
    def test_seed_maps_only_existing_values_and_keeps_field_evidence(self) -> None:
        record = {
            "id": "a",
            "source_url": "https://linkareer.com/activity/1",
            "title": {"value": "공모전 A", "evidence": "공모전 A"},
            "organizer": {"value": "기관 A", "evidence": "기관 A"},
            "age": {"value": {"min": 14, "max": None}, "evidence": "만 14세 이상"},
            "student_status": {"value": ["재학생"], "evidence": "대학생"},
            "eligibility": {"value": "대학생", "evidence": "대학생"},
            "region_restriction": {"value": "서울", "evidence": "서울 거주자"},
            "business_registration": {"value": "필수", "evidence": "사업자 등록 필수"},
            "team_policy": {"value": "둘다", "evidence": "개인 또는 팀"},
            "team_size": {"value": "4인 이내", "evidence": "4인 이내 팀"},
            "other_conditions": {"value": ["시상식 필참"], "evidence": "시상식 필참"},
        }

        seed = convert_records([record], "2026-10-28T00:00:00+09:00")
        item = seed["contests"][0]
        section = item["sections"][0]
        self.assertEqual(item["validation_status"], "unverified")
        self.assertTrue(item["is_sample"])
        self.assertEqual(section["age"], {"min": 14, "max": None, "basis_date": None})
        self.assertEqual(section["business_reg"], {"policy": "required", "years": None, "name_restriction": False})
        self.assertEqual(section["team_size"], {"min": None, "max": 4})
        self.assertEqual(section["evidence"]["age"], "만 14세 이상")
        self.assertTrue(all(value is None for value in section["confidence"].values()))
        self.assertNotIn("raw_text", item)

    def test_body_status_overrides_unrestricted_target_chip(self) -> None:
        record = {
            "id": "dream",
            "source_url": "https://linkareer.com/activity/2",
            "title": {"value": "꿈 수필 공모전", "evidence": "꿈 수필 공모전"},
            "organizer": {"value": None, "evidence": None},
            "age": {"value": {"min": 14, "max": None}, "evidence": "만 14세 이상 꿈꾸는 누구나"},
            "student_status": {"value": ["직장인"], "evidence": "학생, 직장인 모두 환영"},
            "eligibility": {"value": "대상 제한 없음", "evidence": "참여대상 대상 제한 없음"},
            "region_restriction": {"value": None, "evidence": None},
            "business_registration": {"value": None, "evidence": None},
            "team_policy": {"value": None, "evidence": None},
            "team_size": {"value": None, "evidence": None},
            "other_conditions": {"value": None, "evidence": None},
        }
        section = convert_records([record], "2026-10-28")["contests"][0]["sections"][0]
        self.assertEqual(section["status"], {"allowed": ["직장인"], "excluded": None, "chip_mismatch": False})
        self.assertEqual(section["evidence"]["status"], "학생, 직장인 모두 환영")

    def test_business_name_prohibition_is_not_mapped_to_owner_exclusion(self) -> None:
        record = {
            "id": "uiseong",
            "source_url": "https://linkareer.com/activity/3",
            "title": {"value": "의성군 공모전", "evidence": "의성군 공모전"},
            "organizer": {"value": "의성군", "evidence": "의성군"},
            "age": {"value": None, "evidence": None},
            "student_status": {"value": "제한없음", "evidence": "대상 제한 없음"},
            "eligibility": {"value": "대상 제한 없음", "evidence": "대상 제한 없음"},
            "region_restriction": {"value": None, "evidence": None},
            "business_registration": {"value": "불가", "evidence": "법인·단체·사업자 명의 불가"},
            "team_policy": {"value": "개인만", "evidence": "개인 자격으로 참가 가능"},
            "team_size": {"value": None, "evidence": None},
            "other_conditions": {"value": None, "evidence": None},
        }
        section = convert_records([record], "2026-10-28")["contests"][0]["sections"][0]
        self.assertEqual(section["business_reg"], {"policy": "any", "years": None, "name_restriction": True})
        self.assertEqual(section["evidence"]["business_reg"], "법인·단체·사업자 명의 불가")

    def test_seed_keeps_region_basis_chip_flag_and_business_name_limit(self) -> None:
        record = {
            "id": "expanded", "source_url": "https://linkareer.com/activity/4",
            "title": {"value": "확장 공모전", "evidence": "확장 공모전"},
            "organizer": {"value": "기관", "evidence": "기관"},
            "age": {"value": None, "evidence": None},
            "student_status": {"value": ["재학생"], "evidence": "대학 재학생만", "chip_mismatch": True, "chip_evidence": "대상 제한 없음"},
            "eligibility": {"value": "대상 제한 없음", "evidence": "대상 제한 없음"},
            "major_scope": {"value": "디자인 관련 전공", "evidence": "디자인 관련 전공자"},
            "region_restriction": {"value": {"regions": ["부산"], "basis": "school"}, "evidence": "부산 소재 대학"},
            "nationality": {"value": "대한민국", "evidence": "대한민국 국민"},
            "business_registration": {"value": "무관", "evidence": "사업자 명의 불가", "years": None, "name_restriction": True},
            "team_policy": {"value": "둘다", "evidence": "개인 또는 최대 4인 팀"},
            "team_size": {"value": {"min": None, "max": 4}, "evidence": "최대 4인 팀"},
            "other_conditions": {"value": None, "evidence": None},
            "sections": [],
        }
        section = convert_records([record], "2026-10-28")["contests"][0]["sections"][0]
        self.assertEqual(section["status"]["chip_mismatch"], True)
        self.assertEqual(section["region"], {"regions": ["부산"], "basis": "school"})
        self.assertEqual(section["major_scope"], "디자인 관련 전공")
        self.assertEqual(section["nationality"], "대한민국")
        self.assertEqual(section["business_reg"], {"policy": "any", "years": None, "name_restriction": True})


if __name__ == "__main__":
    unittest.main()
