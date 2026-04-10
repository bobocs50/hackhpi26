import {
  capitalize,
  formatSeconds,
  humanizeAction,
  toPercent,
} from '../dashboard/data'
import type { VisionFrame, VisionRun } from '../dashboard/data'

type ReportDetail = {
  label: string
  value: string
}

export type RunReport = {
  metadata: ReportDetail[]
  summary: {
    headline: string
    overview: string
    keyFindings: string
    operationalNotes: string
    generatedBy: string
  }
  peakEvent: {
    frame: VisionFrame
    timestamp: string
    action: string
  } | null
}

export function buildRunReport(run: VisionRun): RunReport {
  const frames = run.frames
  if (frames.length === 0) {
    return {
      metadata: [
        { label: 'Folder', value: run.source.folder_name },
        { label: 'Captured', value: formatCapturedAt(run.source.captured_at) },
        { label: 'Location', value: run.source.location_hint },
        { label: 'Frames', value: '0 frames' },
        { label: 'Resolution', value: `${run.source.frame_width} x ${run.source.frame_height}` },
      ],
      summary: {
        headline: 'No frames available',
        overview: 'The selected run does not contain any frames yet.',
        keyFindings: 'No hazards or events could be derived from the current dataset.',
        operationalNotes: 'Add frames to generate a run summary.',
        generatedBy: 'Local structured summary',
      },
      peakEvent: null,
    }
  }

  const peakFrame = frames.reduce((highest, frame) =>
    frame.danger_reasoning.score > highest.danger_reasoning.score ? frame : highest,
  )
  const labelCounts = countLabels(frames)
  const riskCounts = countRiskLevels(frames)
  const durationSeconds = (frames.at(-1)?.timestamp_ms ?? 0) / 1000

  return {
    metadata: [
      { label: 'Folder', value: run.source.folder_name },
      { label: 'Captured', value: formatCapturedAt(run.source.captured_at) },
      { label: 'Location', value: run.source.location_hint },
      { label: 'Run Span', value: `${frames.length} frames / ${durationSeconds.toFixed(1)}s` },
      { label: 'Resolution', value: `${run.source.frame_width} x ${run.source.frame_height}` },
    ],
    summary: buildSummary(run, peakFrame, labelCounts, riskCounts),
    peakEvent: {
      frame: peakFrame,
      timestamp: formatSeconds(peakFrame.timestamp_ms),
      action: humanizeAction(peakFrame.steering.recommended_action),
    },
  }
}

function buildSummary(
  run: VisionRun,
  peakFrame: VisionFrame,
  labelCounts: Record<string, number>,
  riskCounts: Record<'low' | 'medium' | 'high', number>,
) {
  const firstFrame = run.frames[0]
  const lastFrame = run.frames.at(-1) ?? firstFrame
  const dominantHazard =
    Object.entries(labelCounts).sort((left, right) => right[1] - left[1])[0]?.[0] ?? 'hazard'

  return {
    headline: `${capitalize(peakFrame.danger_reasoning.level)}-risk intervention around ${formatSeconds(peakFrame.timestamp_ms)}`,
    overview: [
      `The run opens with ${normalizeSentence(firstFrame.summary)}.`,
      `Risk peaks at ${formatSeconds(peakFrame.timestamp_ms)} when ${normalizeSentence(peakFrame.danger_reasoning.primary_reason)}.`,
      `It ends with ${normalizeSentence(lastFrame.summary)}.`,
    ].join(' '),
    keyFindings: `The dominant detected hazard was ${dominantHazard}. At the peak event the system chose ${humanizeAction(
      peakFrame.steering.recommended_action,
    ).toLowerCase()} because ${normalizeSentence(peakFrame.danger_reasoning.secondary_reason)}.`,
    operationalNotes: `Risk distribution across the run was ${riskCounts.low} low, ${riskCounts.medium} medium, and ${riskCounts.high} high frames. Average speed stayed at ${toPercent(
      average(run.frames.map((frame) => frame.steering.speed_factor)),
    )}, while uncertainty averaged ${average(run.frames.map((frame) => frame.uncertainty.overall)).toFixed(2)}.`,
    generatedBy: 'Local structured summary',
  }
}

function average(values: number[]) {
  if (values.length === 0) {
    return 0
  }

  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function countLabels(frames: VisionFrame[]) {
  const counts: Record<string, number> = {}

  for (const frame of frames) {
    for (const annotation of frame.annotations) {
      counts[annotation.label] = (counts[annotation.label] ?? 0) + 1
    }
  }

  return counts
}

function countRiskLevels(frames: VisionFrame[]) {
  const counts = {
    low: 0,
    medium: 0,
    high: 0,
  }

  for (const frame of frames) {
    counts[frame.danger_reasoning.level] += 1
  }

  return counts
}

function formatCapturedAt(value: string) {
  const date = new Date(value)

  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('en-US')
}

function normalizeSentence(value: string) {
  return value.trim().replace(/\.$/, '').toLowerCase()
}
