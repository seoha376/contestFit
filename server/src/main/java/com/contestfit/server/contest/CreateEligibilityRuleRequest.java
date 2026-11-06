package com.contestfit.server.contest;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record CreateEligibilityRuleRequest(
        @NotNull EligibilityField field,
        @NotNull ConditionOperator operator,
        @NotBlank @Size(max = 500) String value,
        @NotBlank String evidenceQuote
) {
}
