import { navItems } from '../data'

type DashboardHeaderProps = {
  activeView: 'upload' | 'dashboard' | 'report'
  onSelectView: (view: 'upload' | 'dashboard' | 'report') => void
}

export function DashboardHeader({ activeView, onSelectView }: DashboardHeaderProps) {
  return (
    <header className="border-b border-white/6 bg-[#111315]/95 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4 px-6 py-3">
        <p className="text-2xl font-semibold tracking-tight text-white">AgriVision</p>

        <nav className="flex items-center gap-1">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = item.key === activeView

            return (
              <button
                key={item.label}
                type="button"
                onClick={() => {
                  if (item.key === 'upload' || item.key === 'dashboard' || item.key === 'report') {
                    onSelectView(item.key)
                  }
                }}
                disabled={!item.enabled}
                className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition ${
                  isActive
                    ? 'bg-[#232a22] text-white shadow-[inset_0_0_0_1px_rgba(160,180,126,0.18)]'
                    : item.enabled
                      ? 'text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-200'
                      : 'cursor-not-allowed text-zinc-600'
                }`}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>

        <div className="w-24" aria-hidden="true" />
      </div>
    </header>
  )
}
