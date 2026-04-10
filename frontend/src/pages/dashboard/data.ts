import { FileText, LayoutDashboard, Upload } from 'lucide-react'

import mockVisionRun from '../../data/mockVisionRun.json'

import type { VisionRun } from './types'

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

export const navItems = [
  { label: 'Upload', icon: Upload, key: 'upload', enabled: true },
  { label: 'Dashboard', icon: LayoutDashboard, key: 'dashboard', enabled: true },
  { label: 'Report', icon: FileText, key: 'report', enabled: true },
] as const
