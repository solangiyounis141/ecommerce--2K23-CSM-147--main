# Backend (FastAPI + PostgreSQL) - Sprint 2 setup

## Local setup
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # then edit values (never commit .env)
```
Create the database once: `createdb apparel_store` (or use pgAdmin).

## Environment variables
| Variable | Purpose |
|---|---|
| `DATABASE_URL` | e.g. `postgresql+psycopg2://postgres:PASSWORD@localhost:5432/apparel_store` |
| `JWT_SECRET` | Long random string used to sign tokens |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Admin account created by the seed command |

## Run
```bash
export $(grep -v '^#' .env | xargs)      # Windows PowerShell: set each variable manually
alembic upgrade head                     # migrations
python -m app.seed                       # sample data (safe to repeat)
uvicorn app.main:app --reload            # API + docs at http://127.0.0.1:8000/docs
```

## Tests
```bash
JWT_SECRET=test-secret python -m pytest -q
```
