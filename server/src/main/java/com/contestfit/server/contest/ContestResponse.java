package com.contestfit.server.contest;

import java.time.LocalDateTime;
import java.util.List;

public record ContestResponse(
        Long id,
        String title,
        String category,
        LocalDateTime deadline,
        String sourceUrl,
        ValidationStatus validationStatus,
        List<EligibilityRuleResponse> eligibilityRules
) {
    public static ContestResponse from(Contest contest) {
        return new ContestResponse(
                contest.getId(),
                contest.getTitle(),
                contest.getCategory(),
                contest.getDeadline(),
                contest.getSourceUrl(),
                contest.getValidationStatus(),
                contest.getEligibilityRules().stream().map(EligibilityRuleResponse::from).toList()
        );
    }
}
