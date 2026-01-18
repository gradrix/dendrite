-- Migration 001: Generic Tool Storage
-- Provides persistent key-value storage for all tools
-- Replaces Redis for credentials, accumulated knowledge, etc.

-- Generic tool storage table
CREATE TABLE IF NOT EXISTS tool_storage (
    namespace VARCHAR(255) NOT NULL,      -- Tool/domain namespace (e.g., 'strava', 'github')
    key VARCHAR(255) NOT NULL,            -- Key within namespace (e.g., 'credentials', 'kudos_givers')
    value JSONB NOT NULL,                 -- Flexible JSON value
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,                 -- Optional TTL for tokens/cache
    PRIMARY KEY (namespace, key)
);

-- Index for expiration cleanup
CREATE INDEX IF NOT EXISTS idx_tool_storage_expires ON tool_storage(expires_at) 
    WHERE expires_at IS NOT NULL;

-- Index for namespace queries
CREATE INDEX IF NOT EXISTS idx_tool_storage_namespace ON tool_storage(namespace);

-- Function to auto-update updated_at
CREATE OR REPLACE FUNCTION update_tool_storage_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for updated_at
DROP TRIGGER IF EXISTS tool_storage_updated_at ON tool_storage;
CREATE TRIGGER tool_storage_updated_at
    BEFORE UPDATE ON tool_storage
    FOR EACH ROW
    EXECUTE FUNCTION update_tool_storage_timestamp();

-- Grant permissions
GRANT ALL PRIVILEGES ON tool_storage TO dendrite;

-- Log
DO $$
BEGIN
    RAISE NOTICE 'Migration 001: tool_storage table created';
END $$;
