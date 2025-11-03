-- Initialize PostgreSQL extensions for Neural Engine
-- This runs automatically when the database is first created

-- Enable pgvector for embeddings (Phase 10a, 10c)
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension is available
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE NOTICE 'pgvector extension enabled successfully';
    ELSE
        RAISE WARNING 'pgvector extension not available';
    END IF;
END $$;
