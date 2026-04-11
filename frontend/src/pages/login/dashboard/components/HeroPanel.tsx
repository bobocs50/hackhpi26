import { AlertCircle, ChevronLeft, ChevronRight, CheckCircle2, LoaderCircle, Pause, Play } from 'lucide-react'

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
  frameImageUrl?: string | null
  hideAnnotations?: boolean
  showMissingUploadNotice?: boolean
  uploadStatus?: 'idle' | 'uploading' | 'uploaded' | 'failed'
  onTogglePlayback: () => void
  onStepBackward: () => void
  onStepForward: () => void
  onTimelineChange: (index: number) => void
  visionRun: VisionRun
}

export function HeroPanel({
  currentFrame,
  currentFrameIndex,
  totalFrames,
  isPlaying,
  frameImageUrl,
  hideAnnotations = false,
  showMissingUploadNotice = false,
  uploadStatus = 'idle',
  onTogglePlayback,
  onStepBackward,
  onStepForward,
  onTimelineChange,
  visionRun,
}: HeroPanelProps) {
  const levelStyle = levelTheme[currentFrame.danger_reasoning.level]
  const uploadBadge =
    uploadStatus === 'uploading'
      ? {
          label: 'Uploading to backend',
          className: 'border-amber-500/25 bg-amber-500/10 text-amber-100',
          icon: LoaderCircle,
          iconClassName: 'animate-spin',
        }
      : uploadStatus === 'uploaded'
        ? {
            label: 'Synced to backend',
            className: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-100',
            icon: CheckCircle2,
            iconClassName: '',
          }
        : uploadStatus === 'failed'
          ? {
              label: 'Backend upload failed',
              className: 'border-red-500/25 bg-red-500/10 text-red-100',
              icon: AlertCircle,
              iconClassName: '',
            }
          : null
  const UploadBadgeIcon = uploadBadge?.icon

  return (
    <section className="flex min-h-0 flex-col overflow-hidden rounded-3xl border border-[#2a2d2f] bg-[#1f241d] shadow-[0_24px_60px_rgba(0,0,0,0.35)]">
      <div className="relative h-[320px] w-full overflow-hidden border-b border-white/5 lg:h-[340px] xl:h-[350px] 2xl:aspect-video 2xl:h-auto">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(80,96,61,0.22),transparent_48%),linear-gradient(180deg,#232a22_0%,#1d231c_45%,#1a2118_46%,#181e17_100%)]" />
        <div className="absolute inset-x-0 top-[34%] h-px bg-white/4" />
        <div className="absolute inset-x-0 bottom-[26%] h-px bg-white/5" />
        <div className="absolute inset-x-0 bottom-0 h-24 bg-[linear-gradient(180deg,rgba(70,79,53,0),rgba(58,67,44,0.48))]" />
        {frameImageUrl ? (
          <img
            src={frameImageUrl}
            alt={currentFrame.frame_file}
            className="absolute inset-0 h-full w-full object-fill"
          />
        ) : null}
        <div className="absolute left-3 top-3 z-10 flex flex-wrap gap-2">
          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${levelStyle.badge}`}>
            {capitalize(currentFrame.danger_reasoning.level)} Risk
          </span>
          <span className="rounded-full border border-white/10 bg-black/30 px-2.5 py-1 text-[11px] font-medium text-zinc-100 backdrop-blur-sm">
            {humanizeAction(currentFrame.steering.recommended_action)}
          </span>
          {uploadBadge && UploadBadgeIcon ? (
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${uploadBadge.className}`}>
              <UploadBadgeIcon className={`h-3.5 w-3.5 ${uploadBadge.iconClassName}`} />
              {uploadBadge.label}
            </span>
          ) : null}
        </div>

        {!hideAnnotations
          ? currentFrame.annotations.map((annotation) => {
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
            })
          : null}

        {!frameImageUrl && showMissingUploadNotice ? (
          <div className="absolute bottom-3 left-3 rounded-xl border border-white/10 bg-black/25 px-3 py-2 text-sm text-zinc-100 backdrop-blur-sm">
            No uploaded image matched {currentFrame.frame_file}.
          </div>
        ) : null}

        {!hideAnnotations && currentFrame.annotations.length === 0 ? (
          <div className="absolute bottom-3 left-3 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100 backdrop-blur-sm">
            No hazards detected in this frame.
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-2.5 px-3 py-2 text-sm text-zinc-300 xl:py-2.5">
        <button
          type="button"
          onClick={onStepBackward}
          disabled={currentFrameIndex === 0}
          className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/6 text-white transition enabled:hover:border-white/20 enabled:hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Previous frame"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onTogglePlayback}
          className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/6 text-white transition hover:border-white/20 hover:bg-white/10"
          aria-label={isPlaying ? 'Pause playback' : 'Play playback'}
        >
          {isPlaying ? <Pause className="h-4 w-4 fill-current" /> : <Play className="ml-0.5 h-4 w-4 fill-current" />}
        </button>
        <button
          type="button"
          onClick={onStepForward}
          disabled={currentFrameIndex >= totalFrames - 1}
          className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/6 text-white transition enabled:hover:border-white/20 enabled:hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Next frame"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
        <span className="rounded-full border border-white/8 bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.16em] text-zinc-300">
          {isPlaying ? 'Playing' : currentFrameIndex === totalFrames - 1 ? 'Ended' : 'Paused'}
        </span>

        <input
          type="range"
          min={0}
          max={Math.max(totalFrames - 1, 0)}
          step={1}
          value={currentFrameIndex}
          onChange={(event) => onTimelineChange(Number(event.target.value))}
          className="h-1.5 min-w-[180px] flex-1 cursor-pointer appearance-none rounded-full bg-white/10 accent-zinc-100"
          aria-label="Frame timeline"
        />

        <div className="ml-auto flex items-center gap-2 font-mono text-[11px] text-zinc-400">
          <span className="rounded-full border border-white/8 bg-white/[0.04] px-2 py-1">
            {formatSeconds(currentFrame.timestamp_ms)}
          </span>
          <span className="rounded-full border border-white/8 bg-white/[0.04] px-2 py-1">
            {currentFrameIndex + 1} / {totalFrames}
          </span>
        </div>
      </div>
    </section>
  )
}
