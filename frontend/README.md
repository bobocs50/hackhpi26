# AgriVision Frontend

Judge-facing dashboard for the HackHPI 2026 agriculture safety demo.

## Purpose

The frontend visualizes frame-by-frame ML output from the backend so a viewer can understand:

- what the system detected
- why a scene is risky
- what steering action is recommended
- how certain the system is

## Stack

- Vite
- React
- TypeScript
- Tailwind CSS
- `lucide-react` for dashboard icons

## UI Rules

- Keep the video or frame area as the primary visual focus.
- Use `lucide-react` as the only dashboard icon library.
- Do not add a second icon set unless there is a concrete gap Lucide cannot cover.

## Development

```bash
npm install
npm run dev
```

## Current Entry Point

- Dashboard app: `src/pages/dashboard/App.tsx`
