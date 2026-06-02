import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar.jsx'
import Topbar from './Topbar.jsx'

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
