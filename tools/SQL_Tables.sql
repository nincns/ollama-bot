-- Vollständiges Datenbankschema für das Ollama-Bot-System
-- Multi-User-kompatibel mit referenzieller Integrität
-- Aktualisiert: 2025-05-22
-- Filename: SQL_Tables.sql

CREATE TABLE IF NOT EXISTS db_meta (
    version VARCHAR(10) PRIMARY KEY,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scripts (
    id INT(11) AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type ENUM('sh', 'py') NOT NULL,
    version VARCHAR(50),
    description TEXT,
    parameters TEXT,
    tags TEXT,
    content TEXT,
    is_active TINYINT(1) DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE (name, type)
);

CREATE TABLE IF NOT EXISTS prompts (
    id INT(11) AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    role ENUM('system', 'pre', 'post', 'analysis', 'other') NOT NULL,
    version VARCHAR(50),
    description TEXT,
    tags TEXT,
    content TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'de',
    model VARCHAR(100),
    is_active TINYINT(1) DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_profile (
    user_id BIGINT(20) PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    messenger_id VARCHAR(255),
    role ENUM('admin', 'user', 'disabled') DEFAULT 'disabled',
    preferred_language VARCHAR(10) DEFAULT 'de',
    frequent_script_ids TEXT,
    last_active DATETIME,
    usage_pattern TEXT,
    meta_notes TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
    id BIGINT(20) AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT(20),
    user_message TEXT,
    cleaned_prompt TEXT,
    model_response TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    model_used VARCHAR(50),
    associated_script_id INT,
    system_prompt_id INT,
    pre_prompt_id INT,
    post_prompt_id INT,
    message_status ENUM('new', 'queued', 'progress', 'solved') DEFAULT 'new';
    agent VARCHAR(50),
    metric ENUM('low', 'normal', 'high', 'critical') DEFAULT 'normal',
    dialog_id VARCHAR(64),
    locked_by_agent VARCHAR(50),
    locked_at DATETIME,
    processing_started_at DATETIME,
    processing_finished_at DATETIME,
    failure_reason TEXT,
    response_sent TINYINT(1) DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES user_profile(user_id) ON DELETE SET NULL,
    FOREIGN KEY (associated_script_id) REFERENCES scripts(id) ON DELETE SET NULL,
    FOREIGN KEY (system_prompt_id) REFERENCES prompts(id) ON DELETE SET NULL,
    FOREIGN KEY (pre_prompt_id) REFERENCES prompts(id) ON DELETE SET NULL,
    FOREIGN KEY (post_prompt_id) REFERENCES prompts(id) ON DELETE SET NULL
);

CREATE INDEX idx_conversations_status ON conversations(message_status);
CREATE INDEX idx_conversations_dialog_id ON conversations(dialog_id);
CREATE INDEX idx_conversations_user_timestamp ON conversations(user_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS conversation_log (
    id BIGINT(20) AUTO_INCREMENT PRIMARY KEY,
    conversation_id BIGINT(20),
    role ENUM('user', 'assistant', 'system', 'meta') NOT NULL,
    message TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reasoning_log (
    id BIGINT(20) AUTO_INCREMENT PRIMARY KEY,
    conversation_id BIGINT(20),
    reasoning TEXT,
    confidence_score FLOAT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS conversation_history (
    id BIGINT(20) AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT(20),
    prompt TEXT,
    response TEXT,
    model_used VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_profile(user_id)
);

CREATE TABLE IF NOT EXISTS script_usage (
    id BIGINT(20) AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT(20),
    script_id INT,
    parameters_used TEXT,
    result TEXT,
    executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('queued', 'running', 'done', 'error') DEFAULT 'queued',
    FOREIGN KEY (user_id) REFERENCES user_profile(user_id),
    FOREIGN KEY (script_id) REFERENCES scripts(id)
);

CREATE TABLE IF NOT EXISTS agent_log (
    id BIGINT(20) AUTO_INCREMENT PRIMARY KEY,
    agent_name VARCHAR(100) NOT NULL,
    log_type ENUM('startup', 'status', 'assignment', 'warning', 'info', 'error') NOT NULL,
    conversation_id BIGINT(20) NULL,
    message TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS agent_status (
    agent_name VARCHAR(100) PRIMARY KEY,
    hostname VARCHAR(100),
    last_seen DATETIME,
    performance_class ENUM('cpu', 'gpu', 'low', 'medium', 'high') DEFAULT NULL,
    recommended_models TEXT,
    model_list TEXT,
    model_active TEXT,
    runtime_status TEXT,
    is_available TINYINT(1) DEFAULT TRUE,
    notes TEXT,
    cpu_load_percent FLOAT,
    mem_used_percent FLOAT,
    gpu_util_percent FLOAT,
    gpu_mem_used_mb INT,
    gpu_mem_total_mb INT 
);

CREATE TABLE IF NOT EXISTS model_catalog (
    id INT(11) AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(100),
    provider ENUM('ollama', 'openai', 'local', 'huggingface') DEFAULT 'ollama',
    version VARCHAR(50),
    model_size ENUM('small', 'medium', 'large', 'xl'),
    language_support TEXT,
    supports_chat TINYINT(1) DEFAULT TRUE,
    supports_reasoning TINYINT(1) DEFAULT FALSE,
    supports_knowledge TINYINT(1) DEFAULT FALSE,
    tags TEXT,
    is_active TINYINT(1) DEFAULT TRUE,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE (model_name, version)
);