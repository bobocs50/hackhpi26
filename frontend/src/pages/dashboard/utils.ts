import { levelTheme } from './data'

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
