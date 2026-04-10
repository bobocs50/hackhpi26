export function UploadView() {
  return (
    <div className="mx-auto flex min-h-[calc(100vh-73px)] w-full max-w-5xl items-center px-6 py-8">
      <section className="w-full rounded-3xl border border-dashed border-[#4a5447] bg-[linear-gradient(180deg,#171a1c_0%,#111315_100%)] p-6 shadow-[0_24px_60px_rgba(0,0,0,0.3)] sm:p-8">
        <div className="flex min-h-[420px] flex-col items-center justify-center rounded-[1.75rem] border border-dashed border-white/10 bg-[radial-gradient(circle_at_top,rgba(196,255,140,0.08),transparent_45%),rgba(255,255,255,0.015)] px-6 text-center">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-zinc-500">Upload</p>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Drop a folder with frames
          </h1>
          <div className="mt-8 rounded-2xl border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-medium text-zinc-300">
            Drop folder here
          </div>
        </div>
      </section>
    </div>
  )
}
