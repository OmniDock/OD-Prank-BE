# Database Management

## Structure
- `migrations/rls/` - Row Level Security setup
- `scripts/` - Helper scripts for database operations
- `seeds/` - Development data

## Usage

### Apply RLS setup:
```bash
cd db/scripts
./apply.sh ../migrations/rls/001_enable_rls.sql
./apply.sh ../migrations/rls/002_create_policies.sql
```

### For production (Railway):
Upload SQL files to Railway's database console or include in deployment pipeline.
