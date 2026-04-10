import { useState } from 'react'
import { ArrowRight, LockKeyhole } from 'lucide-react'

type PasscodeGateProps = {
  errorMessage?: string | null
  onUnlock: (passcode: string) => void
}

export function PasscodeGate({ errorMessage, onUnlock }: PasscodeGateProps) {
  const [passcode, setPasscode] = useState('')

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#111315] text-zinc-50">
      <div
        className="absolute inset-0"
        aria-hidden="true"
        style={{
          background:
            'radial-gradient(circle at 16% 18%, rgba(190, 220, 143, 0.16), transparent 28%), radial-gradient(circle at 84% 14%, rgba(101, 136, 96, 0.16), transparent 24%), radial-gradient(circle at 50% 78%, rgba(84, 94, 130, 0.16), transparent 34%), linear-gradient(140deg, #15181a 0%, #101214 42%, #16161b 100%)',
        }}
      />
      <div
        className="absolute inset-0 opacity-20"
        aria-hidden="true"
        style={{
          background:
            'linear-gradient(120deg, transparent 28%, rgba(255,255,255,0.08) 38%, transparent 46%), linear-gradient(145deg, transparent 52%, rgba(255,255,255,0.05) 61%, transparent 70%)',
        }}
      />

      <div
        className="absolute inset-0 opacity-30"
        aria-hidden="true"
        style={{
          background:
            'linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)',
          backgroundSize: '120px 120px',
          maskImage: 'linear-gradient(180deg, rgba(0,0,0,0.75), transparent)',
        }}
      />

      <div className="relative mx-auto flex min-h-screen w-full max-w-[1500px] flex-col px-6 py-8 sm:px-8 lg:px-10">
        <header className="flex items-center justify-between">
          <p className="text-2xl font-semibold tracking-tight text-white">AgriVision</p>
          <div className="hidden rounded-full border border-white/8 bg-white/[0.03] px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-zinc-400 sm:block">
            Protected Access
          </div>
        </header>

        <section className="flex flex-1 items-center py-8">
          <div className="grid w-full items-center gap-12 lg:grid-cols-[minmax(0,1.1fr)_460px]">
            <div className="max-w-2xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#a4b18b]">
                Autonomous Field Intelligence
              </p>
              <h1 className="mt-5 text-5xl font-semibold leading-[1.02] tracking-tight text-white sm:text-6xl">
                Safety reports and run review for field operations.
              </h1>
              <p className="mt-6 max-w-xl text-lg leading-8 text-zinc-300">
                Review uploaded frame runs, inspect incident summaries, and move between upload,
                dashboard, and report views in one secure internal workspace.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <InfoChip label="Run Reports" value="Summary-first review" />
                <InfoChip label="Frame Input" value="Folder-based upload" />
                <InfoChip label="Access" value="Passcode protected" />
              </div>
            </div>

            <section className="rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(24,27,29,0.76),rgba(17,18,22,0.72))] p-8 shadow-[0_28px_90px_rgba(0,0,0,0.28)] backdrop-blur-xl sm:p-10">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-zinc-500">
                    AgriVision Access
                  </p>
                  <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-[2.5rem]">
                    Enter passcode
                  </h2>
                </div>
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-[#4d5e3f] bg-[#232a22] text-[#dbe9b3] shadow-[0_14px_30px_rgba(0,0,0,0.24)]">
                  <LockKeyhole className="h-6 w-6" />
                </div>
              </div>

              <p className="mt-4 text-base leading-7 text-zinc-400">
                Use the internal preview passcode to open the workspace.
              </p>

              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  onUnlock(passcode)
                }}
                className="mt-8"
              >
                <label htmlFor="passcode-input" className="sr-only">
                  Passcode
                </label>
                <input
                  id="passcode-input"
                  type="password"
                  autoComplete="current-password"
                  value={passcode}
                  onChange={(event) => setPasscode(event.target.value)}
                  placeholder="Passcode"
                  className="w-full rounded-2xl border border-white/10 bg-[#101214] px-5 py-4 text-base text-white outline-none transition placeholder:text-zinc-500 focus:border-[#5c7245] focus:ring-2 focus:ring-[#5c7245]/30"
                />

                {errorMessage ? <p className="mt-3 text-sm text-rose-300">{errorMessage}</p> : null}

                <button
                  type="submit"
                  className="mt-6 inline-flex items-center gap-2 rounded-full border border-[#5a6f43] bg-[#2a3323] px-6 py-3 text-base font-medium text-[#edf5d5] transition hover:border-[#6a8350] hover:bg-[#313c29]"
                >
                  <span>Enter Workspace</span>
                  <ArrowRight className="h-4 w-4" />
                </button>
              </form>
            </section>
          </div>
        </section>
      </div>
    </div>
  )
}

function InfoChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.035] px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-zinc-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-zinc-100">{value}</p>
    </div>
  )
}
