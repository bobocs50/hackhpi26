import { useState } from 'react'
import { Bot, SendHorizonal } from 'lucide-react'

import { capitalize, humanizeAction } from '../data'
import type { DetectionBadge, VisionFrame } from '../data'

type ChatPanelProps = {
  currentFrame: VisionFrame
  detectionBadges: DetectionBadge[]
}

type ChatMessage = {
  id: string
  role: 'assistant' | 'user'
  text: string
}

function buildInitialMessages(frame: VisionFrame, detectionBadges: DetectionBadge[]): ChatMessage[] {
  const topObjects = detectionBadges
    .slice(0, 2)
    .map((annotation) => annotation.text_label)
    .join(', ')

  return [
    {
      id: `assistant-intro-${frame.frame_index}`,
      role: 'assistant',
      text: `Frame ${frame.frame_index + 1} loaded.`,
    },
    {
      id: `assistant-context-${frame.frame_index}`,
      role: 'assistant',
      text:
        detectionBadges.length > 0
          ? `${capitalize(frame.danger_reasoning.level)} risk. ${topObjects}.`
          : `${capitalize(frame.danger_reasoning.level)} risk. No hazards flagged.`,
    },
  ]
}

function buildAssistantReply(input: string, frame: VisionFrame, detectionBadges: DetectionBadge[]): string {
  const normalizedInput = input.toLowerCase()

  if (normalizedInput.includes('risk') || normalizedInput.includes('danger')) {
    return `${capitalize(frame.danger_reasoning.level)} risk at ${frame.danger_reasoning.score.toFixed(2)}. ${frame.danger_reasoning.primary_reason}`
  }

  if (normalizedInput.includes('steer') || normalizedInput.includes('action') || normalizedInput.includes('brake')) {
    return `Recommended action is ${humanizeAction(frame.steering.recommended_action)} with steering at ${frame.steering.steering_angle_deg.toFixed(1)}° and brake at ${Math.round(frame.steering.brake_factor * 100)}%.`
  }

  if (normalizedInput.includes('object') || normalizedInput.includes('detect') || normalizedInput.includes('see')) {
    if (detectionBadges.length === 0) {
      return 'No objects or hazards are flagged in this frame.'
    }

    const labels = detectionBadges
      .slice(0, 3)
      .map((annotation) => `${annotation.text_label} (${Math.round(annotation.certainty * 100)}%)`)
      .join(', ')

    return `The model is currently tracking ${labels}.`
  }

  return `This frame suggests ${humanizeAction(frame.steering.recommended_action)} because ${frame.danger_reasoning.primary_reason.toLowerCase()}.`
}

export function ChatPanel({ currentFrame, detectionBadges }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    buildInitialMessages(currentFrame, detectionBadges),
  )
  const [draft, setDraft] = useState('')

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const nextDraft = draft.trim()
    if (!nextDraft) {
      return
    }

    const timestamp = Date.now()

    const userMessage: ChatMessage = {
      id: `user-${timestamp}`,
      role: 'user',
      text: nextDraft,
    }

    const assistantMessage: ChatMessage = {
      id: `assistant-${timestamp + 1}`,
      role: 'assistant',
      text: buildAssistantReply(nextDraft, currentFrame, detectionBadges),
    }

    setMessages((existing) => [...existing, userMessage, assistantMessage])
    setDraft('')
  }

  return (
    <aside className="h-full min-h-[620px] max-w-[880px] rounded-3xl border border-white/6 bg-[#15171a] shadow-[0_20px_48px_rgba(0,0,0,0.24)]">
      <div className="flex h-full flex-col">
        <div className="border-b border-white/6 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#3b4730] bg-[#232a22] text-[#d7e4b0]">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-zinc-500">Research Assistant</p>
            </div>
          </div>
        </div>

        <div className="flex-1 space-y-2.5 overflow-y-auto px-4 py-3 sm:px-5">
          {messages.map((message) => (
            <article
              key={message.id}
              className={`max-w-[85%] rounded-2xl border px-3.5 py-2.5 text-sm leading-6 shadow-[0_10px_24px_rgba(0,0,0,0.14)] ${
                message.role === 'assistant'
                  ? 'border-white/6 bg-[#111315] text-zinc-200'
                  : 'ml-auto border-[#3b4730] bg-[#232a22] text-[#f2f5e8]'
              }`}
            >
              {message.text}
            </article>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="border-t border-white/6 px-4 py-3">
          <label htmlFor="dashboard-chat-input" className="sr-only">
            Research assistant input
          </label>
          <textarea
            id="dashboard-chat-input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Type a question..."
            rows={3}
            className="w-full resize-none rounded-2xl border border-white/8 bg-[#111315] px-4 py-3 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-[#536441] focus:ring-2 focus:ring-[#536441]/30"
          />
          <div className="mt-3 flex items-center justify-end gap-3">
            <button
              type="submit"
              className="inline-flex items-center gap-2 rounded-xl border border-[#536441] bg-[#2a3323] px-4 py-2 text-sm font-medium text-[#edf5d5] transition hover:border-[#63794c] hover:bg-[#313c29]"
            >
              <SendHorizonal className="h-4 w-4" />
              <span>Send</span>
            </button>
          </div>
        </form>
      </div>
    </aside>
  )
}
