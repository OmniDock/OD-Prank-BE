#!/bin/bash
set -e

if [ -z "$1" ]; then
    echo "Usage: ./apply.sh <sql-file>"
    echo "Example: ./apply.sh migrations/rls/001_enable_rls.sql"
    exit 1
fi

echo "🗄️  Applying: $1"

# Get DB URL from your app config
DB_URL=$(cd ../../ && python -c "from app.core.config import settings; print(settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://'))")
# DB_URL=$(python -c "import sys; sys.path.append('.'); from app.core.config import settings; print(settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://'))")
# DB_URL="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
psql "$DB_URL" -f "$1"
echo "✅ Applied successfully!"
