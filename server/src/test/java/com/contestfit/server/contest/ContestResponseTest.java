package com.contestfit.server.contest;

import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;

class ContestResponseTest {
    @Test
    void mapsContestAndEligibilityEvidenceToResponse() {
        Contest contest = new Contest(
                "IT 서비스 아이디어 개발 공모전",
                "IT 서비스",
                LocalDateTime.of(2026, 11, 18, 17, 0),
                "https://example.test/notice",
                ValidationStatus.VERIFIED
        );
        contest.addEligibilityRule(new EligibilityRule(
                EligibilityField.TEAM_SIZE,
                ConditionOperator.MAX,
                "4",
                "팀 구성: 최대 4인"
        ));

        ContestResponse response = ContestResponse.from(contest);

        assertThat(response.title()).isEqualTo("IT 서비스 아이디어 개발 공모전");
        assertThat(response.eligibilityRules()).singleElement().satisfies(rule -> {
            assertThat(rule.field()).isEqualTo(EligibilityField.TEAM_SIZE);
            assertThat(rule.evidenceQuote()).isEqualTo("팀 구성: 최대 4인");
        });
    }
}
