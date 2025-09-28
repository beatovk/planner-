# Entertainment Planner API - Operations Guide

## Quick Start

### Local Development

```bash
# 1. Setup environment
cd entertainment-planner-api
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp env.example .env
# Edit .env with your DATABASE_URL

# 3. Start development server
make dev
# Or manually:
# export PORT=8010
# export PYTHONPATH=.
# uvicorn apps.api.main:app --host 0.0.0.0 --port $PORT --reload
```

### Health Checks

```bash
# Local health check
make api-diag

# Or manually:
curl -sS "http://127.0.0.1:8010/api/health" | python3 -m json.tool
curl -sS "http://127.0.0.1:8010/api/health/db_diag" | python3 -m json.tool
```

## Deployment

### Staging Deployment

```bash
# 1. Deploy to staging
fly deploy -a planner-api-staging --no-cache --build-arg BUILD_REF=$(git rev-parse --short HEAD)

# 2. Check deployment
curl -sS "https://planner-api-staging.fly.dev/api/health" | python3 -m json.tool
curl -sS "https://planner-api-staging.fly.dev/api/health/db_diag" | python3 -m json.tool
```

### Production Deployment

```bash
# 1. Deploy to production
fly deploy -a planner-api-prod --no-cache --build-arg BUILD_REF=$(git rev-parse --short HEAD)

# 2. Check deployment
curl -sS "https://planner-api-prod.fly.dev/api/health" | python3 -m json.tool
```

## Database Operations

### Create Materialized View

```bash
# Connect to staging database
fly ssh console -a planner-api-staging -C "python3 -c \"
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.getenv('DATABASE_URL'))
with open('/app/create_mv_fixed.sql', 'r') as f:
    sql = f.read()
with engine.connect() as conn:
    conn.execute(text(sql))
    conn.commit()
    print('MV created and refreshed')
\""
```

### Refresh Materialized View

```bash
# Refresh MV on staging
fly ssh console -a planner-api-staging -C "python3 -c \"
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    conn.execute(text('REFRESH MATERIALIZED VIEW epx.places_search_mv;'))
    conn.commit()
    print('MV refreshed')
\""
```

## Monitoring

### API Endpoints

- `GET /api/health` - Basic health check
- `GET /api/health/db_diag` - Database diagnostics
- `GET /api/debug/version` - Code fingerprints
- `GET /api/places/search?q=...` - Search places
- `GET /api/rails?q=...&diag=1` - Get recommendations with diagnostics

### Key Metrics

- **Database records**: Check `mv_count` in `/api/health/db_diag`
- **Derived flags**: `romantic_cnt`, `chill_cnt`, `cinema_cnt`
- **Search performance**: Check `processing_time_ms` in search responses
- **Rails quality**: Check `debug.rails_sizes` when using `diag=1`

## Rollback

### Quick Rollback

```bash
# Rollback to previous version
fly releases -a planner-api-staging
fly machine update <machine-id> -a planner-api-staging --image <previous-image>

# Or redeploy specific tag
git checkout v0.1.0-stable-rails
fly deploy -a planner-api-staging --no-cache
```

### Emergency Stop

```bash
# Stop all machines
fly machine stop <machine-id> -a planner-api-staging
```

## Troubleshooting

### Common Issues

1. **Empty rails results**: Check if MV has data and derived flags are populated
2. **Search not working**: Verify FTS index exists and MV is refreshed
3. **Database connection**: Check DATABASE_URL and network connectivity
4. **Unicode errors**: Ensure all text is properly encoded

### Debug Commands

```bash
# Check database size
fly ssh console -a planner-api-staging -C "python3 /app/check_db_size.py"

# Check schema
fly ssh console -a planner-api-staging -C "python3 /app/check_schemas.py"

# View logs
fly logs -a planner-api-staging
```

## Environment Variables

| Variable | Description | Default | Staging | Production |
|----------|-------------|---------|---------|------------|
| `APP_ENV` | Environment name | `development` | `staging` | `production` |
| `PORT` | Server port | `8000` | `8000` | `8000` |
| `DATABASE_URL` | PostgreSQL connection | - | Required | Required |
| `REFRESH_MV_INTERVAL` | MV refresh interval (seconds) | `0` | `300` | `0` |
| `TRACE_RAILS` | Enable rails tracing | `0` | `1` | `0` |
| `ALLOW_TEXT_FALLBACK` | Allow text fallback | `0` | `0` | `0` |

## Release Process

1. **Tag release**: `git tag -a v0.1.0 -m "Release v0.1.0"`
2. **Deploy staging**: `fly deploy -a planner-api-staging`
3. **Test staging**: Run health checks and smoke tests
4. **Deploy production**: `fly deploy -a planner-api-prod`
5. **Monitor**: Check logs and metrics for 30 minutes
