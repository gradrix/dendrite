-- Add goal_decomposition_patterns table for Phase 2.2
-- This table stores learned decomposition patterns for similar goals

CREATE TABLE IF NOT EXISTS goal_decomposition_patterns (
    id SERIAL PRIMARY KEY,
    goal_text TEXT NOT NULL,
    goal_type VARCHAR(100),
    subgoals JSONB NOT NULL,  -- Array of subgoal descriptions
    success BOOLEAN NOT NULL,
    execution_time_ms INTEGER,
    tools_used JSONB,  -- Array of tool names used
    usage_count INTEGER DEFAULT 1,
    efficiency_score FLOAT,  -- success_rate * (1 / normalized_time)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_goal_decomp_goal_type ON goal_decomposition_patterns(goal_type);
CREATE INDEX IF NOT EXISTS idx_goal_decomp_success ON goal_decomposition_patterns(success);
CREATE INDEX IF NOT EXISTS idx_goal_decomp_efficiency ON goal_decomposition_patterns(efficiency_score DESC);
CREATE INDEX IF NOT EXISTS idx_goal_decomp_created_at ON goal_decomposition_patterns(created_at DESC);

-- Grant permissions
GRANT ALL PRIVILEGES ON goal_decomposition_patterns TO dendrite;
GRANT ALL PRIVILEGES ON SEQUENCE goal_decomposition_patterns_id_seq TO dendrite;

-- Log addition
DO $$
BEGIN
    RAISE NOTICE 'Goal decomposition patterns table added successfully!';
    RAISE NOTICE 'Phase 2.2: Goal Decomposition Learner integration complete';
END $$;
