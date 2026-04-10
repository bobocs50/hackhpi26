import { getLevelTheme } from '../dashboard/data'
import type { VisionRun } from '../dashboard/types'
import { capitalize } from '../dashboard/utils'
import { buildRunReport } from './reportData'

type ReportViewProps = {
  run: VisionRun
}

export function ReportView({ run }: ReportViewProps) {
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
          <p className="mt-6 max-w-4xl text-base leading-8 text-zinc-200">{report.summary.overview}</p>
          <div className="mt-6 flex flex-wrap gap-2">
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${peakLevelStyle.badge}`}>
              {capitalize(report.peakEvent.frame.danger_reasoning.level)} risk peak
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-medium text-zinc-300">
              {report.summary.generatedBy}
            </span>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(280px,0.75fr)]">
        <article className="rounded-2xl border border-white/6 bg-[#141518] p-6 shadow-[0_16px_40px_rgba(0,0,0,0.22)]">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Summary Text</p>
          <div className="mt-5 space-y-5">
            <NarrativeBlock title="What Happened" text={report.summary.overview} prominent />
            <NarrativeBlock title="Key Findings" text={report.summary.keyFindings} />
            <NarrativeBlock title="Operational Notes" text={report.summary.operationalNotes} />
          </div>
        </article>

        <div className="grid gap-4">
          <article className="rounded-2xl border border-white/6 bg-[#141518] p-5 shadow-[0_16px_40px_rgba(0,0,0,0.22)]">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Run Context</p>
            <div className="mt-4 grid gap-3">
              {report.metadata.map((item) => (
                <CompactDetail key={item.label} label={item.label} value={item.value} detail={item.detail} />
              ))}
            </div>
          </article>

          <article className="rounded-2xl border border-white/6 bg-[#141518] p-5 shadow-[0_16px_40px_rgba(0,0,0,0.22)]">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Critical Moment</p>
            <div className="mt-4 space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${peakLevelStyle.badge}`}>
                  {capitalize(report.peakEvent.frame.danger_reasoning.level)} Risk
                </span>
                <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-medium text-zinc-300">
                  {report.peakEvent.timestamp}
                </span>
              </div>

              <div>
                <h2 className="text-lg font-semibold text-white">
                  {report.peakEvent.frame.danger_reasoning.primary_reason}
                </h2>
                <p className="mt-2 text-sm leading-6 text-zinc-400">{report.peakEvent.frame.summary}</p>
              </div>

              <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Suggested Action</p>
                <p className="mt-2 text-base font-semibold text-white">{report.peakEvent.action}</p>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <article className="rounded-2xl border border-white/6 bg-[#141518] p-5 shadow-[0_16px_40px_rgba(0,0,0,0.22)]">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Supporting Data</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {report.kpis.slice(0, 4).map((metric) => (
              <CompactDetail key={metric.label} label={metric.label} value={metric.value} detail={metric.detail} />
            ))}
          </div>
        </article>

        <article className="rounded-2xl border border-dashed border-white/10 bg-[#111216] p-5 shadow-[0_16px_40px_rgba(0,0,0,0.18)]">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Later Additions</p>
          <div className="mt-4 space-y-3">
            <PlaceholderRow title="Charts and plots" text="Add Plotly charts here once you want calculated trends and visual breakdowns." />
            <PlaceholderRow title="Calculated stats" text="Keep derived metrics light for now, then expand once the report logic is final." />
            <PlaceholderRow title="LLM summary" text="This area can later hold longer generated text, recommendations, or report exports." />
          </div>
        </article>
      </section>
    </div>
  )
}

function NarrativeBlock({ title, text, prominent = false }: { title: string; text: string; prominent?: boolean }) {
  return (
    <div className={`rounded-2xl border p-5 ${prominent ? 'border-white/10 bg-white/[0.04]' : 'border-white/6 bg-white/[0.02]'}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">{title}</p>
      <p className={`mt-3 text-zinc-300 ${prominent ? 'text-base leading-8' : 'text-sm leading-7'}`}>{text}</p>
    </div>
  )
}

function CompactDetail({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-white/6 bg-white/[0.02] p-4">
      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-zinc-500">{label}</p>
      <p className="mt-2 text-base font-semibold text-zinc-100">{value}</p>
      <p className="mt-1 text-sm text-zinc-500">{detail}</p>
    </div>
  )
}

function PlaceholderRow({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
      <p className="text-sm font-semibold text-zinc-200">{title}</p>
      <p className="mt-1 text-sm leading-6 text-zinc-400">{text}</p>
    </div>
  )
}
