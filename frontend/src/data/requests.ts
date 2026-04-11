const BACKEND_URL = 'http://localhost:8000'

export type UploadFramesResponse = {
  run_id: string
  folder_name: string | null
  file_count: number
  status: 'processing'
}

export type RunFramesResponse = {
  run_id: string
  folder_name: string | null
  file_count: number
  status: 'processing' | 'completed' | 'failed'
  pipeline_stage?: string | null
  final_output_ready?: boolean
  final_output_generated_at?: string | null
  created_at: string
  updated_at: string
  tracker_status: 'processing' | 'completed' | 'failed'
  tracker_started_at: string | null
  tracker_finished_at: string | null
  tracker_error: string | null
  frames: string[]
}

export type SGGNode = {
  id: number
  cls: string
  is_ego: boolean
  x: number
  y: number
  vx: number
  vy: number
  danger_quality: number
  smoothed_certainty: number
  ttc_label: string
}

export type SGGEdge = {
  source_x: number
  source_y: number
  target_x: number
  target_y: number
  label: string
  color: string
  reasoning?: string
}

export type SGGDistanceLine = {
  target_x: number
  target_y: number
  distance: number
}

export type SGGVisualData = {
  nodes: SGGNode[]
  edges: SGGEdge[]
  distance_lines: SGGDistanceLine[]
}

export type APFEntity = {
  id: number
  cls: string
  x: number
  y: number
  z: number
  color: string
  danger_quality: number
  smoothed_certainty: number
  ttc_label: string
  danger_class: string
}

export type APFVisualData = {
  x_grid: Array<number | string>
  y_grid: Array<number | string>
  z_surface: Array<Array<number | string>>
  ego_x: number
  ego_y: number
  ego_v: number
  entities: APFEntity[]
  extent_x: number
  extent_y: number
  control_steer_x: number
  control_steer_y: number
  delta_theta: number
  v_target: number
  trajectory: Array<[number, number, number] | string>
  corridor_xy: Array<[number, number]>
}

export type MockVisualDataResponse = {
  sggVisualData: SGGVisualData
  apfVisualData: APFVisualData
}

export type UploadedRunDangerEntity = {
  id: number
  cls: string
  dangerQuality: number
  dangerClass: string
  ttc: number | null
}

export type UploadedRunFrameData = {
  frameIndex: number
  frameFile: string
  timestampMs: number
  steering: {
    deltaTheta: number
    controlSteerX: number
    controlSteerY: number
  }
  velocity: {
    vTarget: number
    egoV: number
  }
  dangerZone: {
    topEntity: UploadedRunDangerEntity | null
    entities: UploadedRunDangerEntity[]
  }
  reasoning: {
    summary: string
    primaryRelation: string | null
    sourceEntityId: number
    targetEntityId: number
  }
  sggVisualData: SGGVisualData
  apfVisualData: APFVisualData
}

export type UploadedRunVisualDataResponse = {
  runId: string
  status: 'completed'
  sourceFrames: {
    fileCount: number
    fileNames: string[]
    samplingFps: number
  }
  tracker: {
    status: string
    startedAt: string | null
    finishedAt: string | null
    error: string | null
    csvPath: string
    processedFrames: number
  }
  frames: UploadedRunFrameData[]
}

export type ReportMetadataItem = {
  label: string
  value: string
}

export type RunReportResponse = {
  headline: string
  body: string
  metadata: ReportMetadataItem[]
  generated_by: string
  fallback_used: boolean
}

export async function getMockVisualData(): Promise<MockVisualDataResponse> {
  const res = await fetch(`${BACKEND_URL}/mock-visual-data`)

  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`)
  }

  return res.json()
}

export async function uploadFrameFolder(
  files: File[],
  folderName?: string,
): Promise<UploadFramesResponse> {
  const formData = new FormData()

  for (const file of files) {
    formData.append('files', file, file.name)
  }

  if (folderName) {
    formData.append('folder_name', folderName)
  }

  const res = await fetch(`${BACKEND_URL}/runs/upload-frames`, {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    let message = `Request failed with status ${res.status}`

    try {
      const data = await res.json()
      if (typeof data.detail === 'string') {
        message = data.detail
      }
    } catch {
    }

    throw new Error(message)
  }

  return res.json()
}

export async function getRunFrames(runId: string): Promise<RunFramesResponse> {
  const res = await fetch(`${BACKEND_URL}/runs/${runId}/frames`)

  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`)
  }

  return res.json()
}

export async function getRunVisualData(runId: string): Promise<UploadedRunVisualDataResponse> {
  const res = await fetch(`${BACKEND_URL}/runs/${runId}/visual-data`)

  if (!res.ok) {
    let message = `Request failed with status ${res.status}`

    try {
      const data = await res.json()
      if (typeof data.detail === 'string') {
        message = data.detail
      }
    } catch {
    }

    throw new Error(message)
  }

  return res.json()
}

export async function getRunReport(): Promise<RunReportResponse> {
  const res = await fetch(`${BACKEND_URL}/report`)

  if (!res.ok) {
    let message = `Request failed with status ${res.status}`

    try {
      const data = await res.json()
      if (typeof data.detail === 'string') {
        message = data.detail
      }
    } catch {
    }

    throw new Error(message)
  }

  return res.json()
}
