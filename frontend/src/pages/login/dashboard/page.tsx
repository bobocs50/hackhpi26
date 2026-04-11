import { useEffect, useMemo, useRef, useState } from 'react'

import { DashboardHeader } from './components/DashboardHeader'
import { DashboardInsights } from './components/DashboardInsights'
import { HeroPanel } from './components/HeroPanel'
import { VisualizationsPanel } from './components/VisualizationsPanel'
import { ResearchPage } from '../research/page'
import { ReportPage } from '../report/page'
import { UploadPage, type UploadSessionState } from '../upload/page'
import { getAnnotationTheme, visionRun } from './data'
import type { VisionFrame } from './data'
import {
  getRunFrames,
  getRunVisualData,
  uploadFrameFolder,
} from '../../../data/requests'
import type {
  MockVisualDataResponse,
  UploadedRunFrameData,
  UploadedRunVisualDataResponse,
} from '../../../data/requests'

const SUPPORTED_IMAGE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'webp'])
const DASHBOARD_FRAME_LIMIT = 20
const EMPTY_UPLOAD_STATE: UploadSessionState = {
  folderName: null,
  totalFiles: 0,
  matchedFrames: 0,
  unmatchedFiles: 0,
  status: 'idle',
  runId: null,
  error: null,
}

function revokePreviewUrls(previewUrls: Record<string, string>) {
  Object.values(previewUrls).forEach((url) => URL.revokeObjectURL(url))
}

function compareFrameNames(left: string, right: string) {
  return left.localeCompare(right, undefined, {
    numeric: true,
    sensitivity: 'base',
  })
}

type UploadedFramePreview = {
  name: string
  url: string
}

function getFrameFileName(file: File) {
  const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath ?? ''
  const sourceName = relativePath || file.name
  return sourceName.split('/').at(-1) ?? file.name
}

