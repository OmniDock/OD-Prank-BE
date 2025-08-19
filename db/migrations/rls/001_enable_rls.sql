-- Enable Row Level Security
-- Run after Alembic migrations

ALTER TABLE scenarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_lines ENABLE ROW LEVEL SECURITY;

