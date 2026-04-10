import type { VisionFrame, VisionRun } from '../dashboard/types'
import { capitalize, formatSeconds, humanizeAction, toPercent } from '../dashboard/utils'
import type { RunReport } from './types'

export function buildRunReport(run: VisionRun): RunReport {
  const frames = run.frames
  if (frames.length === 0) {
    return {
      metadata: [
        { label: 'Run ID', value: run.run_id, detail: 'Structured source ID' },
        { label: 'Folder', value: run.source.folder_name, detail: 'Input frame batch' },
        {
          label: 'Captured',
          value: formatCapturedAt(run.source.captured_at),
          detail: run.source.location_hint,
        },
        {
          label: 'Resolution',
          value: `${run.source.frame_width} x ${run.source.frame_height}`,
          detail: `${run.source.sampling_rate_fps} FPS sampling`,
        },
      ],
      summary: {
        headline: 'No frames available',
        overview: 'The selected run does not contain any frames yet.',
        keyFindings: 'No hazards or events could be derived from the current dataset.',
        operationalNotes: 'Add frames to generate report metrics and charts.',
        generatedBy: 'Local structured summary',
      },
      kpis: [
        { label: 'Peak Danger', value: '0.00', detail: 'No frames available' },
        { label: 'Avg Danger', value: '0.00', detail: 'No frames available' },
        { label: 'Avg Uncertainty', value: '0.00', detail: 'No frames available' },
        { label: 'Avg Speed', value: '0%', detail: '0% average brake' },
        { label: 'Detections', value: '0', detail: '0 hazard labels' },
        { label: 'Risk Mix', value: '0/0/0', detail: 'Low / medium / high' },
      ],
      peakEvent: null,
      charts: {
        riskTrend: [],
        controlTrend: [],
        detectionsByLabel: [],
        riskDistribution: [
          { label: 'Low', value: 0, color: '#34d399' },
          { label: 'Medium', value: 0, color: '#f59e0b' },
          { label: 'High', value: 0, color: '#f87171' },
        ],
      },
    }
  }

  const peakFrame = frames.reduce((highest, frame) =>
    frame.danger_reasoning.score > highest.danger_reasoning.score ? frame : highest,
  )
  const labelCounts = countLabels(frames)
  const riskCounts = countRiskLevels(frames)
  const durationSeconds = (frames.at(-1)?.timestamp_ms ?? 0) / 1000
  const averageDanger = average(frames.map((frame) => frame.danger_reasoning.score))
  const averageUncertainty = average(frames.map((frame) => frame.uncertainty.overall))
  const averageSpeed = average(frames.map((frame) => frame.steering.speed_factor))
  const averageBrake = average(frames.map((frame) => frame.steering.brake_factor))

  return {
    metadata: [
      { label: 'Run ID', value: run.run_id, detail: 'Structured source ID' },
      { label: 'Folder', value: run.source.folder_name, detail: 'Input frame batch' },
      {
        label: 'Captured',
        value: formatCapturedAt(run.source.captured_at),
        detail: run.source.location_hint,
      },
      {
        label: 'Resolution',
        value: `${run.source.frame_width} x ${run.source.frame_height}`,
        detail: `${run.source.sampling_rate_fps} FPS sampling`,
      },
      {
        label: 'Run Span',
        value: `${frames.length} frames`,
        detail: `${durationSeconds.toFixed(1)}s total`,
      },
    ],
    summary: buildSummary(run, peakFrame, labelCounts, riskCounts),
    kpis: [
      {
        label: 'Peak Danger',
        value: peakFrame.danger_reasoning.score.toFixed(2),
        detail: `Frame ${peakFrame.frame_index + 1} at ${formatSeconds(peakFrame.timestamp_ms)}`,
      },
      {
        label: 'Avg Danger',
        value: averageDanger.toFixed(2),
        detail: `${riskCounts.high} high-risk frames`,
      },
      {
        label: 'Avg Uncertainty',
        value: averageUncertainty.toFixed(2),
        detail: 'Across all frames',
      },
      {
        label: 'Avg Speed',
        value: toPercent(averageSpeed),
        detail: `${toPercent(averageBrake)} average brake`,
      },
      {
        label: 'Detections',
        value: String(totalDetections(labelCounts)),
        detail: `${Object.keys(labelCounts).length} hazard labels`,
      },
      {
        label: 'Risk Mix',
        value: `${riskCounts.low}/${riskCounts.medium}/${riskCounts.high}`,
        detail: 'Low / medium / high',
      },
    ],
    peakEvent: {
      frame: peakFrame,
      timestamp: formatSeconds(peakFrame.timestamp_ms),
      action: humanizeAction(peakFrame.steering.recommended_action),
      objectLabels: peakFrame.annotations.map((annotation) => annotation.text_label),
    },
    charts: {
      riskTrend: [
        {
          name: 'Danger Score',
          color: '#f59e0b',
          points: frames.map((frame) => ({
            x: formatSeconds(frame.timestamp_ms),
            y: frame.danger_reasoning.score,
          })),
        },
      ],
      controlTrend: [
        {
          name: 'Speed Factor',
          color: '#34d399',
          points: frames.map((frame) => ({
            x: formatSeconds(frame.timestamp_ms),
            y: frame.steering.speed_factor,
          })),
        },
        {
          name: 'Brake Factor',
          color: '#fb7185',
          points: frames.map((frame) => ({
            x: formatSeconds(frame.timestamp_ms),
            y: frame.steering.brake_factor,
          })),
        },
      ],
      detectionsByLabel: Object.entries(labelCounts).map(([label, value]) => ({
        label: capitalize(label),
        value,
        color: label.includes('worker') ? '#f87171' : '#f59e0b',
      })),
      riskDistribution: [
        { label: 'Low', value: riskCounts.low, color: '#34d399' },
        { label: 'Medium', value: riskCounts.medium, color: '#f59e0b' },
        { label: 'High', value: riskCounts.high, color: '#f87171' },
      ],
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

function totalDetections(counts: Record<string, number>) {
  return Object.values(counts).reduce((sum, value) => sum + value, 0)
}

function formatCapturedAt(value: string) {
  const date = new Date(value)

  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('en-US')
}

function normalizeSentence(value: string) {
  return value.trim().replace(/\.$/, '').toLowerCase()
}
