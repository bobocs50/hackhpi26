# AgroCIT: Deterministic Safety Intelligence For Field Autonomy

Real-time hazard interpretation and APF-based steering support for agricultural vehicles, built around an upload-to-dashboard workflow.

## 1. Hero Summary

Agricultural autonomy fails hardest when perception is uncertain and reaction is late. This project focuses on that gap.

AgroCIT ingests a short frame sequence, runs tracking and deterministic safety inference, and returns frame-by-frame reasoning plus control suggestions. The system is intentionally hybrid: detector + tracker + deterministic graph/physics logic, with visual outputs that operators and judges can inspect directly.

This is not an end-to-end learned autonomy stack. It is a transparent safety pipeline designed for explainability and fast iteration in field-like scenarios.

## 2. Demo/User Flow

1. Upload frames from the UI (current tracker pipeline processes up to 20 frames).
2. Backend stores the run and starts background processing.
3. YOLO + ResNet ReID tracker writes annotated frames and tracking CSV.
4. CSV is mapped to kinematics and fed into deterministic SGG + APF logic.
5. Backend writes run-scoped `final_output.json`.
6. Frontend dashboard loads run visual data (SGG + APF), supports frame stepping, research/chat, and report views.
7. Chat/report can use Claude when configured, with deterministic fallback behavior.

## 3. Key Features

- Frame upload pipeline with run IDs and status polling.
- YOLO detection + ResNet-embedding ReID tracking over uploaded frames.
- Deterministic SGG inference for certainty, TTC, and danger quality.
- APF control output for steering (`delta_theta`) and target velocity (`v_target`).
- APF visualization payload: potential surface, steering cue, suggested path trajectory, corridor, and entities.
- Run-grounded chat endpoint (`/runs/{run_id}/chat`) and report endpoint (`/report`).

## 4. Architecture Overview

High-level flow:

1. Frontend uploads image frames to FastAPI.
2. FastAPI creates `run_id`, persists files/metadata, and starts tracker task.
3. Tracker (`backend/yolo_tracker.py`) emits:
   - annotated frame images
   - tracking CSV (`multiclass_tracking_20frames.csv`)
4. Backend maps CSV into kinematics entities.
5. Deterministic SGG inference + processing generates graph semantics and danger classes.
6. APF service computes lateral steering, longitudinal velocity, potential field (`z_surface`), corridor, and rollout trajectory.
7. Backend writes `final_output.json` per run under `backend/data/uploads/<run_id>/`.
8. Frontend fetches run-specific visual data and renders dashboard pages.

## 5. Math And Decision Logic

### SGG certainty

Given detector confidence and track age:

$$
c_i = \text{Conf}_{YOLO} \cdot \left(1 - e^{-\lambda \cdot Age_{track}}\right)
$$

### Time-to-collision (TTC)

Relative velocity is projected toward ego. If the object is moving away, TTC is infinite.

$$
TTC_i = \frac{dist}{\max(\epsilon, v_{closing})}, \quad TTC_i \to \infty\ \text{if}\ v_{closing}\le 0
$$

### Danger quality

Class severity weight with exponential TTC decay:

$$
q_i = \left(\frac{W_{class}}{W_{max}}\right) \cdot e^{-k \cdot TTC_i}
$$

### Lateral APF (steering)

Implemented components include:

- Crop-edge attractive term from occupancy-grid gradient and PD edge tracking.
- Repulsive obstacle term using certainty, danger quality, distance, and forward exponential decay.
- Exponential forward decay term $e^{-\alpha y}$ to prioritize near-forward threats.
- Vortex (tangential) component to reduce symmetric deadlocks.
- Adaptive repulsion weight based on nearest hazard distance.
- Steering clamp and rate limiting for control smoothness.

### Longitudinal APF (target velocity)

- Builds a forward safety corridor polygon.
- Computes in-corridor threat score from predicted entities.
- Reduces target speed from base velocity based on max in-corridor threat.

### APF surface visualization

`z_surface` is log-scaled potential:

$$
z_{surface} = \log(1 + U)
$$

This improves readability versus raw potential magnitudes.

## 6. Tech Stack

### Frontend

- React + TypeScript + Vite
- Plotly via `react-plotly.js`
- Tailwind CSS

### Backend

- FastAPI + Uvicorn
- Pydantic
- NumPy, SciPy, Shapely
- OpenCV
- PyTorch + TorchVision
- Ultralytics YOLO

### Optional AI services

- Anthropic Claude via `ANTHROPIC_API_KEY` for report/chat generation
- Deterministic fallback when key is absent or remote call fails

## 7. Repository Structure

```text
.
├── backend/
│   ├── main.py
│   ├── yolo_tracker.py
│   ├── reporting.py
│   ├── requirements.txt
│   ├── src/agri_nav/
│   │   ├── dto/
│   │   ├── logic/
│   │   ├── mapper/
│   │   ├── service/
│   │   └── viz/
│   └── data/uploads/
├── frontend/
│   ├── src/
│   └── package.json
└── README.md
```

Supporting docs:

- Backend details: [backend/README.md](backend/README.md)
- Frontend details: [frontend/README.md](frontend/README.md)

## 8. Local Setup And Run

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH=src python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend docs:

- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host
```

Default local UI URL: http://localhost:5173

### Environment variables

- `ANTHROPIC_API_KEY` (optional, enables Claude-backed report/chat)
- `ANTHROPIC_MODEL` (optional override)
- `CORS_ORIGINS` (optional comma-separated list)

## 9. Backend API Overview

### `POST /runs/upload-frames`

Uploads frame files, creates `run_id`, starts background tracker processing.

### `GET /runs/{run_id}/frames`

Returns run status, tracker status, and uploaded frame list.

### `GET /runs/{run_id}/visual-data`

Returns run-scoped final visual payload when ready (`final_output.json`).

### `POST /runs/{run_id}/chat`

Run-grounded chat endpoint using Claude when configured, fallback otherwise.

### `GET /report`

Returns run summary report (Claude-backed if available, fallback if not).

### `GET /mock-visual-data` (optional demo fallback)

Returns live/fixture demo visual data when upload-run output is not used.

## 10. Current Limitations And Next Steps

- Current tracker processing window is short (first 20 frames), suitable for demo runs, not long missions.
- Runtime dependencies are heavy (Torch/YOLO/OpenCV), so startup and environment setup are non-trivial.
- SGG/APF are deterministic and explainable, but still require broader field validation and calibration.
- Upload pipeline currently assumes image frame inputs, not full sensor fusion.

Planned improvements:

- Longer sequence processing and streaming ingestion.
- Better model/runtime packaging for reproducible deployment.
- Expanded evaluation on diverse weather/lighting/terrain conditions.
- Richer operator UX for uncertainty and intervention planning.

## 11. Team / Hackathon Context

Built for HackHPI 2026 as a practical safety-intelligence layer for agricultural autonomy: combining interpretable perception outputs, deterministic decision logic, and operator-facing visualization/reporting.