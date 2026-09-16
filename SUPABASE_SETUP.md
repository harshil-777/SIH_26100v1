# Supabase Setup for Phase 0

## 1. Create Supabase project

1. Go to [supabase.com](https://supabase.com)
2. Sign in or create account
3. Create new project → name it `gem-compliance`
4. Wait for provisioning (~5 min)

## 2. Get connection string

In Supabase dashboard:
- **Settings** → **Database** → **Connection pooling** (tab)
- Mode: `Transaction` (NOT Session)
- Copy the connection string URI

⚠️ The URI will look like:
```
postgresql://postgres.XXXX:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres
```

## 3. Update `.env` in project root

```bash
DATABASE_URL=postgresql+asyncpg://postgres.XXXX:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres
REDIS_URL=redis://localhost:6379/0
ADAPTER_MODE=mock
SEED_DATA_DIR=WORKING DOCUMENTS
STORAGE_DIR=storage
```

**Key changes from Supabase's URI:**
- Replace `postgresql://` with `postgresql+asyncpg://`
- If password has `@`, `:`, `/`, or `#`, URL-encode it: `%40` `%3A` `%2F` `%23`

Example with special chars:
```
postgresql+asyncpg://postgres.abc123:pass%40word@aws-0-us-east-1.pooler.supabase.com:5432/postgres
```

## 4. Create schema and seed data

Run these from project root (`D:\I041_HARSHIL\GEM_SIH`):

```powershell
# Apply migrations
.\.venv\Scripts\python.exe -m alembic upgrade head

# Load seed fixtures
.\.venv\Scripts\python.exe -m app.db.seed
```

Expected output from seed:
```
tenders                             6
bidders                            12
bids                               12
document_types                     12
tender_document_requirements       18
bid_document_submissions           40
bid_declarations                    8
verification_results               75
debarred_entities                   4
documents                          38
```

## 5. Secure the database

Run this SQL in Supabase **SQL Editor** to enable RLS:

```sql
do $$
declare t text;
begin
  foreach t in array array[
    'users','tenders','bidders','bids','document_types',
    'tender_document_requirements','bid_document_submissions','bid_declarations',
    'documents','verification_results','compliance_scores','debarred_entities','audit_log'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
  end loop;
end $$;
```

This blocks the PostgREST API while leaving your Python app (which connects as `postgres`) fully working.

## 6. Verify seed loaded

Run this query in Supabase **SQL Editor**:

```sql
select
  (select count(*) from bids)                 as bids,
  (select count(*) from tenders)              as tenders,
  (select count(*) from document_types)       as document_types,
  (select count(*) from verification_results) as verifications,
  (select count(*) from documents)            as documents,
  (select count(*) from debarred_entities)    as debarred;
```

Expected result:
```
bids | tenders | document_types | verifications | documents | debarred
-----|---------|----------------|---------------|-----------|----------
  12 |       6 |             12 |            75 |        38 |        4
```

## 7. Test the API

```powershell
# Start the API server
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Then in another terminal:
```powershell
# Test the dashboard endpoint
curl http://localhost:8000/dashboard/bids

# Or browse
Start-Process http://localhost:8000/docs
```

Expected response: 12 bid rows with `overall_score: null` and `risk_level: null` (not verified yet).

## Troubleshooting

| Error | Fix |
|-------|-----|
| `asyncpg.exceptions.UndefinedTableError` | Schema not created; run `alembic upgrade head` |
| `asyncpg.exceptions.InvalidCatalogNameError` | Using wrong pooler mode (use `Transaction`, not `Session`) |
| `asyncpg.exceptions.CannotConnectNowError` | Check DATABASE_URL has correct host/port; test with `psql` |
| Dashboard returns `[]` | Schema created but seed didn't run; check `alembic upgrade head` succeeded first |

## For Docker (once installed)

Edit [docker-compose.yml](docker-compose.yml):

1. **Comment out the `postgres` service** (lines 2–16):
```yaml
  # postgres:
  #   image: postgres:15-alpine
  #   ...
```

2. **Update `api` and `worker` environment vars** to use Supabase:
```yaml
  api:
    # ...
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres.XXXX:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres
      REDIS_URL: redis://redis:6379/0
      # ... rest unchanged
```

3. **Update their `depends_on`** (remove postgres):
```yaml
  api:
    # ...
    depends_on:
      redis:
        condition: service_healthy
```

4. Start:
```bash
docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.db.seed
```
