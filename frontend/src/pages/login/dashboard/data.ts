import { FileText, LayoutDashboard, Upload } from 'lucide-react'

import mockVisionRun from '../../../data/mockVisionRun.json'

export type Point = {
  x: number
  y: number
}

export type Annotation = {
  id: string
  label: string
  text_label: string
  certainty: number
  bbox: {
    x: number
    y: number
    width: number
    height: number
  }
  segment_points?: Point[]
  reason?: string
}

export type VisionFrame = {
  frame_file: string
  frame_index: number
  timestamp_ms: number
  annotations: Annotation[]
  steering: {
    recommended_action: string
    steering_angle_deg: number
    speed_factor: number
    brake_factor: number
    vector_reasoning?: string[]
  }
  danger_reasoning: {
    level: 'low' | 'medium' | 'high'
    score: number
    primary_reason: string
    secondary_reason: string
  }
  uncertainty: {
    overall: number
    notes?: string[]
  }
  summary: string
}

export type VisionRun = {
  run_id: string
  source: {
    folder_name: string
    location_hint: string
    captured_at: string
    sampling_rate_fps: number
    frame_width: number
    frame_height: number
  }
  frames: VisionFrame[]
}

export type LevelTheme = {
  tone: string
  badge: string
  box: string
}

export type DetectionBadge = Annotation & {
  color: LevelTheme
}

export const visionRun = mockVisionRun as VisionRun

export const levelTheme = {
  low: {
    tone: 'text-emerald-300',
    badge: 'border-emerald-500/30 bg-emerald-500/12 text-emerald-200',
    box: 'border-emerald-400/90 bg-emerald-500/6 text-emerald-200',
  },
  medium: {
    tone: 'text-amber-300',
    badge: 'border-amber-500/30 bg-amber-500/12 text-amber-200',
    box: 'border-amber-400/90 bg-amber-500/6 text-amber-100',
  },
  high: {
    tone: 'text-red-300',
    badge: 'border-red-500/30 bg-red-500/12 text-red-200',
    box: 'border-red-400/90 bg-red-500/6 text-red-100',
  },
} as const

export function getLevelTheme(level: keyof typeof levelTheme) {
  return levelTheme[level]
}

export function formatSeconds(timestampMs: number) {
  return `${(timestampMs / 1000).toFixed(1)}s`
}

export function toPercent(value: number) {
  return `${Math.round(value * 100)}%`
}

export function formatSigned(value: number) {
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}`
}

export function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function humanizeAction(value: string) {
  return value
    .split('_')
    .map((part) => capitalize(part))
    .join(' ')
}

export function getSteeringDirection(value: number) {
  if (value < -0.25) {
    return 'left'
  }

  if (value > 0.25) {
    return 'right'
  }

  return 'straight'
}

export function getAnnotationTheme(label: string) {
  const normalized = label.toLowerCase()

  if (normalized.includes('worker') || normalized.includes('person')) {
    return levelTheme.high
  }

  if (
    normalized.includes('rock') ||
    normalized.includes('obstacle') ||
    normalized.includes('equipment')
  ) {
    return levelTheme.medium
  }

  return levelTheme.low
}

export const navItems = [
  { label: 'Upload', icon: Upload, key: 'upload', enabled: true },
  { label: 'Dashboard', icon: LayoutDashboard, key: 'dashboard', enabled: true },
  { label: 'Report', icon: FileText, key: 'report', enabled: true },
] as const
