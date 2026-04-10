import { useEffect, useMemo, useState } from 'react'

import { DashboardHeader } from './components/DashboardHeader'
import { ChatPanel } from './components/ChatPanel'
import { DashboardInsights } from './components/DashboardInsights'
import { HeroPanel } from './components/HeroPanel'
import { ReportPage } from '../report/page'
import { UploadPage } from '../upload/page'
import { getAnnotationTheme, visionRun } from './data'

function DashboardPage() {
  const [activeView, setActiveView] = useState<'upload' | 'dashboard' | 'report'>('upload')
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)

  const totalFrames = visionRun.frames.length
  const currentFrame = visionRun.frames[currentFrameIndex] ?? visionRun.frames[0]

  useEffect(() => {
    if (!isPlaying) {
      return
    }

    if (currentFrameIndex >= totalFrames - 1) {
      return
    }

    const frameDurationMs = 1000 / Math.max(visionRun.source.sampling_rate_fps, 1)
    const timer = window.setTimeout(() => {
      setCurrentFrameIndex((index) => {
        if (index >= totalFrames - 1) {
          setIsPlaying(false)
          return index
        }

        if (index >= totalFrames - 2) {
          setIsPlaying(false)
        }

        return index + 1
      })
    }, frameDurationMs)

    return () => window.clearTimeout(timer)
  }, [currentFrameIndex, isPlaying, totalFrames])

  const detectionBadges = useMemo(() => {
    return currentFrame.annotations.map((annotation) => ({
      ...annotation,
      color: getAnnotationTheme(annotation.label),
    }))
  }, [currentFrame.annotations])

  return (
    <main className="min-h-screen bg-[#1a1a1f] text-zinc-50">
      <DashboardHeader activeView={activeView} onSelectView={setActiveView} />

      {activeView === 'upload' ? (
        <UploadPage />
      ) : activeView === 'dashboard' ? (
        <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 px-6 py-5">
          <section className="px-1">
            <h1 className="text-[1.9rem] font-semibold tracking-tight text-white">Dashboard</h1>
          </section>

          <section className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
            <div className="grid gap-4">
              <HeroPanel
                currentFrame={currentFrame}
                currentFrameIndex={currentFrameIndex}
                totalFrames={totalFrames}
                isPlaying={isPlaying}
                onTogglePlayback={() => {
                  if (currentFrameIndex === totalFrames - 1 && !isPlaying) {
                    setCurrentFrameIndex(0)
                  }
                  setIsPlaying((playing) => !playing)
                }}
                onTimelineChange={(index) => {
                  setIsPlaying(false)
                  setCurrentFrameIndex(index)
                }}
                visionRun={visionRun}
              />

              <DashboardInsights currentFrame={currentFrame} detectionBadges={detectionBadges} />
            </div>

            <ChatPanel currentFrame={currentFrame} detectionBadges={detectionBadges} />
          </section>
        </div>
      ) : (
        <ReportPage run={visionRun} />
      )}
    </main>
  )
}

export default DashboardPage
