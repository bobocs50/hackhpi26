import { useEffect, useState } from 'react'

import type { RunReportResponse } from '../../../data/requests'
import { getRunReport } from '../../../data/requests'

export function ReportPage() {
  const [report, setReport] = useState<RunReportResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isCancelled = false

    async function loadReport() {
      try {
        setIsLoading(true)
        setError(null)
        const payload = await getRunReport()

        if (!isCancelled) {
          setReport(payload)
        }
      } catch (loadError) {
        if (!isCancelled) {
          const message = loadError instanceof Error ? loadError.message : 'Failed to load report'
          setError(message)
          setReport(null)
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false)
        }
      }
    }

    void loadReport()

    return () => {
      isCancelled = true
    }
  }, [])

  if (isLoading) {
    return (
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-6 py-5">
        <section className="rounded-3xl border border-[#2a2d2f] bg-[linear-gradient(135deg,#1d221d_0%,#17191d_55%,#101114_100%)] px-6 py-7 shadow-[0_24px_60px_rgba(0,0,0,0.35)]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-500">Run Report</p>
          <h1 className="mt-3 text-[2rem] font-semibold tracking-tight text-white">Generating report</h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-zinc-300">
            Loading the backend report for this run.
          </p>
        </section>
      </div>
    )
  }

  if (error) {
    return (
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-6 py-5">
        <section className="rounded-3xl border border-[#2a2d2f] bg-[linear-gradient(135deg,#1d221d_0%,#17191d_55%,#101114_100%)] px-6 py-6 shadow-[0_24px_60px_rgba(0,0,0,0.35)]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-500">Run Report</p>
          <h1 className="mt-3 text-[2rem] font-semibold tracking-tight text-white">No report data available</h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-zinc-300">{error}</p>
        </section>
      </div>
    )
  }

  if (!report) {
    return null
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-6 py-5">
      <section className="rounded-3xl border border-[#2a2d2f] bg-[linear-gradient(135deg,#1d221d_0%,#17191d_55%,#101114_100%)] px-6 py-7 shadow-[0_24px_60px_rgba(0,0,0,0.35)]">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-500">Run Report</p>
          <h1 className="mt-3 max-w-4xl text-[2.3rem] font-semibold tracking-tight text-white">
            {report.headline}
          </h1>
          <div className="mt-6 rounded-[1.75rem] border border-white/8 bg-[linear-gradient(180deg,rgba(255,255,255,0.045),rgba(255,255,255,0.025))] p-7 sm:p-9">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Summary</p>
            <div className="mt-5 max-w-4xl text-base leading-8 text-zinc-100 sm:text-[1.02rem]">
              <p>{report.body}</p>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap gap-2">
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-zinc-200">
              {report.fallback_used ? 'Fallback Report' : 'Claude Report'}
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
