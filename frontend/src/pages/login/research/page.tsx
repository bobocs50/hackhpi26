import { ChatPanel } from '../dashboard/components/ChatPanel'
import type { DetectionBadge, VisionFrame } from '../dashboard/data'

type ResearchPageProps = {
  currentFrame: VisionFrame
  detectionBadges: DetectionBadge[]
}

export function ResearchPage({ currentFrame, detectionBadges }: ResearchPageProps) {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-6 py-5">
      <section className="mx-auto w-full max-w-[880px] rounded-3xl border border-[#2a2d2f] bg-[linear-gradient(135deg,#1d221d_0%,#17191d_55%,#101114_100%)] px-6 py-6 shadow-[0_24px_60px_rgba(0,0,0,0.35)]">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Workspace</p>
        <h1 className="mt-2 text-[1.9rem] font-semibold tracking-tight text-white">Research Assistant</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
          Ask for a quick read on the current frame, hazards, steering choice, or recommended action
          without giving up dashboard space.
        </p>
      </section>

      <section className="mx-auto w-full max-w-[880px]">
        <ChatPanel currentFrame={currentFrame} detectionBadges={detectionBadges} />
      </section>
    </div>
  )
}
