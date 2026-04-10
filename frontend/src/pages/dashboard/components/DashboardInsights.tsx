import { ArrowLeft, ArrowRight } from 'lucide-react'

import { levelTheme } from '../data'
import type { DetectionBadge, VisionFrame } from '../types'
import { formatSigned, getAnnotationTheme, getSteeringDirection, humanizeAction, toPercent } from '../utils'

type DashboardInsightsProps = {
  currentFrame: VisionFrame
  detectionBadges: DetectionBadge[]
}

type MetricCardProps = {
  label: string
  value: string
  detail: string
}

function MetricCard({ label, value, detail }: MetricCardProps) {
  return (
    <article className="rounded-2xl border border-white/6 bg-[#141518] p-3.5 shadow-[0_14px_30px_rgba(0,0,0,0.18)]">
      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-zinc-500">{label}</p>
      <p className="mt-2 text-lg font-semibold tabular-nums text-zinc-100">{value}</p>
      <p className="mt-1 text-sm text-zinc-500">{detail}</p>
    </article>
  )
}

export function DashboardInsights({ currentFrame, detectionBadges }: DashboardInsightsProps) {
  const levelStyle = levelTheme[currentFrame.danger_reasoning.level]
  const steeringDirection = getSteeringDirection(currentFrame.steering.steering_angle_deg)
  const summaryMetrics = [
    {
      label: 'Speed',
      value: toPercent(currentFrame.steering.speed_factor),
      detail: currentFrame.steering.speed_factor >= 0.5 ? 'Normal' : 'Reduced',
    },
    {
      label: 'Brake',
      value: toPercent(currentFrame.steering.brake_factor),
      detail: currentFrame.steering.brake_factor > 0 ? 'Applied' : 'None',
    },
    {
      label: 'Objects',
      value: String(currentFrame.annotations.length),
      detail: 'Detected',
    },
    {
      label: 'Steering',
      value: `${formatSigned(currentFrame.steering.steering_angle_deg)}°`,
      detail: currentFrame.steering.steering_angle_deg >= 0 ? 'Right' : 'Left',
    },
  ]
  const visibleBadges = detectionBadges.slice(0, 4)

  return (
    <>
      <section className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(280px,320px)]">
        <article className="rounded-2xl border border-white/6 bg-[#15171a] p-4 shadow-[0_16px_36px_rgba(0,0,0,0.2)]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500">Current Decision</p>
          <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-3">
              <div className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${levelStyle.badge}`}>
                {currentFrame.danger_reasoning.level} Risk
              </div>
              <div>
                <p className="text-3xl font-semibold tabular-nums text-white">
                  {currentFrame.danger_reasoning.score.toFixed(2)}
                </p>
                <p className="mt-1 text-sm text-zinc-400">{currentFrame.danger_reasoning.primary_reason}</p>
              </div>
            </div>
            <div className="max-w-sm rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Recommended Action</p>
              <div className="mt-2 flex items-center gap-2 text-lg font-semibold text-white">
                {steeringDirection === 'left' ? <ArrowLeft className="h-5 w-5 text-amber-300" /> : null}
                {steeringDirection === 'right' ? <ArrowRight className="h-5 w-5 text-amber-300" /> : null}
                <span>{humanizeAction(currentFrame.steering.recommended_action)}</span>
              </div>
            </div>
          </div>
        </article>

        <aside className="grid gap-3 sm:grid-cols-2 xl:grid-cols-2">
          {summaryMetrics.map((metric) => (
            <MetricCard
              key={metric.label}
              label={metric.label}
              value={metric.value}
              detail={metric.detail}
            />
          ))}
        </aside>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <article className="rounded-2xl border border-white/6 bg-[#141518] p-5 shadow-[0_16px_40px_rgba(0,0,0,0.22)]">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Analysis</p>
          <h2 className="mt-4 text-xl font-semibold tracking-tight text-white">
            {currentFrame.danger_reasoning.primary_reason}
          </h2>
          <p className="mt-3 text-sm leading-6 text-zinc-300">{currentFrame.summary}</p>
          <p className="mt-2 text-sm leading-6 text-zinc-500">
            {currentFrame.danger_reasoning.secondary_reason}
          </p>

          <div className="mt-5 flex flex-wrap gap-2">
            {visibleBadges.map((annotation) => (
              <span
                key={annotation.id}
                className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${annotation.color.badge}`}
              >
                {annotation.text_label} {Math.round(annotation.certainty * 100)}%
              </span>
            ))}
            {detectionBadges.length > visibleBadges.length ? (
              <span className="inline-flex items-center rounded-full border border-white/8 bg-white/[0.03] px-3 py-1 text-xs font-medium text-zinc-400">
                +{detectionBadges.length - visibleBadges.length} more
              </span>
            ) : null}
          </div>

          {(currentFrame.steering.vector_reasoning ?? []).length > 0 ? (
            <div className="mt-6 rounded-2xl border border-white/6 bg-white/[0.02] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Reasoning</p>
              <div className="mt-3 space-y-2">
                {(currentFrame.steering.vector_reasoning ?? []).map((item) => (
                  <p key={item} className="text-sm leading-6 text-zinc-300">
                    {item}
                  </p>
                ))}
              </div>
            </div>
          ) : null}
        </article>

        <aside className="space-y-4">
          <article className="rounded-2xl border border-white/6 bg-[#141518] p-5 shadow-[0_16px_40px_rgba(0,0,0,0.22)]">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Scene Data</p>
            <div className="mt-4 space-y-3">
              {currentFrame.annotations.length === 0 ? (
                <div className="rounded-xl border border-white/6 bg-white/[0.02] px-4 py-3 text-sm text-zinc-400">
                  No objects or hazards are flagged in this frame.
                </div>
              ) : null}
              {currentFrame.annotations.map((annotation) => (
                <div key={annotation.id} className="rounded-xl border border-white/6 bg-white/[0.02] p-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-white">{annotation.text_label}</p>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[11px] ${getAnnotationTheme(annotation.label).badge}`}
                    >
                      {annotation.label}
                    </span>
                  </div>
                  <p className="mt-1.5 text-sm leading-6 text-zinc-400">
                    {annotation.reason ?? 'No additional reasoning.'}
                  </p>
                </div>
              ))}
            </div>
          </article>

          <article className="rounded-2xl border border-white/6 bg-[#141518] p-5 shadow-[0_16px_40px_rgba(0,0,0,0.22)]">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Uncertainty</p>
            <p className="mt-4 text-3xl font-semibold tabular-nums text-white">
              {currentFrame.uncertainty.overall.toFixed(2)}
            </p>
            <div className="mt-3 space-y-2">
              {(currentFrame.uncertainty.notes ?? []).length > 0 ? (
                (currentFrame.uncertainty.notes ?? []).map((note) => (
                  <p key={note} className="text-sm leading-6 text-zinc-400">
                    {note}
                  </p>
                ))
              ) : (
                <p className="text-sm leading-6 text-zinc-400">
                  Confidence is stable for this frame. No additional uncertainty notes were provided.
                </p>
              )}
            </div>
          </article>
        </aside>
      </section>
    </>
  )
}
