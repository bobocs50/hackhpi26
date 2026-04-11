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
import { getMockVisualData, uploadFrameFolder } from '../../../data/requests'
import type { MockVisualDataResponse } from '../../../data/requests'
import visualDataFixture from '../../../../../backend/data/visual_data_fixture.json'

const SUPPORTED_IMAGE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'webp'])
const EMPTY_UPLOAD_STATE: UploadSessionState = {
  folderName: null,
  totalFiles: 0,
  matchedFrames: 0,
  unmatchedFiles: 0,
  status: 'idle',
  runId: null,
  error: null,
}
const INITIAL_VISUAL_DATA = visualDataFixture as unknown as MockVisualDataResponse

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

function DashboardPage() {
  const [activeView, setActiveView] = useState<'upload' | 'dashboard' | 'research' | 'report'>('upload')
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [uploadedFrameUrls, setUploadedFrameUrls] = useState<Record<string, string>>({})
  const [uploadedFrameSequence, setUploadedFrameSequence] = useState<UploadedFramePreview[]>([])
  const [uploadState, setUploadState] = useState<UploadSessionState>(EMPTY_UPLOAD_STATE)
  const [visualData, setVisualData] = useState<MockVisualDataResponse | null>(INITIAL_VISUAL_DATA)
  const isVisualDataLoading = false
  const [visualDataError, setVisualDataError] = useState<string | null>(null)
  const previewUrlsRef = useRef<Record<string, string>>({})
  const uploadRequestIdRef = useRef(0)

  const frameDurationMs = 1000 / Math.max(visionRun.source.sampling_rate_fps, 1)
  const totalFrames = uploadedFrameSequence.length || visionRun.frames.length
  const baseFrame =
    visionRun.frames[Math.min(currentFrameIndex, Math.max(visionRun.frames.length - 1, 0))] ?? visionRun.frames[0]
  const uploadedFramePreview = uploadedFrameSequence[currentFrameIndex]
  const currentFrame: VisionFrame =
    uploadedFramePreview && baseFrame
      ? {
          ...baseFrame,
          frame_file: uploadedFramePreview.name,
          frame_index: currentFrameIndex,
          timestamp_ms: currentFrameIndex * frameDurationMs,
          annotations: [],
        }
      : baseFrame
  const currentFrameImageUrl =
    (currentFrame ? uploadedFrameUrls[currentFrame.frame_file] : null) ?? uploadedFramePreview?.url ?? null
  const hasPreviewFrames = Object.keys(uploadedFrameUrls).length > 0

  useEffect(() => {
    let isCancelled = false

    async function loadVisualData() {
      try {
        setVisualDataError(null)
        const payload = await getMockVisualData()

        if (!isCancelled) {
          setVisualData(payload)
        }
      } catch (error) {
        if (!isCancelled) {
          const message = error instanceof Error ? error.message : 'Failed to load visual data'
          setVisualDataError(message)
        }
      }
    }

    void loadVisualData()

    return () => {
      isCancelled = true
    }
  }, [])

  useEffect(() => {
    return () => {
      revokePreviewUrls(previewUrlsRef.current)
    }
  }, [])

  useEffect(() => {
    if (!isPlaying) {
      return
    }

    if (currentFrameIndex >= totalFrames - 1) {
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
  }, [currentFrameIndex, isPlaying, totalFrames])

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

    const nextPreviewUrls: Record<string, string> = {}
    const sortedImageFiles = [...imageFiles].sort((left, right) =>
      compareFrameNames(getFrameFileName(left), getFrameFileName(right)),
    )

    imageFiles.forEach((file) => {
      nextPreviewUrls[getFrameFileName(file)] = URL.createObjectURL(file)
    })
    const nextPreviewSequence = sortedImageFiles.map((file) => ({
      name: getFrameFileName(file),
      url: nextPreviewUrls[getFrameFileName(file)],
    }))

    revokePreviewUrls(previewUrlsRef.current)
    previewUrlsRef.current = nextPreviewUrls
    setUploadedFrameUrls(nextPreviewUrls)
    setUploadedFrameSequence(nextPreviewSequence)

    const folderName = getFolderName(imageFiles)
    const filenameMatches = visionRun.frames.filter((frame) => nextPreviewUrls[frame.frame_file]).length
    const matchedFrames =
      filenameMatches > 0 ? filenameMatches : Math.min(sortedImageFiles.length, visionRun.frames.length)
    const nextRequestId = uploadRequestIdRef.current + 1
    uploadRequestIdRef.current = nextRequestId

    setUploadState({
      folderName,
      totalFiles: imageFiles.length,
      matchedFrames,
      unmatchedFiles: Math.max(imageFiles.length - matchedFrames, 0),
      status: 'uploading',
      runId: null,
      error: null,
    })
    setCurrentFrameIndex(0)
    setIsPlaying(false)
    setActiveView('dashboard')

    void uploadFrameFolder(imageFiles, folderName ?? undefined)
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
                currentFrameIndex={currentFrameIndex}
                totalFrames={totalFrames}
                isPlaying={isPlaying}
                frameImageUrl={currentFrameImageUrl}
                uploadStatus={uploadState.status}
                hideAnnotations={hasPreviewFrames}
                showMissingUploadNotice={hasPreviewFrames}
                onTogglePlayback={() => {
                  if (currentFrameIndex === totalFrames - 1 && !isPlaying) {
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
              visualData={visualData}
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
