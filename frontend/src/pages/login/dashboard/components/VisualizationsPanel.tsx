import type { ReactNode } from 'react'

import type { MockVisualDataResponse } from '../../../../data/requests'
import { APFFieldPlot } from './APFFieldPlot'
import { SGGGraphPlot } from './SGGGraphPlot'

type VisualizationsPanelProps = {
  visualData: MockVisualDataResponse | null
  visualDataError: string | null
  isVisualDataLoading: boolean
}

function VisualizationCard({
  title,
  description,
  badge,
  accent,
  children,
}: {
  title: string
  description: string
  badge: string
  accent: 'moss' | 'steel' | 'amber' | 'red'
  children: ReactNode
}) {
  const accentStyles = {
    moss: {
      halo: 'from-[#7c8f54]/20 via-transparent to-transparent',
      bar: 'bg-[#8da85a]',
      badge: 'border-[#8da85a]/25 bg-[#8da85a]/10 text-[#d9e6b8]',
    },
    steel: {
      halo: 'from-[#5a7d90]/20 via-transparent to-transparent',
      bar: 'bg-[#7aa8ba]',
      badge: 'border-[#7aa8ba]/25 bg-[#7aa8ba]/10 text-[#d5e8f0]',
    },
    amber: {
      halo: 'from-[#b98a4a]/20 via-transparent to-transparent',
      bar: 'bg-[#d6a25c]',
      badge: 'border-[#d6a25c]/25 bg-[#d6a25c]/10 text-[#f3deb7]',
    },
    red: {
      halo: 'from-[#b95c5c]/20 via-transparent to-transparent',
      bar: 'bg-[#d77272]',
      badge: 'border-[#d77272]/25 bg-[#d77272]/10 text-[#f3c8c8]',
    },
  }[accent]

  return (
    <article className="relative flex min-h-0 flex-col overflow-hidden rounded-[1.45rem] border border-white/8 bg-[#141518] p-3.5 shadow-[0_22px_60px_rgba(0,0,0,0.28)] xl:p-4">
      <div className={`pointer-events-none absolute inset-0 bg-[linear-gradient(160deg,rgba(255,255,255,0.03),transparent_38%)]`} />
      <div className={`pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-r ${accentStyles.halo}`} />

      <div className="relative mb-2.5 flex items-start justify-between gap-3 xl:mb-3">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <span className={`h-2.5 w-2.5 rounded-full ${accentStyles.bar}`} />
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-zinc-500">{title}</p>
          </div>
          <p className="mt-1 max-w-3xl text-[12px] leading-[1.125rem] text-zinc-400 xl:mt-1.5 xl:text-[13px] xl:leading-5">{description}</p>
        </div>
        <span className={`shrink-0 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${accentStyles.badge}`}>
          {badge}
        </span>
      </div>

      <div className="relative min-h-0 flex-1">{children}</div>
    </article>
  )
}

export function VisualizationsPanel({
  visualData,
  visualDataError,
  isVisualDataLoading,
}: VisualizationsPanelProps) {
  if (isVisualDataLoading) {
    return (
      <VisualizationCard
        title="Interactive Visualizations"
        description="Loading the SGG and APF Plotly data from the backend."
        badge="Loading"
        accent="amber"
      >
        <div className="min-h-[260px] overflow-hidden rounded-2xl border border-white/8 bg-[linear-gradient(135deg,#1c211c_0%,#171a19_50%,#111314_100%)] p-4">
          <div className="h-full animate-pulse">
            <div className="h-4 w-32 rounded-full bg-[#756b4b]/35" />
            <div className="mt-3 h-3 w-72 max-w-full rounded-full bg-white/8" />
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <div className="h-18 rounded-2xl bg-white/6" />
              <div className="h-18 rounded-2xl bg-white/6" />
              <div className="h-18 rounded-2xl bg-white/6" />
            </div>
            <div className="mt-4 h-[150px] rounded-[1.4rem] border border-white/8 bg-[radial-gradient(circle_at_top,rgba(125,135,92,0.16),transparent_42%),linear-gradient(180deg,rgba(255,255,255,0.03),rgba(255,255,255,0.01))]" />
            <p className="mt-4 text-sm text-zinc-400">Preparing scene graph and force-field plots.</p>
          </div>
        </div>
      </VisualizationCard>
    )
  }

  if (visualDataError) {
    return (
      <VisualizationCard
        title="Interactive Visualizations"
        description="The dashboard could not load the backend visualization payload."
        badge="Error"
        accent="red"
      >
        <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-red-400/20 bg-[linear-gradient(180deg,rgba(127,29,29,0.16),rgba(69,10,10,0.1))] px-6 text-center text-sm text-red-100">
          {visualDataError}
        </div>
      </VisualizationCard>
    )
  }

  if (!visualData) {
    return (
      <VisualizationCard
        title="Interactive Visualizations"
        description="SGG and APF charts appear only after backend processing finishes for the uploaded run."
        badge="Waiting"
        accent="amber"
      >
        <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-white/8 bg-[linear-gradient(180deg,rgba(36,42,33,0.88),rgba(20,24,24,0.92))] px-6 text-center text-sm text-zinc-300">
          Upload frames and wait for the backend pipeline to produce real SGG and APF data.
        </div>
      </VisualizationCard>
    )
  }

  const sggSignature = [
    visualData.sggVisualData.nodes.length,
    visualData.sggVisualData.edges.length,
    visualData.sggVisualData.nodes.map((node) => `${node.id}:${node.x}:${node.y}`).join('|'),
  ].join('::')

  const apfSignature = [
    visualData.apfVisualData.entities.length,
    visualData.apfVisualData.control_steer_x,
    visualData.apfVisualData.control_steer_y,
    visualData.apfVisualData.entities.map((entity) => `${entity.id}:${entity.x}:${entity.y}`).join('|'),
  ].join('::')

  return (
    <section className="grid min-h-0 gap-3 md:grid-cols-2">
      <VisualizationCard
        title="SGG Graph"
        description="Top-down scene graph replicated from the original Python view."
        badge="2D Scene"
        accent="moss"
      >
        <div className="h-[250px] overflow-hidden rounded-[1.35rem] border border-[#d8d2c0]/75 bg-[radial-gradient(circle_at_top,rgba(168,181,126,0.16),transparent_40%),linear-gradient(180deg,#f6f2e7_0%,#f2ede0_100%)] p-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.45)] lg:h-[260px] xl:h-[300px] 2xl:h-[380px]">
          <SGGGraphPlot key={sggSignature} data={visualData.sggVisualData} />
        </div>
      </VisualizationCard>

      <VisualizationCard
        title="APF Field"
        description="3D force-field surface, entities, steering vector, and corridor from the backend JSON."
        badge="3D Field"
        accent="steel"
      >
        <div className="h-[250px] overflow-hidden rounded-[1.35rem] border border-white/8 bg-[radial-gradient(circle_at_top,rgba(122,168,186,0.18),transparent_34%),linear-gradient(180deg,#11161a_0%,#0d1013_100%)] p-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] lg:h-[260px] xl:h-[300px] 2xl:h-[380px]">
          <APFFieldPlot key={apfSignature} data={visualData.apfVisualData} />
        </div>
      </VisualizationCard>
    </section>
  )
}
