# Deployment Guide

## Railway Deployment

### Prerequisites
- GitHub/GitLab account
- Railway account (https://railway.app)
- Push code to GitHub repository

### Step 1: Create Railway Project

1. Go to https://railway.app
2. Click "New Project"
3. Choose "Deploy from GitHub repo"
4. Select your repository

### Step 2: Add PostgreSQL Database

1. Click "New" → "Database" → "Add PostgreSQL"
2. Railway automatically creates `DATABASE_URL` variable

### Step 3: Configure Environment Variables

Go to your service → "Variables" tab and add:

```bash
# JWT Secret (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=<your-secure-random-key>

# App Environment
APP_ENV=production
DEBUG=false

# CORS (Railway provides public domain automatically)
CORS_ALLOWED_ORIGINS=https://${{RAILWAY_PUBLIC_DOMAIN}}

# Database (automatically set by Railway PostgreSQL)
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

**Note:** Railway automatically sets `PORT` and `DATABASE_URL` for you.

### Step 4: Deploy

1. Push to your GitHub repository
2. Railway will automatically:
   - Build Docker image
   - Run migrations (`alembic upgrade head`)
   - Start the application
3. Your app will be available at `https://<your-app>.up.railway.app`

### Step 5: Initial Setup

After first deployment, you need to create the admin user:

1. Go to Railway → Your Service → "Connect"
2. Connect via Railway CLI or use the web terminal
3. Run:

```bash
# The admin user is created automatically by migration 001
# Default credentials:
# Email: admin@school.com
# Password: Admin123!
```

**IMPORTANT:** Change the default admin password after first login!

---

## Environment Variables Reference

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Yes | Set by Railway |
| `JWT_SECRET_KEY` | Secret key for JWT tokens | Yes | - |
| `JWT_ALGORITHM` | JWT algorithm | No | HS256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | No | 15 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | No | 7 |
| `APP_ENV` | Environment (development/production) | No | development |
| `DEBUG` | Debug mode | No | true |
| `CORS_ALLOWED_ORIGINS` | Allowed CORS origins (comma-separated) | No | * |
| `PORT` | Server port | No | 8000 (Railway sets automatically) |

---

## Health Check

Railway uses `/health` endpoint for health checks. The app is healthy when it returns:

```json
{"status": "healthy"}
```

---

## Logs

View logs in Railway dashboard:
- Service → "Deployments" → Click on deployment → "View Logs"

---

## Database Migrations

Migrations run automatically on deployment via the start command in `Dockerfile`:

```bash
uv run alembic upgrade head && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

To run migrations manually:
1. Connect to Railway service via CLI
2. Run: `uv run alembic upgrade head`

---

## Troubleshooting

### Build fails
- Check Dockerfile syntax
- Ensure all dependencies are in `pyproject.toml`
- Check Railway build logs

### Database connection error
- Verify `DATABASE_URL` is set correctly
- Check PostgreSQL service is running in Railway
- Ensure connection string format: `postgresql+asyncpg://...`

### Frontend not loading
- Verify frontend build succeeded (check `frontend/dist` exists)
- Check CORS settings
- Verify static files are served correctly

### 502 Bad Gateway
- Check if migrations ran successfully
- Verify health check endpoint responds
- Check application logs for startup errors

---

## Scaling

Railway free tier includes:
- 500 hours of usage per month
- 512MB RAM, shared CPU
- PostgreSQL database (500MB)

To scale:
1. Service → "Settings" → "Resources"
2. Upgrade plan if needed

---

## Backup

### Database Backup

Railway provides automatic backups for paid plans. For manual backup:

```bash
# Connect to Railway PostgreSQL
railway connect Postgres

# Dump database
pg_dump > backup.sql
```

---

## Custom Domain

1. Service → "Settings" → "Domains"
2. Add custom domain
3. Configure DNS records as shown by Railway
4. Update `CORS_ALLOWED_ORIGINS` to include your domain

---

## Security Checklist

- [ ] Change default admin password
- [ ] Set strong `JWT_SECRET_KEY` (use `openssl rand -hex 32`)
- [ ] Set `DEBUG=false` in production
- [ ] Configure proper CORS origins
- [ ] Enable Railway's built-in SSL/TLS
- [ ] Review user roles and permissions
- [ ] Set up database backups
- [ ] Monitor application logs
