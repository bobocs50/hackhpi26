import type { VisionFrame } from '../dashboard/types'

export type ReportMetric = {
  label: string
  value: string
  detail: string
}

export type ReportPoint = {
  x: string
  y: number
}

export type ReportSeries = {
  name: string
  color: string
  points: ReportPoint[]
}

export type ReportBarDatum = {
  label: string
  value: number
  color: string
}

export type RunReport = {
  metadata: ReportMetric[]
  summary: {
    headline: string
    overview: string
    keyFindings: string
    operationalNotes: string
    generatedBy: string
  }
  kpis: ReportMetric[]
  peakEvent: {
    frame: VisionFrame
    timestamp: string
    action: string
    objectLabels: string[]
  } | null
  charts: {
    riskTrend: ReportSeries[]
    controlTrend: ReportSeries[]
    detectionsByLabel: ReportBarDatum[]
    riskDistribution: ReportBarDatum[]
  }
}
