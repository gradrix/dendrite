-- Initialize Dendrite Database Schema
-- Phase 8a: Execution History & Learning Foundation

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Execution history: Track every goal execution
CREATE TABLE executions (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    goal_id VARCHAR(255) NOT NULL,
    goal_text TEXT NOT NULL,
    intent VARCHAR(50),
    success BOOLEAN,
    error TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Metadata for analysis
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for executions
CREATE INDEX idx_executions_goal_id ON executions(goal_id);
CREATE INDEX idx_executions_created_at ON executions(created_at DESC);
CREATE INDEX idx_executions_success ON executions(success);
CREATE INDEX idx_executions_intent ON executions(intent);

-- Tool usage: Track which tools were used and how they performed
CREATE TABLE tool_executions (
    id SERIAL PRIMARY KEY,
    execution_id UUID REFERENCES executions(execution_id) ON DELETE CASCADE,
    tool_name VARCHAR(255) NOT NULL,
    parameters JSONB,
    result JSONB,
    success BOOLEAN,
    error TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for tool_executions
CREATE INDEX idx_tool_name ON tool_executions(tool_name);
CREATE INDEX idx_tool_success ON tool_executions(tool_name, success);
CREATE INDEX idx_tool_created_at ON tool_executions(created_at DESC);

-- Tool statistics: Aggregated metrics (updated periodically)
CREATE TABLE tool_statistics (
    tool_name VARCHAR(255) PRIMARY KEY,
    total_executions INTEGER DEFAULT 0,
    successful_executions INTEGER DEFAULT 0,
    failed_executions INTEGER DEFAULT 0,
    avg_duration_ms FLOAT,
    last_used TIMESTAMP,
    first_used TIMESTAMP,
    success_rate FLOAT GENERATED ALWAYS AS (
        CASE 
            WHEN total_executions > 0 THEN successful_executions::FLOAT / total_executions 
            ELSE 0 
        END
    ) STORED,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User feedback: Learn from user ratings
CREATE TABLE execution_feedback (
    id SERIAL PRIMARY KEY,
    execution_id UUID REFERENCES executions(execution_id) ON DELETE CASCADE,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for execution_feedback
CREATE INDEX idx_feedback_execution ON execution_feedback(execution_id);
CREATE INDEX idx_feedback_rating ON execution_feedback(rating);

-- Tool creation events: Track AI-generated tools
CREATE TABLE tool_creation_events (
    id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    tool_class VARCHAR(255),
    goal_text TEXT,
    generated_code TEXT,
    validation_passed BOOLEAN,
    validation_errors JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(50) DEFAULT 'ai' -- 'ai' or 'admin'
);

-- Indexes for tool_creation_events
CREATE INDEX idx_tool_creation_name ON tool_creation_events(tool_name);
CREATE INDEX idx_tool_creation_date ON tool_creation_events(created_at DESC);

-- Create view for easy tool performance queries
CREATE VIEW tool_performance AS
SELECT 
    te.tool_name,
    COUNT(*) as execution_count,
    SUM(CASE WHEN te.success THEN 1 ELSE 0 END) as success_count,
    SUM(CASE WHEN NOT te.success THEN 1 ELSE 0 END) as failure_count,
    ROUND((SUM(CASE WHEN te.success THEN 1 ELSE 0 END)::FLOAT / COUNT(*))::numeric, 3) as success_rate,
    ROUND(AVG(te.duration_ms)::numeric, 2) as avg_duration_ms,
    MAX(te.created_at) as last_used,
    MIN(te.created_at) as first_used
FROM tool_executions te
GROUP BY te.tool_name;

-- Create function to update tool statistics (called periodically)
CREATE OR REPLACE FUNCTION update_tool_statistics()
RETURNS void AS $$
BEGIN
    INSERT INTO tool_statistics (
        tool_name, 
        total_executions, 
        successful_executions, 
        failed_executions,
        avg_duration_ms,
        last_used,
        first_used,
        updated_at
    )
    SELECT 
        tool_name,
        COUNT(*) as total,
        SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
        SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failed,
        AVG(duration_ms) as avg_duration,
        MAX(created_at) as last_used,
        MIN(created_at) as first_used,
        NOW() as updated_at
    FROM tool_executions
    GROUP BY tool_name
    ON CONFLICT (tool_name) 
    DO UPDATE SET
        total_executions = EXCLUDED.total_executions,
        successful_executions = EXCLUDED.successful_executions,
        failed_executions = EXCLUDED.failed_executions,
        avg_duration_ms = EXCLUDED.avg_duration_ms,
        last_used = EXCLUDED.last_used,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dendrite;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dendrite;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Dendrite database initialized successfully!';
    RAISE NOTICE 'Schema version: 1.0 (Phase 8a)';
END $$;
