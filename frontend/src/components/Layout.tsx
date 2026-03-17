import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'

const pageTitles: Record<string, string> = {
  '/upload': 'Data Upload',
  '/fleet': 'Fleet Overview',
  '/planning': 'Feed Planning & Optimization',
}

export default function Layout() {
  const { pathname } = useLocation()
  const title = pageTitles[pathname] ?? 'Dashboard'

  return (
    <div className="flex h-full">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center justify-between px-6 py-3 border-b border-[#234060] bg-[#001E35] shrink-0">
          <h1 className="text-[#D4D4D4] font-semibold text-base">{title}</h1>
          <div className="flex items-center gap-3">
            <span className="text-[#4A4A4A] text-xs">Ethylene Cracking Fleet · AF Plant</span>
            <div className="w-2 h-2 rounded-full bg-[#00B4CC]" title="Live" />
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
