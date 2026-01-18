-- Phase 10a: Goal Decomposition Learning
-- Track successful goal → subgoals patterns to learn efficient decomposition strategies

-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Goal decomposition patterns table
CREATE TABLE IF NOT EXISTS goal_decomposition_patterns (
    pattern_id SERIAL PRIMARY KEY,
    goal_text TEXT NOT NULL,
    goal_type VARCHAR(100),  -- e.g., 'data_retrieval', 'data_analysis', 'multi_step_task'
    goal_embedding vector(384),  -- Chroma uses 384-dim embeddings (all-MiniLM-L6-v2)
    subgoal_sequence JSONB NOT NULL,  -- Array of subgoals in order
    subgoal_count INTEGER NOT NULL,
    success BOOLEAN NOT NULL,
    execution_time_ms INTEGER,
    tools_used JSONB,  -- Array of tool names used
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    usage_count INTEGER DEFAULT 1,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Metadata
    complexity_score FLOAT,  -- How complex was this decomposition?
    efficiency_score FLOAT,  -- How efficient was execution?
    
    -- Indexing
    CONSTRAINT unique_goal_subgoals UNIQUE (goal_text, subgoal_sequence)
);

-- Index for fast similarity search
CREATE INDEX IF NOT EXISTS idx_goal_patterns_embedding 
ON goal_decomposition_patterns USING ivfflat (goal_embedding vector_cosine_ops)
WITH (lists = 100);

-- Index for goal type filtering
CREATE INDEX IF NOT EXISTS idx_goal_patterns_type 
ON goal_decomposition_patterns(goal_type);

-- Index for success filtering
CREATE INDEX IF NOT EXISTS idx_goal_patterns_success 
ON goal_decomposition_patterns(success);

-- Index for usage tracking
CREATE INDEX IF NOT EXISTS idx_goal_patterns_usage 
ON goal_decomposition_patterns(usage_count DESC, last_used DESC);

-- View: Successful patterns ranked by usage
CREATE OR REPLACE VIEW successful_goal_patterns AS
SELECT 
    pattern_id,
    goal_text,
    goal_type,
    subgoal_sequence,
    subgoal_count,
    usage_count,
    execution_time_ms,
    efficiency_score,
    last_used,
    created_at
FROM goal_decomposition_patterns
WHERE success = TRUE
ORDER BY usage_count DESC, efficiency_score DESC NULLS LAST;

-- View: Pattern effectiveness by goal type
CREATE OR REPLACE VIEW pattern_effectiveness_by_type AS
SELECT 
    goal_type,
    COUNT(*) as total_patterns,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_patterns,
    ROUND(AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END), 3) as success_rate,
    ROUND(AVG(subgoal_count), 1) as avg_subgoals,
    ROUND(AVG(execution_time_ms), 0) as avg_execution_ms,
    SUM(usage_count) as total_usage
FROM goal_decomposition_patterns
GROUP BY goal_type
ORDER BY total_usage DESC;

-- View: Most efficient patterns (fast + successful)
CREATE OR REPLACE VIEW most_efficient_patterns AS
SELECT 
    pattern_id,
    goal_text,
    goal_type,
    subgoal_count,
    execution_time_ms,
    efficiency_score,
    usage_count,
    tools_used
FROM goal_decomposition_patterns
WHERE success = TRUE
  AND execution_time_ms IS NOT NULL
  AND efficiency_score IS NOT NULL
ORDER BY efficiency_score DESC, execution_time_ms ASC
LIMIT 100;

-- Function: Find similar goal patterns using vector similarity
CREATE OR REPLACE FUNCTION find_similar_goal_patterns(
    query_embedding vector(384),
    similarity_threshold FLOAT DEFAULT 0.8,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    pattern_id INTEGER,
    goal_text TEXT,
    goal_type VARCHAR(100),
    subgoal_sequence JSONB,
    similarity FLOAT,
    usage_count INTEGER,
    success BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.pattern_id,
        p.goal_text,
        p.goal_type,
        p.subgoal_sequence,
        1 - (p.goal_embedding <=> query_embedding) as similarity,
        p.usage_count,
        p.success
    FROM goal_decomposition_patterns p
    WHERE 1 - (p.goal_embedding <=> query_embedding) >= similarity_threshold
    ORDER BY p.goal_embedding <=> query_embedding ASC
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Function: Update pattern usage
CREATE OR REPLACE FUNCTION update_pattern_usage(p_pattern_id INTEGER)
RETURNS VOID AS $$
BEGIN
    UPDATE goal_decomposition_patterns
    SET usage_count = usage_count + 1,
        last_used = CURRENT_TIMESTAMP
    WHERE pattern_id = p_pattern_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Calculate efficiency score
CREATE OR REPLACE FUNCTION calculate_efficiency_score(
    p_execution_time_ms INTEGER,
    p_subgoal_count INTEGER,
    p_success BOOLEAN
)
RETURNS FLOAT AS $$
DECLARE
    time_score FLOAT;
    complexity_penalty FLOAT;
    success_bonus FLOAT;
BEGIN
    -- Time score: faster is better (normalized to 0-1)
    -- Assume 10 seconds (10000ms) is baseline
    time_score := 1.0 / (1.0 + (p_execution_time_ms::FLOAT / 10000.0));
    
    -- Complexity penalty: fewer subgoals is better
    complexity_penalty := 1.0 / (1.0 + (p_subgoal_count::FLOAT / 5.0));
    
    -- Success bonus
    success_bonus := CASE WHEN p_success THEN 1.0 ELSE 0.0 END;
    
    -- Combined score
    RETURN (time_score * 0.4 + complexity_penalty * 0.3 + success_bonus * 0.3);
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE goal_decomposition_patterns IS 'Phase 10a: Stores successful goal decomposition patterns for learning and reuse';
COMMENT ON COLUMN goal_decomposition_patterns.goal_embedding IS 'Vector embedding for similarity search (384-dim from all-MiniLM-L6-v2)';
COMMENT ON COLUMN goal_decomposition_patterns.subgoal_sequence IS 'Ordered array of subgoals that led to success';
COMMENT ON COLUMN goal_decomposition_patterns.efficiency_score IS 'Combined score: fast execution + simple decomposition + success';
