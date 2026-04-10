import { Pause, Play } from 'lucide-react'

import {
  capitalize,
  formatSeconds,
  getAnnotationTheme,
  humanizeAction,
  levelTheme,
} from '../data'
import type { VisionFrame, VisionRun } from '../data'

type HeroPanelProps = {
  currentFrame: VisionFrame
  currentFrameIndex: number
  totalFrames: number
  isPlaying: boolean
  onTogglePlayback: () => void
  onTimelineChange: (index: number) => void
  visionRun: VisionRun
}

export function HeroPanel({
  currentFrame,
  currentFrameIndex,
  totalFrames,
  isPlaying,
  onTogglePlayback,
  onTimelineChange,
  visionRun,
}: HeroPanelProps) {
  const levelStyle = levelTheme[currentFrame.danger_reasoning.level]

  return (
    <section className="overflow-hidden rounded-3xl border border-[#2a2d2f] bg-[#1f241d] shadow-[0_24px_60px_rgba(0,0,0,0.35)]">
      <div className="relative aspect-video overflow-hidden border-b border-white/5">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(80,96,61,0.22),transparent_48%),linear-gradient(180deg,#232a22_0%,#1d231c_45%,#1a2118_46%,#181e17_100%)]" />
        <div className="absolute inset-x-0 top-[34%] h-px bg-white/4" />
        <div className="absolute inset-x-0 bottom-[26%] h-px bg-white/5" />
        <div className="absolute inset-x-0 bottom-0 h-24 bg-[linear-gradient(180deg,rgba(70,79,53,0),rgba(58,67,44,0.48))]" />
        <div className="absolute left-4 top-4 z-10 flex flex-wrap gap-2">
          <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${levelStyle.badge}`}>
            {capitalize(currentFrame.danger_reasoning.level)} Risk
          </span>
          <span className="rounded-full border border-white/10 bg-black/30 px-3 py-1 text-xs font-medium text-zinc-100 backdrop-blur-sm">
            {humanizeAction(currentFrame.steering.recommended_action)}
          </span>
        </div>

        {currentFrame.annotations.map((annotation) => {
          const theme = getAnnotationTheme(annotation.label)
          const left = (annotation.bbox.x / visionRun.source.frame_width) * 100
          const top = (annotation.bbox.y / visionRun.source.frame_height) * 100
          const width = (annotation.bbox.width / visionRun.source.frame_width) * 100
          const height = (annotation.bbox.height / visionRun.source.frame_height) * 100

          return (
            <div
              key={annotation.id}
              className={`absolute rounded-[2px] border-2 ${theme.box}`}
              style={{
                left: `${left}%`,
                top: `${top}%`,
                width: `${width}%`,
                height: `${height}%`,
              }}
            >
              <div
                className={`absolute -top-5 left-0 rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${theme.badge}`}
              >
                {annotation.text_label}
              </div>
            </div>
          )
        })}

        {currentFrame.annotations.length === 0 ? (
          <div className="absolute bottom-4 left-4 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100 backdrop-blur-sm">
            No hazards detected in this frame.
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm text-zinc-300">
        <button
          type="button"
          onClick={onTogglePlayback}
          className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/6 text-white transition hover:border-white/20 hover:bg-white/10"
          aria-label={isPlaying ? 'Pause playback' : 'Play playback'}
        >
          {isPlaying ? <Pause className="h-4 w-4 fill-current" /> : <Play className="ml-0.5 h-4 w-4 fill-current" />}
        </button>
        <span className="rounded-full border border-white/8 bg-white/[0.04] px-3 py-1 text-xs font-medium uppercase tracking-[0.16em] text-zinc-300">
          {isPlaying ? 'Playing' : currentFrameIndex === totalFrames - 1 ? 'Ended' : 'Paused'}
        </span>

        <input
          type="range"
          min={0}
          max={Math.max(totalFrames - 1, 0)}
          step={1}
          value={currentFrameIndex}
          onChange={(event) => onTimelineChange(Number(event.target.value))}
          className="h-1.5 min-w-[240px] flex-1 cursor-pointer appearance-none rounded-full bg-white/10 accent-zinc-100"
          aria-label="Frame timeline"
        />

        <div className="ml-auto flex items-center gap-2 font-mono text-xs text-zinc-400">
          <span className="rounded-full border border-white/8 bg-white/[0.04] px-2.5 py-1">
            {formatSeconds(currentFrame.timestamp_ms)}
          </span>
          <span className="rounded-full border border-white/8 bg-white/[0.04] px-2.5 py-1">
            {currentFrameIndex + 1} / {totalFrames}
          </span>
        </div>
      </div>
    </section>
  )
}
