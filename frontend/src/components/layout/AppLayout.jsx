/**
 * AppLayout — persistent shell component shared by all page routes.
 * Renders the fixed Sidebar on the left and the Topbar above the page content area.
 */
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar.jsx'
import Topbar from './Topbar.jsx'

/** Renders the two-column app shell; the current page is injected via <Outlet>. */
export default function AppLayout() {
  return (
    <div className="min-h-full flex">
      <Sidebar />
      <div className="flex-1 min-w-0 flex flex-col">
        <Topbar />
        <main className="flex-1 mx-3 mb-3 overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
