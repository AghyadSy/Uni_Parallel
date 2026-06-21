## Install

```powershell
cd D:\projects\WORK\backend
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## PostgreSQL

Set PostgreSQL connection variables before running migrations:

```powershell
$env:POSTGRES_DB = "backend"
$env:POSTGRES_USER = "postgres"
$env:POSTGRES_PASSWORD = "postgres"
$env:POSTGRES_HOST = "127.0.0.1"
$env:POSTGRES_PORT = "5432"
```

Or use a single `DATABASE_URL`:

```powershell
$env:DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/backend"
```

## Migrate

```powershell
py manage.py migrate
```

## Seed Demo Data

```powershell
py manage.py seed_demo_data
```

## Run Server

```powershell
py manage.py runserver 127.0.0.1:8000
```

## Run Background Worker

Open another CMD or PowerShell window:

```powershell
cd D:\projects\WORK\backend
.venv\Scripts\activate
py manage.py run_background_worker
```

For one batch only:

```powershell
py manage.py run_background_worker --once
```
