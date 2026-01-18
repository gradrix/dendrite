-- Phase 9f: Tool Version Management
-- Track all versions of every tool with complete history

-- Tool versions - complete version history for every tool
CREATE TABLE IF NOT EXISTS tool_versions (
    version_id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    version_number INT NOT NULL,
    
    -- Version content
    code TEXT NOT NULL,
    code_hash VARCHAR(64),  -- SHA-256 hash for deduplication
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50) NOT NULL DEFAULT 'human',  -- 'human' or 'autonomous'
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Performance metrics (updated over time)
    success_rate FLOAT,
    total_executions INT DEFAULT 0,
    successful_executions INT DEFAULT 0,
    failed_executions INT DEFAULT 0,
    avg_duration_ms FLOAT,
    
    -- Deployment tracking
    deployment_count INT DEFAULT 0,
    first_deployed_at TIMESTAMP,
    last_deployed_at TIMESTAMP,
    total_deployment_duration_hours FLOAT DEFAULT 0,  -- How long this version was active
    
    -- Improvement context
    improvement_reason TEXT,
    improvement_type VARCHAR(50),  -- 'initial', 'bugfix', 'enhancement', 'rollback'
    previous_version_id INT REFERENCES tool_versions(version_id),
    
    -- Rollback tracking
    was_rolled_back BOOLEAN DEFAULT FALSE,
    rolled_back_at TIMESTAMP,
    rollback_reason TEXT,
    replaced_by_version_id INT REFERENCES tool_versions(version_id),
    
    UNIQUE(tool_name, version_number)
);

-- Version deployments - track each time a version was deployed
CREATE TABLE IF NOT EXISTS version_deployments (
    deployment_id SERIAL PRIMARY KEY,
    version_id INT NOT NULL REFERENCES tool_versions(version_id),
    tool_name VARCHAR(255) NOT NULL,
    
    -- Deployment info
    deployed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deployed_by VARCHAR(50) NOT NULL DEFAULT 'autonomous',  -- 'human' or 'autonomous'
    deployment_type VARCHAR(50) NOT NULL,  -- 'new', 'improvement', 'rollback', 'restore'
    
    -- Reason
    reason TEXT,
    
    -- Outcome
    undeployed_at TIMESTAMP,
    was_successful BOOLEAN,
    final_success_rate FLOAT,
    total_executions_during_deployment INT DEFAULT 0,
    
    -- Related entities
    monitoring_session_id INT,  -- Reference to deployment_monitoring
    improvement_attempt_id INT  -- Reference to improvement_attempts
);

