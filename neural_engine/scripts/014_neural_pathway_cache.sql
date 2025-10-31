-- Neural Pathway Cache Schema
-- Caches successful execution traces for fast System 1 lookup
-- Includes tool dependency tracking for automatic invalidation

-- Main pathway cache table
CREATE TABLE IF NOT EXISTS neural_pathways (
    pathway_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_text TEXT NOT NULL,
    goal_embedding vector(384), -- Chroma embedding for similarity search
    goal_type VARCHAR(100), -- e.g., 'data_retrieval', 'data_analysis', 'action'
    
    -- Execution trace
    execution_steps JSONB NOT NULL, -- [{step_num, action, tool, params, result}, ...]
    tool_names TEXT[] NOT NULL, -- Array of tool names used (for dependency tracking)
    final_result JSONB NOT NULL,
    
    -- Context and metadata
    context_hash VARCHAR(64), -- Hash of relevant context (user prefs, constraints)
    complexity_score FLOAT, -- 0.0-1.0 measure of pathway complexity
    execution_time_ms INTEGER,
    
    -- Success tracking
    success_count INTEGER DEFAULT 1,
    failure_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Validation state
    is_valid BOOLEAN DEFAULT TRUE,
    invalidation_reason TEXT,
    invalidated_at TIMESTAMP,
    
    -- Indexes
    CONSTRAINT positive_success_count CHECK (success_count >= 0),
    CONSTRAINT positive_failure_count CHECK (failure_count >= 0)
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_neural_pathways_embedding 
    ON neural_pathways USING ivfflat (goal_embedding vector_cosine_ops)
    WHERE is_valid = TRUE;

CREATE INDEX IF NOT EXISTS idx_neural_pathways_goal_type 
    ON neural_pathways(goal_type) 
    WHERE is_valid = TRUE;

CREATE INDEX IF NOT EXISTS idx_neural_pathways_tool_names 
    ON neural_pathways USING GIN(tool_names)
    WHERE is_valid = TRUE;

CREATE INDEX IF NOT EXISTS idx_neural_pathways_last_used 
    ON neural_pathways(last_used_at DESC)
    WHERE is_valid = TRUE;

CREATE INDEX IF NOT EXISTS idx_neural_pathways_success_rate 
    ON neural_pathways((success_count::float / NULLIF(success_count + failure_count, 0)) DESC)
    WHERE is_valid = TRUE;

-- Tool dependency tracking for automatic invalidation
CREATE TABLE IF NOT EXISTS pathway_tool_dependencies (
    dependency_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pathway_id UUID NOT NULL REFERENCES neural_pathways(pathway_id) ON DELETE CASCADE,
    tool_name VARCHAR(200) NOT NULL,
    tool_version VARCHAR(50),
    is_critical BOOLEAN DEFAULT TRUE, -- If false, pathway may work with fallback
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(pathway_id, tool_name)
);

CREATE INDEX IF NOT EXISTS idx_pathway_tool_deps_tool_name 
    ON pathway_tool_dependencies(tool_name);

-- View: High-confidence pathways (for fast System 1 execution)
CREATE OR REPLACE VIEW high_confidence_pathways AS
SELECT 
    p.pathway_id,
    p.goal_text,
    p.goal_type,
    p.tool_names,
    p.execution_steps,
    p.final_result,
    p.execution_time_ms,
    p.success_count,
    p.failure_count,
    (p.success_count::float / NULLIF(p.success_count + p.failure_count, 0)) as success_rate,
    p.last_used_at
FROM neural_pathways p
WHERE 
    p.is_valid = TRUE
    AND p.success_count >= 3
    AND (p.success_count::float / NULLIF(p.success_count + p.failure_count, 0)) >= 0.85
ORDER BY 
    (p.success_count::float / NULLIF(p.success_count + p.failure_count, 0)) DESC,
    p.success_count DESC,
    p.last_used_at DESC;

-- View: Pathway effectiveness by goal type
CREATE OR REPLACE VIEW pathway_effectiveness_by_type AS
SELECT 
    goal_type,
    COUNT(*) as pathway_count,
    AVG(success_count::float / NULLIF(success_count + failure_count, 0)) as avg_success_rate,
    AVG(execution_time_ms) as avg_execution_time_ms,
    SUM(success_count) as total_successes,
    SUM(failure_count) as total_failures
FROM neural_pathways
WHERE is_valid = TRUE
GROUP BY goal_type
ORDER BY avg_success_rate DESC, total_successes DESC;

-- View: Recently invalidated pathways (for debugging)
CREATE OR REPLACE VIEW recently_invalidated_pathways AS
SELECT 
    pathway_id,
    goal_text,
    goal_type,
    tool_names,
    invalidation_reason,
    invalidated_at,
    success_count,
    failure_count,
    (success_count::float / NULLIF(success_count + failure_count, 0)) as previous_success_rate
FROM neural_pathways
WHERE is_valid = FALSE
ORDER BY invalidated_at DESC
LIMIT 100;

-- Function: Find similar cached pathways
CREATE OR REPLACE FUNCTION find_similar_pathways(
    p_goal_embedding vector(384),
    p_goal_type VARCHAR(100) DEFAULT NULL,
    p_similarity_threshold FLOAT DEFAULT 0.85,
    p_min_success_count INTEGER DEFAULT 2,
    p_limit INTEGER DEFAULT 5
)
RETURNS TABLE (
    pathway_id UUID,
    goal_text TEXT,
    execution_steps JSONB,
    tool_names TEXT[],
    final_result JSONB,
    similarity_score FLOAT,
    success_rate FLOAT,
    execution_time_ms INTEGER,
    usage_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.pathway_id,
        p.goal_text,
        p.execution_steps,
        p.tool_names,
        p.final_result,
        1 - (p.goal_embedding <=> p_goal_embedding) as similarity_score,
        (p.success_count::float / NULLIF(p.success_count + p.failure_count, 0)) as success_rate,
        p.execution_time_ms,
        (p.success_count + p.failure_count) as usage_count
    FROM neural_pathways p
    WHERE 
        p.is_valid = TRUE
        AND (p_goal_type IS NULL OR p.goal_type = p_goal_type)
        AND p.success_count >= p_min_success_count
        AND (1 - (p.goal_embedding <=> p_goal_embedding)) >= p_similarity_threshold
    ORDER BY 
        (1 - (p.goal_embedding <=> p_goal_embedding)) DESC,
        (p.success_count::float / NULLIF(p.success_count + p.failure_count, 0)) DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function: Invalidate pathways using a specific tool
CREATE OR REPLACE FUNCTION invalidate_pathways_for_tool(
    p_tool_name VARCHAR(200),
    p_reason TEXT DEFAULT 'Tool removed or unavailable'
)
RETURNS INTEGER AS $$
DECLARE
    v_affected_count INTEGER;
BEGIN
    -- Invalidate all pathways that depend on this tool
    UPDATE neural_pathways
    SET 
        is_valid = FALSE,
        invalidation_reason = p_reason,
        invalidated_at = CURRENT_TIMESTAMP
    WHERE 
        is_valid = TRUE
        AND p_tool_name = ANY(tool_names);
    
    GET DIAGNOSTICS v_affected_count = ROW_COUNT;
    
    RETURN v_affected_count;
END;
$$ LANGUAGE plpgsql;

-- Function: Update pathway usage (increment success or failure)
CREATE OR REPLACE FUNCTION update_pathway_usage(
    p_pathway_id UUID,
    p_success BOOLEAN,
    p_execution_time_ms INTEGER DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_updated BOOLEAN;
BEGIN
    IF p_success THEN
        UPDATE neural_pathways
        SET 
            success_count = success_count + 1,
            last_used_at = CURRENT_TIMESTAMP,
            execution_time_ms = COALESCE(p_execution_time_ms, execution_time_ms)
        WHERE pathway_id = p_pathway_id AND is_valid = TRUE;
    ELSE
        UPDATE neural_pathways
        SET 
            failure_count = failure_count + 1,
            last_used_at = CURRENT_TIMESTAMP
        WHERE pathway_id = p_pathway_id AND is_valid = TRUE;
        
        -- Auto-invalidate if failure rate too high (>30% with at least 5 uses)
        UPDATE neural_pathways
        SET 
            is_valid = FALSE,
            invalidation_reason = 'High failure rate detected',
            invalidated_at = CURRENT_TIMESTAMP
        WHERE 
            pathway_id = p_pathway_id 
            AND is_valid = TRUE
            AND (success_count + failure_count) >= 5
            AND (failure_count::float / NULLIF(success_count + failure_count, 0)) > 0.30;
    END IF;
    
    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN (v_updated > 0);
END;
$$ LANGUAGE plpgsql;

-- Function: Calculate pathway confidence score
CREATE OR REPLACE FUNCTION calculate_pathway_confidence(
    p_pathway_id UUID
)
RETURNS FLOAT AS $$
DECLARE
    v_confidence FLOAT;
BEGIN
    SELECT 
        CASE 
            WHEN (success_count + failure_count) = 0 THEN 0.0
            ELSE 
                -- Combine success rate with usage count (more uses = more confidence)
                (success_count::float / (success_count + failure_count)) * 
                LEAST(1.0, (success_count + failure_count) / 10.0) * -- Cap at 10 uses
                CASE 
                    WHEN EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_used_at)) / 86400 > 30 
                    THEN 0.8 -- Decay confidence for old pathways
                    ELSE 1.0
                END
        END
    INTO v_confidence
    FROM neural_pathways
    WHERE pathway_id = p_pathway_id;
    
    RETURN COALESCE(v_confidence, 0.0);
END;
$$ LANGUAGE plpgsql;

-- Function: Clean up old invalidated pathways
CREATE OR REPLACE FUNCTION cleanup_old_invalidated_pathways(
    p_days_old INTEGER DEFAULT 90
)
RETURNS INTEGER AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    DELETE FROM neural_pathways
    WHERE 
        is_valid = FALSE
        AND invalidated_at < (CURRENT_TIMESTAMP - (p_days_old || ' days')::INTERVAL);
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Track tool dependencies when pathway is created
CREATE OR REPLACE FUNCTION track_pathway_tool_dependencies()
RETURNS TRIGGER AS $$
BEGIN
    -- Insert dependency records for each tool
    INSERT INTO pathway_tool_dependencies (pathway_id, tool_name, is_critical)
    SELECT NEW.pathway_id, unnest(NEW.tool_names), TRUE
    ON CONFLICT (pathway_id, tool_name) DO NOTHING;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_track_pathway_tool_dependencies
    AFTER INSERT ON neural_pathways
    FOR EACH ROW
    EXECUTE FUNCTION track_pathway_tool_dependencies();

-- Comments
COMMENT ON TABLE neural_pathways IS 'Caches successful execution traces for fast System 1 lookup. Automatically invalidated when dependent tools are removed.';
COMMENT ON TABLE pathway_tool_dependencies IS 'Tracks which tools each pathway depends on for automatic invalidation when tools are removed.';
COMMENT ON FUNCTION find_similar_pathways IS 'Finds cached pathways similar to a given goal embedding. Returns high-confidence paths for direct execution.';
COMMENT ON FUNCTION invalidate_pathways_for_tool IS 'Invalidates all pathways that depend on a specific tool. Called when tool is removed or becomes unavailable.';
COMMENT ON FUNCTION update_pathway_usage IS 'Updates pathway success/failure counts. Auto-invalidates pathways with high failure rates.';
COMMENT ON FUNCTION calculate_pathway_confidence IS 'Calculates confidence score (0.0-1.0) based on success rate, usage count, and recency.';
