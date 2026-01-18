-- Phase 9e: Post-Deployment Monitoring
-- Track tool performance after deployment and enable auto-rollback

-- Monitoring sessions - track each deployment being monitored
CREATE TABLE IF NOT EXISTS deployment_monitoring (
    session_id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    deployment_time TIMESTAMP NOT NULL,
    monitoring_started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    monitoring_window_hours INT NOT NULL DEFAULT 24,
    baseline_window_days INT NOT NULL DEFAULT 7,
    regression_threshold FLOAT NOT NULL DEFAULT 0.15,
    status VARCHAR(50) NOT NULL DEFAULT 'active',  -- active, completed, rolled_back
    completed_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Health checks - periodic checks during monitoring
CREATE TABLE IF NOT EXISTS deployment_health_checks (
    check_id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    session_id INT REFERENCES deployment_monitoring(session_id),
    checked_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Baseline metrics (before deployment)
    baseline_success_rate FLOAT,
    baseline_total_executions INT,
    baseline_avg_duration_ms FLOAT,
    
    -- Current metrics (after deployment)
    current_success_rate FLOAT,
    current_total_executions INT,
    current_avg_duration_ms FLOAT,
    
    -- Comparison
    success_rate_drop FLOAT,  -- Positive value = drop
    duration_change_percent FLOAT,  -- Positive = slower
    regression_detected BOOLEAN NOT NULL DEFAULT FALSE,
    regression_severity VARCHAR(20),  -- none, medium, high, critical
    needs_rollback BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Additional context
    has_sufficient_data BOOLEAN NOT NULL DEFAULT TRUE,
    warnings TEXT[]
);

-- Rollback events - when auto-rollback is triggered
CREATE TABLE IF NOT EXISTS deployment_rollbacks (
    rollback_id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    session_id INT REFERENCES deployment_monitoring(session_id),
    rollback_time TIMESTAMP NOT NULL DEFAULT NOW(),
    reason TEXT NOT NULL,
    
    -- Metrics at rollback time
    success_rate_drop FLOAT,
    regression_severity VARCHAR(20),
    
    -- Rollback details
    rollback_successful BOOLEAN NOT NULL,
    previous_version_restored TEXT,
    error_message TEXT,
    
    -- Post-rollback validation
    verified_at TIMESTAMP,
    verification_success BOOLEAN
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_deployment_monitoring_tool ON deployment_monitoring(tool_name);
CREATE INDEX IF NOT EXISTS idx_deployment_monitoring_status ON deployment_monitoring(status);
CREATE INDEX IF NOT EXISTS idx_deployment_monitoring_time ON deployment_monitoring(deployment_time);

CREATE INDEX IF NOT EXISTS idx_health_checks_tool ON deployment_health_checks(tool_name);
CREATE INDEX IF NOT EXISTS idx_health_checks_session ON deployment_health_checks(session_id);
CREATE INDEX IF NOT EXISTS idx_health_checks_regression ON deployment_health_checks(regression_detected);

CREATE INDEX IF NOT EXISTS idx_rollbacks_tool ON deployment_rollbacks(tool_name);
CREATE INDEX IF NOT EXISTS idx_rollbacks_time ON deployment_rollbacks(rollback_time);

-- View: Active monitoring sessions
CREATE OR REPLACE VIEW active_monitoring AS
SELECT 
    dm.session_id,
    dm.tool_name,
    dm.deployment_time,
    dm.monitoring_started_at,
    EXTRACT(EPOCH FROM (NOW() - dm.monitoring_started_at)) / 3600 AS hours_elapsed,
    dm.monitoring_window_hours,
    dm.regression_threshold,
    
    -- Latest health check
    (SELECT checked_at FROM deployment_health_checks 
     WHERE session_id = dm.session_id 
     ORDER BY checked_at DESC LIMIT 1) AS last_check,
    
    (SELECT regression_detected FROM deployment_health_checks 
     WHERE session_id = dm.session_id 
     ORDER BY checked_at DESC LIMIT 1) AS regression_detected,
    
    (SELECT success_rate_drop FROM deployment_health_checks 
     WHERE session_id = dm.session_id 
     ORDER BY checked_at DESC LIMIT 1) AS latest_success_rate_drop,
    
    -- Check count
    (SELECT COUNT(*) FROM deployment_health_checks 
     WHERE session_id = dm.session_id) AS check_count,
    
    -- Rollback status
    EXISTS(SELECT 1 FROM deployment_rollbacks 
           WHERE session_id = dm.session_id 
           AND rollback_successful = TRUE) AS was_rolled_back

FROM deployment_monitoring dm
WHERE dm.status = 'active'
ORDER BY dm.monitoring_started_at DESC;

-- View: Tool health history
CREATE OR REPLACE VIEW tool_health_history AS
SELECT 
    tool_name,
    checked_at,
    baseline_success_rate,
    current_success_rate,
    success_rate_drop,
    regression_detected,
    regression_severity,
    needs_rollback,
    has_sufficient_data,
    
    -- Calculate trend
    LAG(current_success_rate) OVER (
        PARTITION BY tool_name 
        ORDER BY checked_at
    ) AS previous_success_rate,
    
    current_success_rate - LAG(current_success_rate) OVER (
        PARTITION BY tool_name 
        ORDER BY checked_at
    ) AS success_rate_trend

FROM deployment_health_checks
ORDER BY tool_name, checked_at DESC;

-- View: Rollback summary
CREATE OR REPLACE VIEW rollback_summary AS
SELECT 
    tool_name,
    COUNT(*) AS total_rollbacks,
    COUNT(*) FILTER (WHERE rollback_successful = TRUE) AS successful_rollbacks,
    AVG(success_rate_drop) AS avg_success_rate_drop,
    MAX(success_rate_drop) AS max_success_rate_drop,
    MIN(rollback_time) AS first_rollback,
    MAX(rollback_time) AS latest_rollback,
    
    -- Verification stats
    COUNT(*) FILTER (WHERE verified_at IS NOT NULL) AS verified_count,
    COUNT(*) FILTER (WHERE verification_success = TRUE) AS verified_successful

FROM deployment_rollbacks
GROUP BY tool_name
ORDER BY total_rollbacks DESC;

-- View: Deployment stability score
CREATE OR REPLACE VIEW deployment_stability AS
SELECT 
    dm.tool_name,
    COUNT(DISTINCT dm.session_id) AS total_deployments,
    
    -- Rollback rate
    COUNT(DISTINCT dr.rollback_id)::FLOAT / 
        NULLIF(COUNT(DISTINCT dm.session_id), 0) AS rollback_rate,
    
    -- Average time to rollback (when it happens)
    AVG(EXTRACT(EPOCH FROM (dr.rollback_time - dm.deployment_time)) / 3600) 
        FILTER (WHERE dr.rollback_id IS NOT NULL) AS avg_hours_to_rollback,
    
    -- Health check stats
    AVG(dhc.current_success_rate) AS avg_post_deployment_success_rate,
    AVG(dhc.success_rate_drop) AS avg_success_rate_drop,
    
    -- Regression frequency
    COUNT(*) FILTER (WHERE dhc.regression_detected = TRUE)::FLOAT / 
        NULLIF(COUNT(dhc.check_id), 0) AS regression_frequency,
    
    -- Latest deployment
    MAX(dm.deployment_time) AS latest_deployment,
    MAX(dm.status) AS latest_status

FROM deployment_monitoring dm
LEFT JOIN deployment_health_checks dhc ON dm.session_id = dhc.session_id
LEFT JOIN deployment_rollbacks dr ON dm.session_id = dr.session_id
GROUP BY dm.tool_name
ORDER BY rollback_rate DESC, total_deployments DESC;

-- Sample queries

-- 1. Find tools with active regressions
-- SELECT * FROM active_monitoring WHERE regression_detected = TRUE;

-- 2. Get health trend for a specific tool
-- SELECT * FROM tool_health_history WHERE tool_name = 'some_tool' LIMIT 10;

-- 3. Find tools that frequently get rolled back
-- SELECT * FROM rollback_summary WHERE rollback_rate > 0.2;  -- 20%+

-- 4. Check deployment stability across all tools
-- SELECT * FROM deployment_stability ORDER BY avg_post_deployment_success_rate ASC;

-- 5. Recent rollbacks with details
-- SELECT 
--     tool_name,
--     rollback_time,
--     reason,
--     success_rate_drop,
--     regression_severity,
--     rollback_successful
-- FROM deployment_rollbacks
-- WHERE rollback_time > NOW() - INTERVAL '7 days'
-- ORDER BY rollback_time DESC;

-- 6. Monitoring sessions needing attention
-- SELECT 
--     session_id,
--     tool_name,
--     hours_elapsed,
--     monitoring_window_hours,
--     check_count,
--     regression_detected,
--     latest_success_rate_drop
-- FROM active_monitoring
-- WHERE regression_detected = TRUE
--    OR (hours_elapsed > monitoring_window_hours AND check_count < 5)
-- ORDER BY latest_success_rate_drop DESC;
