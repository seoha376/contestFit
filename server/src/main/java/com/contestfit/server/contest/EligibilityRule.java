package com.contestfit.server.contest;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "eligibility_rules")
public class EligibilityRule {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "contest_id", nullable = false)
    @JsonIgnore
    private Contest contest;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private EligibilityField field;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private ConditionOperator operator;

    @Column(name = "rule_value", nullable = false, length = 500)
    private String value;

    @Column(name = "evidence_quote", nullable = false, columnDefinition = "TEXT")
    private String evidenceQuote;

    protected EligibilityRule() {
    }

    public EligibilityRule(EligibilityField field, ConditionOperator operator, String value, String evidenceQuote) {
        this.field = field;
        this.operator = operator;
        this.value = value;
        this.evidenceQuote = evidenceQuote;
    }

    void setContest(Contest contest) { this.contest = contest; }
    public Long getId() { return id; }
    public EligibilityField getField() { return field; }
    public ConditionOperator getOperator() { return operator; }
    public String getValue() { return value; }
    public String getEvidenceQuote() { return evidenceQuote; }
}
