package com.contestfit.server.contest;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import jakarta.persistence.Table;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "contests")
public class Contest {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 255)
    private String title;

    @Column(length = 100)
    private String category;

    private LocalDateTime deadline;

    @Column(name = "source_url", nullable = false, length = 2048)
    private String sourceUrl;

    @Enumerated(EnumType.STRING)
    @Column(name = "validation_status", nullable = false, length = 20)
    private ValidationStatus validationStatus = ValidationStatus.DRAFT;

    @Column(name = "seed_payload", columnDefinition = "JSON")
    private String seedPayload;

    @OneToMany(mappedBy = "contest", cascade = CascadeType.ALL, orphanRemoval = true)
    private final List<EligibilityRule> eligibilityRules = new ArrayList<>();

    protected Contest() {
    }

    public Contest(String title, String category, LocalDateTime deadline, String sourceUrl, ValidationStatus validationStatus) {
        this(title, category, deadline, sourceUrl, validationStatus, null);
    }

    public Contest(String title, String category, LocalDateTime deadline, String sourceUrl, ValidationStatus validationStatus, String seedPayload) {
        this.title = title;
        this.category = category;
        this.deadline = deadline;
        this.sourceUrl = sourceUrl;
        this.validationStatus = validationStatus == null ? ValidationStatus.DRAFT : validationStatus;
        this.seedPayload = seedPayload;
    }

    public void addEligibilityRule(EligibilityRule rule) {
        rule.setContest(this);
        eligibilityRules.add(rule);
    }

    public Long getId() { return id; }
    public String getTitle() { return title; }
    public String getCategory() { return category; }
    public LocalDateTime getDeadline() { return deadline; }
    public String getSourceUrl() { return sourceUrl; }
    public ValidationStatus getValidationStatus() { return validationStatus; }
    public String getSeedPayload() { return seedPayload; }
    public List<EligibilityRule> getEligibilityRules() { return List.copyOf(eligibilityRules); }
}
