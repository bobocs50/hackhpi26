# Frontend Init

This frontend is the dashboard layer for an agriculture safety hackathon project.

## Purpose

Show video or frame-based ML results from the backend in a way that is clear, explainable, and useful for a demo.

The dashboard should help a viewer understand:

- what was detected
- why it is dangerous
- how certain the model is
- what steering action is recommended
- why the system would slow down, dodge, or stop

## Stack

- Frontend: Vite, React, TypeScript
- Planned UI: Tailwind, shadcn/ui, Lucide React, Plotly
- Backend contract: FastAPI + Pydantic JSON responses

## UI Conventions

- Use `lucide-react` as the only icon library for the dashboard
- Use Lucide icons for nav, playback controls, status chips, and light explanatory UI
- Do not introduce a second icon set unless Lucide cannot cover a concrete dashboard need

## Core Frontend Job

The frontend is not responsible for ML logic.

Its job is to:

- fetch structured run or frame data from the backend
- map backend JSON into DTOs or UI-safe models
- render video or frame content
- draw overlays like boxes, labels, confidence, and steering vectors
- show reasoning, uncertainty, and summary panels
- provide simple controls for playback and layer visibility

## Recommended Dashboard Layout

- Center: video player or frame viewer with overlays
- Left: current scene summary, danger reasoning, explanation
- Right: controls, toggles, legend, playback settings
- Bottom: timeline and charts for confidence, danger score, steering magnitude

## Important Data Shape

Frontend should prefer one stable GET response grouped by `frame_index` or `timestamp_ms`.

Each frame should ideally include:

- `frame_index`
- `timestamp_ms`
- `detections`
- `steering`
- `danger_reasoning`
- `uncertainty`
- `summary`

Each detection should ideally include:

- `id`
- `label`
- `confidence`
- `bbox`
- `reason`

## Frontend Rules

- Keep API logic outside view components
- Use adapters between backend JSON and rendered UI models
- Keep components small and readable
- Always show loading and error states
- Do not over-engineer early
- Make the video area the main visual focus
- Every overlay layer should be toggleable

## Team Context

- Philipp: frontend, API integration, DTOs
- Arash: object detection
- Kai: steering vectors and vector reasoning
- Nils: presentation and storyline

## Codex Context

Detailed Codex project context lives in:

- `codex-agents/init.yaml`
- `codex-agents/project-context.md`
- `codex-agents/ui-agent.md`
- `codex-agents/explorer-agent.md`
- `codex-agents/builder-agent.md`