-- Version diffs - store computed diffs between versions
CREATE TABLE IF NOT EXISTS version_diffs (
    diff_id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    from_version_id INT NOT NULL REFERENCES tool_versions(version_id),
    to_version_id INT NOT NULL REFERENCES tool_versions(version_id),
    
    -- Diff content
    unified_diff TEXT NOT NULL,
    lines_added INT,
    lines_removed INT,
    lines_changed INT,
    
    -- Semantic analysis
    breaking_changes BOOLEAN DEFAULT FALSE,
    breaking_change_details TEXT[],
    
    computed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    UNIQUE(from_version_id, to_version_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tool_versions_name ON tool_versions(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_versions_current ON tool_versions(tool_name, is_current);
CREATE INDEX IF NOT EXISTS idx_tool_versions_created ON tool_versions(created_at);
CREATE INDEX IF NOT EXISTS idx_tool_versions_hash ON tool_versions(code_hash);

CREATE INDEX IF NOT EXISTS idx_version_deployments_version ON version_deployments(version_id);
CREATE INDEX IF NOT EXISTS idx_version_deployments_tool ON version_deployments(tool_name);
CREATE INDEX IF NOT EXISTS idx_version_deployments_time ON version_deployments(deployed_at);

CREATE INDEX IF NOT EXISTS idx_version_diffs_tool ON version_diffs(tool_name);
CREATE INDEX IF NOT EXISTS idx_version_diffs_versions ON version_diffs(from_version_id, to_version_id);

-- View: Current versions of all tools
CREATE OR REPLACE VIEW current_tool_versions AS
SELECT 
    tv.tool_name,
    tv.version_id,
    tv.version_number,
    tv.created_at,
    tv.created_by,
    tv.success_rate,
    tv.total_executions,
    tv.deployment_count,
    tv.improvement_reason,
    tv.was_rolled_back,
    
    -- Latest deployment info
    (SELECT deployed_at FROM version_deployments 
     WHERE version_id = tv.version_id 
     ORDER BY deployed_at DESC LIMIT 1) AS last_deployed_at,
    
    -- Previous version info
    pv.version_number AS previous_version_number,
    pv.success_rate AS previous_success_rate
    
FROM tool_versions tv
LEFT JOIN tool_versions pv ON tv.previous_version_id = pv.version_id
WHERE tv.is_current = TRUE
ORDER BY tv.tool_name;

-- View: Version history for each tool
CREATE OR REPLACE VIEW tool_version_history AS
SELECT 
    tv.tool_name,
    tv.version_id,
    tv.version_number,
    tv.created_at,
    tv.created_by,
    tv.is_current,
    tv.success_rate,
    tv.total_executions,
    tv.deployment_count,
    tv.improvement_type,
    tv.improvement_reason,
    tv.was_rolled_back,
    tv.rollback_reason,
    
    -- Time as current version
    CASE 
        WHEN tv.is_current THEN 
            EXTRACT(EPOCH FROM (NOW() - tv.last_deployed_at)) / 3600
        ELSE 
            tv.total_deployment_duration_hours
    END AS hours_deployed,
    
    -- Comparison to previous
    tv.success_rate - LAG(tv.success_rate) OVER (
        PARTITION BY tv.tool_name 
        ORDER BY tv.version_number
    ) AS success_rate_change,
    
    -- Stability indicator
    CASE 
        WHEN tv.was_rolled_back THEN 'unstable'
        WHEN tv.success_rate >= 0.9 THEN 'stable'
        WHEN tv.success_rate >= 0.7 THEN 'acceptable'
        ELSE 'problematic'
    END AS stability

FROM tool_versions tv
ORDER BY tv.tool_name, tv.version_number DESC;

-- View: Deployment history
CREATE OR REPLACE VIEW deployment_history AS
SELECT 
    vd.deployment_id,
    vd.tool_name,
    tv.version_number,
    vd.deployed_at,
    vd.deployed_by,
    vd.deployment_type,
    vd.reason,
    vd.was_successful,
    vd.final_success_rate,
    vd.total_executions_during_deployment,
    
    -- Duration
    CASE 
        WHEN vd.undeployed_at IS NOT NULL THEN
            EXTRACT(EPOCH FROM (vd.undeployed_at - vd.deployed_at)) / 3600
        ELSE
            EXTRACT(EPOCH FROM (NOW() - vd.deployed_at)) / 3600
    END AS hours_deployed,
    
    -- Status
    CASE 
        WHEN vd.undeployed_at IS NULL THEN 'active'
        WHEN vd.was_successful = TRUE THEN 'successful'
        WHEN vd.was_successful = FALSE THEN 'rolled_back'
        ELSE 'completed'
    END AS status

FROM version_deployments vd
JOIN tool_versions tv ON vd.version_id = tv.version_id
ORDER BY vd.deployed_at DESC;

-- View: Tool stability summary
CREATE OR REPLACE VIEW tool_stability_summary AS
SELECT 
    tool_name,
    COUNT(DISTINCT version_id) AS total_versions,
    MAX(version_number) AS current_version_number,
    
    -- Success rates
    AVG(success_rate) FILTER (WHERE success_rate IS NOT NULL) AS avg_success_rate,
    MAX(success_rate) AS best_success_rate,
    MIN(success_rate) AS worst_success_rate,
    
    -- Rollback stats
    COUNT(*) FILTER (WHERE was_rolled_back = TRUE) AS rollback_count,
    COUNT(*) FILTER (WHERE was_rolled_back = TRUE)::FLOAT / 
        NULLIF(COUNT(*), 0) AS rollback_rate,
    
    -- Deployment stats
    SUM(deployment_count) AS total_deployments,
    AVG(deployment_count) AS avg_deployments_per_version,
    
    -- Latest info
    MAX(created_at) AS latest_version_created_at,
    (SELECT created_by FROM tool_versions 
     WHERE tool_name = tv.tool_name AND is_current = TRUE) AS current_version_created_by

FROM tool_versions tv
GROUP BY tool_name
ORDER BY rollback_rate DESC, tool_name;

-- View: Recent version changes
CREATE OR REPLACE VIEW recent_version_changes AS
SELECT 
    tv.tool_name,
    tv.version_number,
    tv.created_at,
    tv.created_by,
    tv.improvement_type,
    tv.improvement_reason,
    
    -- Compare to previous
    pv.version_number AS previous_version,
    tv.success_rate - pv.success_rate AS success_rate_delta,
    
    -- Diff info
    vd.lines_added,
    vd.lines_removed,
    vd.breaking_changes,
    
    -- Current status
    tv.is_current,
    tv.was_rolled_back

FROM tool_versions tv
LEFT JOIN tool_versions pv ON tv.previous_version_id = pv.version_id
LEFT JOIN version_diffs vd ON vd.from_version_id = pv.version_id 
    AND vd.to_version_id = tv.version_id
WHERE tv.created_at > NOW() - INTERVAL '30 days'
ORDER BY tv.created_at DESC;

-- Function: Get version at specific time
CREATE OR REPLACE FUNCTION get_version_at_time(
    p_tool_name VARCHAR,
    p_timestamp TIMESTAMP
) RETURNS TABLE(
    version_id INT,
    version_number INT,
    code TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        vd.version_id,
        tv.version_number,
        tv.code
    FROM version_deployments vd
    JOIN tool_versions tv ON vd.version_id = tv.version_id
    WHERE vd.tool_name = p_tool_name
      AND vd.deployed_at <= p_timestamp
      AND (vd.undeployed_at IS NULL OR vd.undeployed_at > p_timestamp)
    ORDER BY vd.deployed_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function: Mark version as current
CREATE OR REPLACE FUNCTION set_current_version(
    p_version_id INT
) RETURNS VOID AS $$
DECLARE
    v_tool_name VARCHAR;
BEGIN
    -- Get tool name
    SELECT tool_name INTO v_tool_name
    FROM tool_versions
    WHERE version_id = p_version_id;
    
    -- Unset all other versions for this tool
    UPDATE tool_versions
    SET is_current = FALSE
    WHERE tool_name = v_tool_name;
    
    -- Set this version as current
    UPDATE tool_versions
    SET is_current = TRUE
    WHERE version_id = p_version_id;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Update deployment duration when version changes
CREATE OR REPLACE FUNCTION update_deployment_duration() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.is_current = TRUE AND NEW.is_current = FALSE THEN
        -- Version is no longer current, update duration
        UPDATE tool_versions
        SET total_deployment_duration_hours = 
            total_deployment_duration_hours + 
            EXTRACT(EPOCH FROM (NOW() - last_deployed_at)) / 3600
        WHERE version_id = OLD.version_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_deployment_duration
    BEFORE UPDATE ON tool_versions
    FOR EACH ROW
    WHEN (OLD.is_current IS DISTINCT FROM NEW.is_current)
    EXECUTE FUNCTION update_deployment_duration();

-- Sample queries documentation

-- 1. Get complete version history for a tool
-- SELECT * FROM tool_version_history WHERE tool_name = 'my_tool';

-- 2. Find tools with high rollback rates
-- SELECT * FROM tool_stability_summary WHERE rollback_rate > 0.2 ORDER BY rollback_rate DESC;

-- 3. Get current version of all tools
-- SELECT * FROM current_tool_versions;

-- 4. Find recent improvements
-- SELECT * FROM recent_version_changes WHERE improvement_type = 'enhancement';

-- 5. Compare two versions
-- SELECT * FROM version_diffs WHERE tool_name = 'my_tool' AND from_version_id = 1 AND to_version_id = 2;

-- 6. Get deployment history for a tool
-- SELECT * FROM deployment_history WHERE tool_name = 'my_tool' ORDER BY deployed_at DESC;

-- 7. Find which version was active at a specific time
-- SELECT * FROM get_version_at_time('my_tool', '2025-10-15 14:30:00');

-- 8. Tools that need attention (high rollback rate or low success rate)
-- SELECT tool_name, rollback_rate, avg_success_rate 
-- FROM tool_stability_summary 
-- WHERE rollback_rate > 0.3 OR avg_success_rate < 0.7
-- ORDER BY rollback_rate DESC;
