-- Tool Lifecycle Management Schema Migration
-- Phase 9d: Add status tracking and lifecycle events

-- Add status columns to tool_creation_events
ALTER TABLE tool_creation_events 
ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active'
  CHECK (status IN ('active', 'deleted', 'archived', 'deprecated'));

ALTER TABLE tool_creation_events
ADD COLUMN IF NOT EXISTS status_changed_at TIMESTAMP DEFAULT NOW();

ALTER TABLE tool_creation_events
ADD COLUMN IF NOT EXISTS status_reason TEXT;

-- Create tool lifecycle events table for audit trail
CREATE TABLE IF NOT EXISTS tool_lifecycle_events (
    event_id SERIAL PRIMARY KEY,
    tool_name VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- created | deleted | restored | archived
    event_time TIMESTAMP DEFAULT NOW(),
    reason TEXT,
    metadata JSONB,  -- {success_rate: 0.95, total_uses: 100, ...}
    triggered_by VARCHAR(50)  -- 'user' | 'ai' | 'auto_cleanup' | 'system'
);

-- Create indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_tool_lifecycle_tool_name 
ON tool_lifecycle_events(tool_name);

CREATE INDEX IF NOT EXISTS idx_tool_lifecycle_event_type 
ON tool_lifecycle_events(event_type);

CREATE INDEX IF NOT EXISTS idx_tool_lifecycle_event_time 
ON tool_lifecycle_events(event_time DESC);

CREATE INDEX IF NOT EXISTS idx_tool_creation_status 
ON tool_creation_events(status);

-- Add comments for documentation
COMMENT ON TABLE tool_lifecycle_events IS 
'Audit trail for tool lifecycle events - creation, deletion, restoration, archival';

COMMENT ON COLUMN tool_creation_events.status IS 
'Current tool status: active (in use), deleted (file removed), archived (old and unused), deprecated (replaced)';

COMMENT ON COLUMN tool_creation_events.status_changed_at IS 
'Timestamp when status last changed - used for auto-cleanup policies';

COMMENT ON COLUMN tool_creation_events.status_reason IS 
'Human-readable reason for status change - e.g., "file_not_found", "auto_cleanup: 90 days old"';

-- Initialize status for existing tools (set all NULL to 'active')
UPDATE tool_creation_events 
SET status = 'active', status_changed_at = created_at 
WHERE status IS NULL;

-- View for active tools only (most common query)
CREATE OR REPLACE VIEW active_tools AS
SELECT tool_name, tool_class, created_at, status_changed_at
FROM tool_creation_events
WHERE status = 'active'
ORDER BY created_at DESC;

-- View for tool lifecycle summary
CREATE OR REPLACE VIEW tool_lifecycle_summary AS
SELECT 
    tce.tool_name,
    tce.status,
    tce.created_at,
    tce.status_changed_at,
    ts.total_executions,
    ts.success_rate,
    ts.last_used,
    (NOW() - ts.last_used) AS days_since_use,
    (NOW() - tce.status_changed_at) AS days_in_status
FROM tool_creation_events tce
LEFT JOIN tool_statistics ts ON tce.tool_name = ts.tool_name
ORDER BY tce.created_at DESC;

COMMENT ON VIEW tool_lifecycle_summary IS 
'Combined view of tool status and usage statistics for lifecycle management decisions';

-- Function to automatically log status changes
CREATE OR REPLACE FUNCTION log_tool_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Only log if status actually changed
    IF (TG_OP = 'UPDATE' AND OLD.status IS DISTINCT FROM NEW.status) THEN
        INSERT INTO tool_lifecycle_events (
            tool_name,
            event_type,
            reason,
            metadata,
            triggered_by
        ) VALUES (
            NEW.tool_name,
            NEW.status,
            NEW.status_reason,
            jsonb_build_object(
                'old_status', OLD.status,
                'new_status', NEW.status,
                'changed_at', NEW.status_changed_at
            ),
            'system'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically log status changes
DROP TRIGGER IF EXISTS tool_status_change_trigger ON tool_creation_events;
CREATE TRIGGER tool_status_change_trigger
    AFTER UPDATE ON tool_creation_events
    FOR EACH ROW
    EXECUTE FUNCTION log_tool_status_change();

-- Query to find tools needing cleanup (for maintenance)
COMMENT ON TABLE tool_lifecycle_events IS $comment$
Sample queries:

-- Find deleted tools older than 90 days with low usage:
SELECT tce.tool_name, tce.status_changed_at, ts.total_executions
FROM tool_creation_events tce
LEFT JOIN tool_statistics ts ON tce.tool_name = ts.tool_name
WHERE tce.status = 'deleted'
  AND tce.status_changed_at < NOW() - INTERVAL '90 days'
  AND COALESCE(ts.total_executions, 0) < 10;

-- Find useful tools that were recently deleted (potential accidents):
SELECT tce.tool_name, ts.success_rate, ts.total_executions, tce.status_changed_at
FROM tool_creation_events tce
JOIN tool_statistics ts ON tce.tool_name = ts.tool_name
WHERE tce.status = 'deleted'
  AND ts.success_rate > 0.85
  AND ts.total_executions > 20;

-- Tool lifecycle audit trail:
SELECT tool_name, event_type, event_time, reason, triggered_by
FROM tool_lifecycle_events
WHERE tool_name = 'my_tool'
ORDER BY event_time DESC;
$comment$;

-- Verification queries
SELECT 'Migration complete!' AS status;
SELECT COUNT(*) AS total_tools, status, 
       COUNT(*) FILTER (WHERE status = 'active') AS active_count,
       COUNT(*) FILTER (WHERE status = 'deleted') AS deleted_count,
       COUNT(*) FILTER (WHERE status = 'archived') AS archived_count
FROM tool_creation_events
GROUP BY status;
