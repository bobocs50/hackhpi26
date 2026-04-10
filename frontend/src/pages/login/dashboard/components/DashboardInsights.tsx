import { ArrowLeft, ArrowRight } from 'lucide-react'

import {
  formatSigned,
  getAnnotationTheme,
  getSteeringDirection,
  humanizeAction,
  levelTheme,
  toPercent,
} from '../data'
import type { DetectionBadge, VisionFrame } from '../data'

type DashboardInsightsProps = {
  currentFrame: VisionFrame
  detectionBadges: DetectionBadge[]
}

type MetricCardProps = {
  label: string
  value: string
}

function MetricCard({ label, value }: MetricCardProps) {
  return (
    <article className="rounded-2xl border border-white/6 bg-[#141518] px-4 py-3 shadow-[0_14px_30px_rgba(0,0,0,0.18)]">
      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-zinc-500">{label}</p>
      <p className="mt-8 text-[1.7rem] font-semibold leading-none tabular-nums text-zinc-100">{value}</p>
    </article>
  )
}

export function DashboardInsights({ currentFrame, detectionBadges }: DashboardInsightsProps) {
  const levelStyle = levelTheme[currentFrame.danger_reasoning.level]
  const steeringDirection = getSteeringDirection(currentFrame.steering.steering_angle_deg)
  const actionLabel = humanizeAction(currentFrame.steering.recommended_action)
  const summaryMetrics = [
    {
      label: 'Speed',
      value: toPercent(currentFrame.steering.speed_factor),
    },
    {
      label: 'Brake',
      value: toPercent(currentFrame.steering.brake_factor),
    },
    {
      label: 'Objects',
      value: String(currentFrame.annotations.length),
    },
    {
      label: 'Steering',
      value: `${formatSigned(currentFrame.steering.steering_angle_deg)}°`,
    },
  ]
  const visibleBadges = detectionBadges.slice(0, 4)

  return (
    <>
      <section className="rounded-[1.5rem] border border-[#31362f] bg-[linear-gradient(135deg,#20271d_0%,#1a1f1a_58%,#141716_100%)] px-5 py-4 shadow-[0_18px_40px_rgba(0,0,0,0.24)]">
        <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#a7b58f]">
          Recommended Action
        </p>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2.5">
              {steeringDirection === 'left' ? <ArrowLeft className="h-5 w-5 shrink-0 text-[#d9e8b4]" /> : null}
              {steeringDirection === 'right' ? <ArrowRight className="h-5 w-5 shrink-0 text-[#d9e8b4]" /> : null}
              <h2 className="text-[1.5rem] font-semibold tracking-tight text-white sm:text-[1.7rem]">
                {actionLabel}
              </h2>
            </div>
            <p className="mt-1.5 max-w-2xl text-sm leading-6 text-zinc-400">
              {currentFrame.danger_reasoning.primary_reason}
            </p>
          </div>

          <div className="flex shrink-0 flex-wrap gap-2">
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${levelStyle.badge}`}>
              {currentFrame.danger_reasoning.level} risk
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs font-medium uppercase tracking-[0.16em] text-zinc-200">
              Score {currentFrame.danger_reasoning.score.toFixed(2)}
            </span>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <aside className="grid grid-cols-2 gap-3 col-span-2 xl:col-span-4 xl:grid-cols-4">
          {summaryMetrics.map((metric) => (
            <MetricCard
              key={metric.label}
              label={metric.label}
              value={metric.value}
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
