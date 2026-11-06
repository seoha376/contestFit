package com.contestfit.server.contest;

public record EligibilityRuleResponse(
        Long id,
        EligibilityField field,
        ConditionOperator operator,
        String value,
        String evidenceQuote
) {
    public static EligibilityRuleResponse from(EligibilityRule rule) {
        return new EligibilityRuleResponse(rule.getId(), rule.getField(), rule.getOperator(), rule.getValue(), rule.getEvidenceQuote());
    }
}
