package com.contestfit.server.contest;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.LocalDateTime;
import java.util.List;

public record CreateContestRequest(
        @NotBlank @Size(max = 255) String title,
        @Size(max = 100) String category,
        LocalDateTime deadline,
        @NotBlank @Size(max = 2048) String sourceUrl,
        ValidationStatus validationStatus,
        List<@Valid CreateEligibilityRuleRequest> eligibilityRules
) {
}
