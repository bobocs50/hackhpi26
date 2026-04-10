import { getLevelTheme } from '../dashboard/data'
import { capitalize } from '../dashboard/data'
import { buildRunReport } from './reportData'
import type { VisionRun } from '../dashboard/data'

type ReportViewProps = {
  run: VisionRun
}

export function ReportPage({ run }: ReportViewProps) {
  const report = buildRunReport(run)
  const peakLevelStyle = report.peakEvent
    ? getLevelTheme(report.peakEvent.frame.danger_reasoning.level)
    : getLevelTheme('low')

  if (!report.peakEvent) {
    return (
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-6 py-5">
        <section className="rounded-3xl border border-[#2a2d2f] bg-[linear-gradient(135deg,#1d221d_0%,#17191d_55%,#101114_100%)] px-6 py-6 shadow-[0_24px_60px_rgba(0,0,0,0.35)]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-500">Run Report</p>
          <h1 className="mt-3 text-[2rem] font-semibold tracking-tight text-white">No report data available</h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-zinc-300">
            The current run does not contain any frames yet, so there is nothing to summarize.
          </p>
        </section>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-6 py-5">
      <section className="rounded-3xl border border-[#2a2d2f] bg-[linear-gradient(135deg,#1d221d_0%,#17191d_55%,#101114_100%)] px-6 py-7 shadow-[0_24px_60px_rgba(0,0,0,0.35)]">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-500">Run Report</p>
          <h1 className="mt-3 max-w-4xl text-[2.3rem] font-semibold tracking-tight text-white">
            {report.summary.headline}
          </h1>
          <div className="mt-6 rounded-[1.75rem] border border-white/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.045),rgba(255,255,255,0.025))] p-7 sm:p-9">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Summary</p>
            <div className="mt-5 max-w-4xl space-y-5 text-base leading-8 text-zinc-100 sm:text-[1.02rem]">
              <p>{report.summary.overview}</p>
              <p>{report.summary.keyFindings}</p>
              <p>{report.summary.operationalNotes}</p>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap gap-2">
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${peakLevelStyle.badge}`}>
              {capitalize(report.peakEvent.frame.danger_reasoning.level)} risk peak
            </span>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-white/6 bg-[#141518] p-5 shadow-[0_16px_40px_rgba(0,0,0,0.22)]">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Run Context</p>
        <div className="mt-4 flex flex-wrap gap-3">
          {report.metadata.map((item) => (
            <ContextPill key={item.label} label={item.label} value={item.value} />
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-white/6 bg-[#141518] p-5 shadow-[0_16px_40px_rgba(0,0,0,0.22)]">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Critical Moment</p>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${peakLevelStyle.badge}`}>
            {capitalize(report.peakEvent.frame.danger_reasoning.level)} risk
          </span>
          <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-medium text-zinc-300">
            {report.peakEvent.timestamp}
          </span>
        </div>
        <h2 className="mt-4 text-lg font-semibold text-white">{report.peakEvent.frame.danger_reasoning.primary_reason}</h2>
        <p className="mt-2 text-sm leading-7 text-zinc-300 sm:text-base">
          {report.peakEvent.frame.summary}
        </p>
        <div className="mt-4 rounded-2xl border border-white/8 bg-white/[0.03] p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Suggested Action</p>
          <p className="mt-2 text-base font-semibold text-white">{report.peakEvent.action}</p>
        </div>
      </section>
    </div>
  )
}

function ContextPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-[160px] rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-zinc-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-zinc-100">{value}</p>
    </div>
  )
}
