# Backend Setup

This backend uses FastAPI.

## 1) Install dependencies

From this folder:

```bash
make install
```

If `make` is not available, use:

```bash
/usr/local/bin/python3 -m pip install -r requirements.txt
```

## 2) Run dev server

```bash
make dev
```

If `make` is not available, use:

```bash
/usr/local/bin/python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 3) Open docs

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Current Upload Flow

- `POST /runs/upload-frames`
  - upload the frame images
  - backend stores them, marks the run as `processing`, and returns a `run_id`
- `GET /runs/{run_id}/frames`
  - inspect the stored frame list for that run
- `GET /report`
  - current report endpoint
