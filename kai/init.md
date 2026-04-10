# Project Init

This repository is a small hackathon monorepo for an agriculture vehicle safety dashboard.

## Purpose

The project combines ML perception outputs with a dashboard that explains danger detection and steering decisions.

The main demo goal is:

- show video or frame data from a vehicle camera
- highlight dangerous objects or situations
- explain why something is considered dangerous
- show recommended steering or stop behavior
- make uncertainty visible

## Repo Structure

- `backend/`: FastAPI API and future Pydantic data models
- `frontend/`: Vite, React, TypeScript dashboard
- `codex-agents/`: older root-level Codex notes

## What Each Part Does

### `backend/`

Backend should convert ML or detection results into a stable JSON contract for the frontend.

Right now it is still very small and only exposes `GET /test`.

### `frontend/`

Frontend should fetch the backend response and turn it into a dashboard with:

- video or frame viewer
- overlays
- reasoning panels
- controls
- charts

### `codex-agents/`

This folder exists at the repo root, but it currently looks older and less aligned with the newer frontend dashboard direction.

The more current project context for active frontend work lives in:

- `frontend/init.md`
- `frontend/codex-agents/init.yaml`
- `frontend/codex-agents/project-context.md`

## Structure Check

The overall split of `backend/` and `frontend/` makes sense.

What is good:

- clear separation between API and UI
- backend and frontend can move independently
- simple enough for a hackathon

What is still weak:

- backend is too thin to reflect the planned architecture yet
- root `codex-agents/` and `frontend/codex-agents/` overlap and can become confusing
- there is no shared typed contract folder yet between backend and frontend

## Recommended Direction

Keep the monorepo shape, but tighten responsibilities:

- `backend/` owns response schema and JSON contract
- `frontend/` owns rendering, dashboard UX, and DTO adapters
- choose one main Codex context location to avoid duplication

If the project grows, a useful future addition would be:

- `shared/` for common API schema examples or contract docs

You do not need that immediately for the hackathon, but it would reduce drift.

## Team Context

- Philipp: frontend, API integration, DTOs
- Arash: object detection
- Kai: steering vectors and vector reasoning
- Nils: presentation and storyline

## Current Priority

The most important architectural step is defining one stable backend GET payload grouped by frame or timestamp.

Once that exists, the frontend dashboard becomes straightforward to build.
