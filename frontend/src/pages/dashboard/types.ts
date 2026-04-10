export type Point = {
  x: number
  y: number
}

export type Annotation = {
  id: string
  label: string
  text_label: string
  certainty: number
  bbox: {
    x: number
    y: number
    width: number
    height: number
  }
  segment_points?: Point[]
  reason?: string
}

export type VisionFrame = {
  frame_file: string
  frame_index: number
  timestamp_ms: number
  annotations: Annotation[]
  steering: {
    recommended_action: string
    steering_angle_deg: number
    speed_factor: number
    brake_factor: number
    vector_reasoning?: string[]
  }
  danger_reasoning: {
    level: 'low' | 'medium' | 'high'
    score: number
    primary_reason: string
    secondary_reason: string
  }
  uncertainty: {
    overall: number
    notes?: string[]
  }
  summary: string
}

export type VisionRun = {
  run_id: string
  source: {
    folder_name: string
    location_hint: string
    captured_at: string
    sampling_rate_fps: number
    frame_width: number
    frame_height: number
  }
  frames: VisionFrame[]
}

export type LevelTheme = {
  tone: string
  badge: string
  box: string
}

export type DetectionBadge = Annotation & {
  color: LevelTheme
}

export type ChatMessage = {
  id: string
  role: 'assistant' | 'user'
  text: string
}
