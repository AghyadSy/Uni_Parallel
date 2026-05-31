## Install

```powershell
cd D:\projects\WORK\backend
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
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
