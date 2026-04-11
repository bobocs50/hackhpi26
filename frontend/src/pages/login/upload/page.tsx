import { useRef } from 'react'
import { CheckCircle2, FolderOpen, LoaderCircle, TriangleAlert, Upload } from 'lucide-react'

export type UploadStatus = 'idle' | 'uploading' | 'uploaded' | 'failed'

export type UploadSessionState = {
  folderName: string | null
  totalFiles: number
  matchedFrames: number
  unmatchedFiles: number
  status: UploadStatus
  runId: string | null
  error: string | null
}

type UploadPageProps = {
  uploadState: UploadSessionState
  hasPreviewFrames: boolean
  onSelectFolder: (files: FileList | null) => void
  onOpenDashboard: () => void
}

const directoryInputProps = {
  directory: '',
  webkitdirectory: '',
} as const

export function UploadPage({
  uploadState,
  hasPreviewFrames,
  onSelectFolder,
  onOpenDashboard,
}: UploadPageProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const statusText = uploadState.error
    ? uploadState.error
    : hasPreviewFrames
      ? `${uploadState.matchedFrames} frame(s) ready in dashboard${uploadState.runId ? `, backend run ${uploadState.runId}` : ', backend upload running'}.`
      : 'Choose a folder with frame images. Matching now falls back to frame order if names differ.'

  return (
    <div className="mx-auto flex min-h-[calc(100vh-73px)] w-full max-w-5xl items-center px-6 py-8">
      <section className="w-full rounded-3xl border border-dashed border-[#4a5447] bg-[linear-gradient(180deg,#171a1c_0%,#111315_100%)] p-6 shadow-[0_24px_60px_rgba(0,0,0,0.3)] sm:p-8">
        <div className="flex min-h-[360px] flex-col items-center justify-center rounded-[1.75rem] border border-dashed border-white/10 bg-[radial-gradient(circle_at_top,rgba(196,255,140,0.08),transparent_45%),rgba(255,255,255,0.015)] px-6 py-8 text-center">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-500">Upload</p>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Drop a folder with frames
          </h1>

          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(event) => {
              onSelectFolder(event.target.files)
              event.target.value = ''
            }}
            {...directoryInputProps}
          />

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="inline-flex items-center gap-2 rounded-2xl border border-[#708456]/30 bg-[#242c20] px-5 py-3 text-sm font-semibold text-white shadow-[0_16px_40px_rgba(0,0,0,0.18)] transition hover:border-[#8da85a]/45 hover:bg-[#2b3426]"
            >
              <FolderOpen className="h-4 w-4" />
              Select frame folder
            </button>

            {hasPreviewFrames ? (
              <button
                type="button"
                onClick={onOpenDashboard}
                className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-semibold text-zinc-100 transition hover:bg-white/[0.08]"
              >
                <Upload className="h-4 w-4" />
                Open dashboard
              </button>
            ) : null}
          </div>

          <div className="mt-6 flex items-center gap-2 text-sm text-zinc-400">
            {uploadState.status === 'uploading' ? (
              <LoaderCircle className="h-4 w-4 animate-spin text-amber-300" />
            ) : uploadState.status === 'uploaded' ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-300" />
            ) : uploadState.status === 'failed' ? (
              <TriangleAlert className="h-4 w-4 text-red-300" />
            ) : (
              <FolderOpen className="h-4 w-4 text-zinc-500" />
            )}
            <p>{statusText}</p>
          </div>
        </div>
      </section>
    </div>
  )
}
