CREATE TABLE log_file_state (
    app_name      VARCHAR2(200) NOT NULL,
    file_path     VARCHAR2(1000) NOT NULL,
    inode_num     NUMBER,
    offset_bytes  NUMBER DEFAULT 0 NOT NULL,
    file_size     NUMBER DEFAULT 0 NOT NULL,
    file_mtime    TIMESTAMP WITH TIME ZONE,
    updated_at    TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT log_file_state_pk PRIMARY KEY (file_path)
);

CREATE TABLE log_app_rules (
    id             NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    app_name       VARCHAR2(200) NOT NULL,
    rule_type      VARCHAR2(20) NOT NULL,
    regex_text     VARCHAR2(1000) NOT NULL,
    note           VARCHAR2(1000),
    enabled        CHAR(1) DEFAULT 'Y' NOT NULL,
    source         VARCHAR2(30) DEFAULT 'manual' NOT NULL,
    confidence     NUMBER(5,4),
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    updated_at     TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT log_app_rules_type_ck
        CHECK (rule_type IN ('normal', 'error')),
    CONSTRAINT log_app_rules_enabled_ck
        CHECK (enabled IN ('Y', 'N')),
    CONSTRAINT log_app_rules_uk
        UNIQUE (app_name, rule_type, regex_text)
);

CREATE TABLE log_warnings (
    id             NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    app_name       VARCHAR2(200) NOT NULL,
    file_path      VARCHAR2(1000) NOT NULL,
    line_no        NUMBER,
    line_hash      VARCHAR2(64) NOT NULL,
    severity       VARCHAR2(20) NOT NULL,
    source         VARCHAR2(30) NOT NULL,
    matched_rule   VARCHAR2(1000),
    log_line       CLOB NOT NULL,
    llm_reason     CLOB,
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL
);

CREATE INDEX log_warnings_app_time_ix
    ON log_warnings (app_name, created_at);

CREATE INDEX log_warnings_hash_ix
    ON log_warnings (line_hash);

CREATE INDEX log_app_rules_app_ix
    ON log_app_rules (app_name, enabled, rule_type);

exit    