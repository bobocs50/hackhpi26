import { formatSigned, toPercent } from '../data'
import type { VisionFrame } from '../data'

type DashboardInsightsProps = {
  currentFrame: VisionFrame
}

type MetricCardProps = {
  label: string
  value: string
}

function MetricCard({ label, value }: MetricCardProps) {
  return (
    <article className="rounded-2xl border border-white/6 bg-[#141518] px-3.5 py-2.5 shadow-[0_14px_30px_rgba(0,0,0,0.18)]">
      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-zinc-500">{label}</p>
      <p className="mt-5 text-[1.45rem] font-semibold leading-none tabular-nums text-zinc-100">{value}</p>
    </article>
  )
}

export function DashboardInsights({ currentFrame }: DashboardInsightsProps) {
  return (
    <section className="grid h-full min-h-0 gap-2.5 lg:grid-rows-[repeat(3,minmax(0,auto))_minmax(0,1fr)]">
      <MetricCard label="Velocity" value={toPercent(currentFrame.steering.speed_factor)} />
      <MetricCard label="Steering" value={`${formatSigned(currentFrame.steering.steering_angle_deg)}°`} />
      <MetricCard label="Danger Score" value={currentFrame.danger_reasoning.score.toFixed(2)} />

      <article className="min-h-0 rounded-2xl border border-white/6 bg-[#141518] px-4 py-3 shadow-[0_16px_40px_rgba(0,0,0,0.22)]">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Reason</p>
        <h2 className="mt-2 text-sm font-semibold tracking-tight text-white">
          {currentFrame.danger_reasoning.primary_reason}
        </h2>
        <p className="mt-2 line-clamp-3 text-[13px] leading-5 text-zinc-400">
          {currentFrame.danger_reasoning.secondary_reason}
        </p>
      </article>
    </section>
  )
}
