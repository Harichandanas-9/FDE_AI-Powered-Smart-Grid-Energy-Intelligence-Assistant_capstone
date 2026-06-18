/**
 * Root application component — configures client-side routing for all pages
 * and runs a background prefetch of the most critical API calls 1.5 s after mount.
 */
import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout.jsx'

import Dashboard              from './pages/Dashboard.jsx'
import ETL                    from './pages/ETL.jsx'
import QueryConsole            from './pages/QueryConsole.jsx'
import GridStability           from './pages/GridStability.jsx'
import FailureAnalysis         from './pages/FailureAnalysis.jsx'
import SmartMeter              from './pages/SmartMeter.jsx'
import Telemetry               from './pages/Telemetry.jsx'
import Recommendations         from './pages/Recommendations.jsx'
import AgentVisualization      from './pages/AgentVisualization.jsx'
import IncidentTimeline        from './pages/IncidentTimeline.jsx'
import HeatmapAnalytics        from './pages/HeatmapAnalytics.jsx'
import Settings                from './pages/Settings.jsx'
import PredictiveIntelligence  from './pages/PredictiveIntelligence.jsx'

import {
  GridScore, Heatmap, Timeline, EtlLastRun,
} from './services/api.js'

// Background prefetch — fires 1.5 s after the app mounts so the initial
// Dashboard load is not delayed. All responses are stored in the 1-hour
// axios localStorage cache, so every subsequent tab click is instant.
function usePrefetch() {
  useEffect(() => {
    const timer = setTimeout(() => {
      // Prefetch only the 4 most critical calls (avoids overloading backend)
      const calls = [
        GridScore,
        Heatmap,
        () => Timeline('day'),
        EtlLastRun,
      ]
      calls.forEach((fn) => {
        try { fn().catch(() => {}) } catch (_) {}
      })
    }, 1500) // wait 1.5 s after initial render
    return () => clearTimeout(timer)
  }, [])
}

/**
 * App — top-level component that wraps the router.
 * All page routes are nested inside AppLayout so they share the sidebar and topbar.
 */
export default function App() {
  usePrefetch()

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index                  element={<Dashboard />} />
          <Route path="query"           element={<QueryConsole />} />
          <Route path="etl"             element={<ETL />} />
          <Route path="stability"       element={<GridStability />} />
          <Route path="failure"         element={<FailureAnalysis />} />
          <Route path="meter"           element={<SmartMeter />} />
          <Route path="telemetry"       element={<Telemetry />} />
          <Route path="recommendations" element={<Recommendations />} />
          <Route path="agents"          element={<AgentVisualization />} />
          <Route path="timeline"        element={<IncidentTimeline />} />
          <Route path="heatmap"         element={<HeatmapAnalytics />} />
          <Route path="predict"         element={<PredictiveIntelligence />} />
          <Route path="settings"        element={<Settings />} />
          <Route path="*"               element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