function getFolderName(files: File[]) {
  const relativePath = (files[0] as File & { webkitRelativePath?: string } | undefined)?.webkitRelativePath

  if (relativePath) {
    return relativePath.split('/')[0] ?? null
  }

  return null
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function toDegrees(radians: number) {
  return (radians * 180) / Math.PI
}

function deriveDangerLevel(frame: UploadedRunFrameData): 'low' | 'medium' | 'high' {
  const topDangerClass = frame.dangerZone.topEntity?.dangerClass

  if (topDangerClass === 'must_avoid') {
    return 'high'
  }

  if (topDangerClass === 'target') {
    return 'medium'
  }

  return 'low'
}

function deriveRecommendedAction(frame: UploadedRunFrameData) {
  const steerDeg = toDegrees(frame.steering.deltaTheta)
  const speedRatio = frame.velocity.egoV > 0 ? frame.velocity.vTarget / frame.velocity.egoV : 1

  if (speedRatio < 0.2) {
    return steerDeg >= 3 ? 'brake_and_steer_right' : steerDeg <= -3 ? 'brake_and_steer_left' : 'brake'
  }

  if (speedRatio < 0.75) {
    return steerDeg >= 3 ? 'slow_forward_with_right_bias' : steerDeg <= -3 ? 'slow_forward_with_left_bias' : 'slow_forward'
  }

  return steerDeg >= 3 ? 'resume_forward_right_bias' : steerDeg <= -3 ? 'resume_forward_left_bias' : 'resume_forward'
}

function buildBackendCurrentFrame(baseFrame: VisionFrame, backendFrame: UploadedRunFrameData): VisionFrame {
  const topEntity = backendFrame.dangerZone.topEntity
  const score = topEntity?.dangerQuality ?? 0
  const steerDeg = toDegrees(backendFrame.steering.deltaTheta)
  const speedFactor = backendFrame.velocity.egoV > 0 ? clamp(backendFrame.velocity.vTarget / backendFrame.velocity.egoV, 0, 1) : 1

  return {
    ...baseFrame,
    frame_file: backendFrame.frameFile,
    frame_index: backendFrame.frameIndex,
    timestamp_ms: backendFrame.timestampMs,
    annotations: [],
    steering: {
      recommended_action: deriveRecommendedAction(backendFrame),
      steering_angle_deg: steerDeg,
      speed_factor: speedFactor,
      brake_factor: clamp(1 - speedFactor, 0, 1),
      vectors: {
        heading_vector: { x: 0, y: 1 },
        avoidance_vector: {
          x: backendFrame.steering.controlSteerX,
          y: backendFrame.steering.controlSteerY,
        },
        safe_corridor_vector: { x: 0, y: 1 },
      },
      vector_reasoning: [backendFrame.reasoning.summary],
    },
    danger_reasoning: {
      level: deriveDangerLevel(backendFrame),
      score,
      primary_reason: backendFrame.reasoning.summary,
      secondary_reason: topEntity
        ? `${topEntity.cls} classified as ${topEntity.dangerClass.replaceAll('_', ' ')}.`
        : 'No tracked hazard in this frame.',
    },
    uncertainty: {
      overall: 0,
      notes: ['Backend uploaded-run data is driving this frame.'],
    },
    summary: backendFrame.reasoning.summary,
  }
}

function DashboardPage() {
  const [activeView, setActiveView] = useState<'upload' | 'dashboard' | 'research' | 'report'>('upload')
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [uploadedFrameUrls, setUploadedFrameUrls] = useState<Record<string, string>>({})
  const [uploadedFrameSequence, setUploadedFrameSequence] = useState<UploadedFramePreview[]>([])
  const [uploadState, setUploadState] = useState<UploadSessionState>(EMPTY_UPLOAD_STATE)
  const [visualData] = useState<MockVisualDataResponse | null>(null)
  const [uploadedRunData, setUploadedRunData] = useState<UploadedRunVisualDataResponse | null>(null)
  const [isVisualDataLoading, setIsVisualDataLoading] = useState(false)
  const [visualDataError, setVisualDataError] = useState<string | null>(null)
  const previewUrlsRef = useRef<Record<string, string>>({})
  const uploadRequestIdRef = useRef(0)

  const backendFrameCount = uploadedRunData?.frames.length ?? 0
  const totalFrames = backendFrameCount || uploadedFrameSequence.length || visionRun.frames.length
  const activeSamplingFps = uploadedRunData?.sourceFrames.samplingFps ?? visionRun.source.sampling_rate_fps
  const frameDurationMs = 1000 / Math.max(activeSamplingFps, 1)
  const safeFrameIndex = Math.min(currentFrameIndex, Math.max(totalFrames - 1, 0))
  const baseFrame =
    visionRun.frames[Math.min(safeFrameIndex, Math.max(visionRun.frames.length - 1, 0))] ?? visionRun.frames[0]
  const backendFrame = uploadedRunData?.frames[safeFrameIndex] ?? null
  const uploadedFramePreview = uploadedFrameSequence[safeFrameIndex]
  const currentFrame: VisionFrame =
    backendFrame && baseFrame
      ? buildBackendCurrentFrame(baseFrame, backendFrame)
      : uploadedFramePreview && baseFrame
        ? {
            ...baseFrame,
            frame_file: uploadedFramePreview.name,
            frame_index: safeFrameIndex,
            timestamp_ms: safeFrameIndex * frameDurationMs,
            annotations: [],
          }
        : baseFrame
  const currentFrameImageUrl =
    (currentFrame ? uploadedFrameUrls[currentFrame.frame_file] : null) ?? uploadedFramePreview?.url ?? null
  const hasPreviewFrames = Object.keys(uploadedFrameUrls).length > 0
  const selectedVisualData = backendFrame
    ? {
        sggVisualData: backendFrame.sggVisualData,
        apfVisualData: backendFrame.apfVisualData,
      }
    : visualData


  useEffect(() => {
    return () => {
      revokePreviewUrls(previewUrlsRef.current)
    }
  }, [])

  useEffect(() => {
    if (!isPlaying) {
      return
    }

    if (safeFrameIndex >= totalFrames - 1) {
      return
    }

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
  }, [frameDurationMs, isPlaying, safeFrameIndex, totalFrames])

  useEffect(() => {
    if (currentFrameIndex <= Math.max(totalFrames - 1, 0)) {
      return
    }

    setCurrentFrameIndex(Math.max(totalFrames - 1, 0))
  }, [currentFrameIndex, totalFrames])

  useEffect(() => {
    if (!uploadState.runId || uploadState.status === 'failed') {
      return
    }

    let isCancelled = false
    let timer: number | null = null

    async function pollRunStatus() {
      try {
        const status = await getRunFrames(uploadState.runId as string)

        if (isCancelled) {
          return
        }

        if (status.status === 'failed') {
          setUploadState((previousState) => ({
            ...previousState,
            status: 'failed',
            error: status.tracker_error ?? 'Backend processing failed.',
          }))
          setIsVisualDataLoading(false)
          return
        }

        if (status.final_output_ready && status.status === 'completed') {
          setIsVisualDataLoading(true)
          const payload = await getRunVisualData(uploadState.runId as string)

          if (isCancelled) {
            return
          }

          setUploadedRunData(payload)
          setUploadState((previousState) => ({
            ...previousState,
            status: 'uploaded',
            error: null,
          }))
          setVisualDataError(null)
          setIsVisualDataLoading(false)
          return
        }

        setIsVisualDataLoading(true)
        timer = window.setTimeout(() => {
          void pollRunStatus()
        }, 1200)
      } catch (error) {
        if (isCancelled) {
          return
        }

        setVisualDataError(error instanceof Error ? error.message : 'Failed to poll backend run status.')
        timer = window.setTimeout(() => {
          void pollRunStatus()
        }, 2000)
      }
    }

    void pollRunStatus()

    return () => {
      isCancelled = true
      if (timer !== null) {
        window.clearTimeout(timer)
      }
    }
  }, [uploadState.runId, uploadState.status])

  const detectionBadges = useMemo(() => {
    return currentFrame.annotations.map((annotation) => ({
      ...annotation,
      color: getAnnotationTheme(annotation.label),
    }))
  }, [currentFrame.annotations])

  function handleFrameFolderSelection(fileList: FileList | null) {
    if (!fileList) {
      return
    }

    const imageFiles = Array.from(fileList).filter((file) => {
      const extension = file.name.split('.').at(-1)?.toLowerCase() ?? ''
      return SUPPORTED_IMAGE_EXTENSIONS.has(extension)
    })

    if (imageFiles.length === 0) {
      setUploadState({
        ...EMPTY_UPLOAD_STATE,
        status: 'failed',
        error: 'No supported image files were found in that folder.',
      })
      return
    }

    const sortedImageFiles = [...imageFiles].sort((left, right) =>
      compareFrameNames(getFrameFileName(left), getFrameFileName(right)),
    )
    const limitedImageFiles = sortedImageFiles.slice(0, DASHBOARD_FRAME_LIMIT)
    const nextPreviewUrls: Record<string, string> = {}

    limitedImageFiles.forEach((file) => {
      nextPreviewUrls[getFrameFileName(file)] = URL.createObjectURL(file)
    })
    const nextPreviewSequence = limitedImageFiles.map((file) => ({
      name: getFrameFileName(file),
      url: nextPreviewUrls[getFrameFileName(file)],
    }))

    revokePreviewUrls(previewUrlsRef.current)
    previewUrlsRef.current = nextPreviewUrls
    setUploadedFrameUrls(nextPreviewUrls)
    setUploadedFrameSequence(nextPreviewSequence)
    setUploadedRunData(null)
    setVisualDataError(null)
    setIsVisualDataLoading(true)

    const folderName = getFolderName(imageFiles)
    const filenameMatches = visionRun.frames.filter((frame) => nextPreviewUrls[frame.frame_file]).length
    const matchedFrames =
      filenameMatches > 0 ? filenameMatches : Math.min(limitedImageFiles.length, visionRun.frames.length)
    const nextRequestId = uploadRequestIdRef.current + 1
    uploadRequestIdRef.current = nextRequestId

    setUploadState({
      folderName,
      totalFiles: limitedImageFiles.length,
      matchedFrames,
      unmatchedFiles: 0,
      status: 'uploading',
      runId: null,
      error: null,
    })
    setCurrentFrameIndex(0)
    setIsPlaying(false)
    setActiveView('dashboard')

    void uploadFrameFolder(limitedImageFiles, folderName ?? undefined)
      .then((response) => {
        if (uploadRequestIdRef.current !== nextRequestId) {
          return
        }

        setUploadState((previousState) => ({
          ...previousState,
          status: 'uploaded',
          runId: response.run_id,
          error: null,
        }))
      })
      .catch((error) => {
        if (uploadRequestIdRef.current !== nextRequestId) {
          return
        }

        setUploadState((previousState) => ({
          ...previousState,
          status: 'failed',
          error: error instanceof Error ? error.message : 'Failed to upload frames to the backend.',
        }))
      })
  }

  return (
    <main className="min-h-screen bg-[#1a1a1f] text-zinc-50">
      <DashboardHeader activeView={activeView} onSelectView={setActiveView} />

      {activeView === 'upload' ? (
        <UploadPage
          uploadState={uploadState}
          hasPreviewFrames={hasPreviewFrames}
          onSelectFolder={handleFrameFolderSelection}
          onOpenDashboard={() => setActiveView('dashboard')}
        />
      ) : activeView === 'dashboard' ? (
        <div className="mx-auto flex min-h-[calc(100vh-72px)] w-full max-w-[1500px] flex-col px-5 py-4 xl:px-6">
          <section className="px-1 pb-3">
            <h1 className="text-[1.9rem] font-semibold tracking-tight text-white">Dashboard</h1>
          </section>

          <section className="grid min-h-0 flex-1 gap-3">
            <div className="grid min-h-0 gap-3 xl:grid-cols-[clamp(240px,22vw,285px)_minmax(0,1fr)] 2xl:grid-cols-[300px_minmax(0,1fr)]">
              <DashboardInsights currentFrame={currentFrame} />

              <HeroPanel
                currentFrame={currentFrame}
                currentFrameIndex={safeFrameIndex}
                totalFrames={totalFrames}
                isPlaying={isPlaying}
                frameImageUrl={currentFrameImageUrl}
                uploadStatus={uploadState.status}
                hideAnnotations={hasPreviewFrames}
                showMissingUploadNotice={hasPreviewFrames && !backendFrame}
                onTogglePlayback={() => {
                  if (safeFrameIndex === totalFrames - 1 && !isPlaying) {
                    setCurrentFrameIndex(0)
                  }
                  setIsPlaying((playing) => !playing)
                }}
                onStepBackward={() => {
                  setIsPlaying(false)
                  setCurrentFrameIndex((index) => Math.max(index - 1, 0))
                }}
                onStepForward={() => {
                  setIsPlaying(false)
                  setCurrentFrameIndex((index) => Math.min(index + 1, totalFrames - 1))
                }}
                onTimelineChange={(index) => {
                  setIsPlaying(false)
                  setCurrentFrameIndex(index)
                }}
                visionRun={visionRun}
              />
            </div>

            <VisualizationsPanel
              visualData={selectedVisualData}
              visualDataError={visualDataError}
              isVisualDataLoading={isVisualDataLoading}
            />
          </section>
        </div>
      ) : activeView === 'research' ? (
        <ResearchPage currentFrame={currentFrame} detectionBadges={detectionBadges} />
      ) : (
        <ReportPage />
      )}
    </main>
  )
}

export default DashboardPage
