-- Shadow and Replay Testing Schema
-- Phase 9d: Store results of safe testing strategies

-- Shadow test results (parallel old/new comparison)
CREATE TABLE IF NOT EXISTS shadow_test_results (
    test_id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    test_count INT NOT NULL,
    agreements INT NOT NULL,
    disagreements INT NOT NULL,
    agreement_rate FLOAT NOT NULL,
    passed BOOLEAN NOT NULL,
    differences JSONB,  -- Details of disagreements
    errors JSONB,       -- Any errors encountered
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shadow_test_tool_name ON shadow_test_results(tool_name);
CREATE INDEX IF NOT EXISTS idx_shadow_test_passed ON shadow_test_results(passed);
CREATE INDEX IF NOT EXISTS idx_shadow_test_created_at ON shadow_test_results(created_at DESC);

-- Replay test results (historical data replay)
CREATE TABLE IF NOT EXISTS replay_test_results (
    test_id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    replay_count INT NOT NULL,
    successes INT NOT NULL,
    failures INT NOT NULL,
    success_rate FLOAT NOT NULL,
    passed BOOLEAN NOT NULL,
    improvements_count INT DEFAULT 0,  -- How many outputs improved
    regressions_count INT DEFAULT 0,   -- How many outputs regressed
    errors JSONB,                      -- Details of failures
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_replay_test_tool_name ON replay_test_results(tool_name);
CREATE INDEX IF NOT EXISTS idx_replay_test_passed ON replay_test_results(passed);
CREATE INDEX IF NOT EXISTS idx_replay_test_created_at ON replay_test_results(created_at DESC);

-- Combined testing view for analytics
CREATE OR REPLACE VIEW testing_summary AS
SELECT 
    'shadow' AS test_type,
    tool_name,
    passed,
    agreement_rate AS score,
    test_count AS sample_size,
    created_at
FROM shadow_test_results
UNION ALL
SELECT 
    'replay' AS test_type,
    tool_name,
    passed,
    success_rate AS score,
    replay_count AS sample_size,
    created_at
FROM replay_test_results
ORDER BY created_at DESC;

-- View for tool testing history
CREATE OR REPLACE VIEW tool_testing_history AS
SELECT 
    tool_name,
    COUNT(*) FILTER (WHERE test_type = 'shadow') AS shadow_tests,
    COUNT(*) FILTER (WHERE test_type = 'replay') AS replay_tests,
    AVG(score) AS avg_score,
    COUNT(*) FILTER (WHERE passed) AS passed_count,
    COUNT(*) FILTER (WHERE NOT passed) AS failed_count,
    MAX(created_at) AS last_test
FROM testing_summary
GROUP BY tool_name
ORDER BY last_test DESC;

-- Comments
COMMENT ON TABLE shadow_test_results IS 
'Results from shadow testing where old and new tool versions run in parallel';

COMMENT ON TABLE replay_test_results IS 
'Results from replay testing where historical successful executions are replayed with improved tool';

COMMENT ON COLUMN shadow_test_results.agreement_rate IS 
'Percentage of test cases where old and new versions produced identical outputs';

COMMENT ON COLUMN replay_test_results.success_rate IS 
'Percentage of historical executions that succeeded when replayed with new version';

COMMENT ON COLUMN replay_test_results.improvements_count IS 
'Number of cases where new version produced better output than original';

COMMENT ON COLUMN replay_test_results.regressions_count IS 
'Number of cases where new version produced worse output or failed (critical!)';

-- Sample queries
COMMENT ON VIEW testing_summary IS $comment$
Sample queries:

-- Get all testing for a specific tool:
SELECT * FROM testing_summary 
WHERE tool_name = 'my_tool'
ORDER BY created_at DESC;

-- Find tools with consistent test passing:
SELECT tool_name, shadow_tests, replay_tests, avg_score, passed_count, failed_count
FROM tool_testing_history
WHERE passed_count > 0 AND failed_count = 0
ORDER BY avg_score DESC;

-- Find tools that failed recent tests:
SELECT tool_name, test_type, score, created_at
FROM testing_summary
WHERE NOT passed
  AND created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;

-- Compare shadow vs replay effectiveness:
SELECT 
    test_type,
    COUNT(*) AS total_tests,
    AVG(score) AS avg_score,
    COUNT(*) FILTER (WHERE passed) AS passed_tests,
    COUNT(*) FILTER (WHERE score > 0.95) AS high_confidence_tests
FROM testing_summary
GROUP BY test_type;
$comment$;

-- Verification
SELECT 'Testing schema created successfully!' AS status;
