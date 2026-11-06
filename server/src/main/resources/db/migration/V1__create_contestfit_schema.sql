CREATE TABLE contests (
    id BIGINT NOT NULL AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100) NULL,
    deadline DATETIME(6) NULL,
    source_url VARCHAR(2048) NOT NULL,
    validation_status VARCHAR(20) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id)
);

CREATE TABLE eligibility_rules (
    id BIGINT NOT NULL AUTO_INCREMENT,
    contest_id BIGINT NOT NULL,
    field VARCHAR(30) NOT NULL,
    operator VARCHAR(20) NOT NULL,
    rule_value VARCHAR(500) NOT NULL,
    evidence_quote TEXT NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_eligibility_rules_contest
        FOREIGN KEY (contest_id) REFERENCES contests(id) ON DELETE CASCADE
);

CREATE TABLE user_profiles (
    id BIGINT NOT NULL AUTO_INCREMENT,
    profile_name VARCHAR(100) NOT NULL,
    major VARCHAR(150) NULL,
    grade INT NULL,
    enrollment_status VARCHAR(30) NULL,
    age INT NULL,
    team_size INT NULL,
    region VARCHAR(50) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id)
);

CREATE TABLE verdict_history (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_profile_id BIGINT NOT NULL,
    contest_id BIGINT NOT NULL,
    result VARCHAR(20) NOT NULL,
    reasons_json JSON NOT NULL,
    evaluated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT fk_verdict_history_profile
        FOREIGN KEY (user_profile_id) REFERENCES user_profiles(id) ON DELETE CASCADE,
    CONSTRAINT fk_verdict_history_contest
        FOREIGN KEY (contest_id) REFERENCES contests(id) ON DELETE CASCADE
);
