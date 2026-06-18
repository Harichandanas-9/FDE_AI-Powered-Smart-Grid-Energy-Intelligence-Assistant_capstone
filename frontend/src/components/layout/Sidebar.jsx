/**
 * Sidebar — left-hand navigation panel containing the app logo and all page links.
 * Active routes are highlighted with an accent dot; each item animates in on mount.
 */
import { NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard, MessageSquare, Activity, AlertTriangle, Gauge,
  Waves, Lightbulb, Network, Clock, Grid3x3, Database, Settings as SettingsIcon, Zap, TrendingUp,
} from 'lucide-react'

const NAV = [
  { to: '/',                   label: 'Dashboard',      Icon: LayoutDashboard, accent: 'accent-dashboard'  },
  { to: '/query',              label: 'Query Console',  Icon: MessageSquare,   accent: 'accent-query'      },
  { to: '/etl',                label: 'ETL',            Icon: Database,        accent: 'accent-etl'        },
  { to: '/stability',          label: 'Grid Stability', Icon: Activity,        accent: 'accent-stability'  },
  { to: '/failure',            label: 'Failure Analysis', Icon: AlertTriangle, accent: 'accent-failure'    },
  { to: '/meter',              label: 'Smart Meter',    Icon: Gauge,           accent: 'accent-meter'      },
  { to: '/telemetry',          label: 'Telemetry',      Icon: Waves,           accent: 'accent-telemetry'  },
  { to: '/recommendations',    label: 'Recommendations',Icon: Lightbulb,       accent: 'accent-recommend'  },
  { to: '/agents',             label: 'Agent Flow',     Icon: Network,         accent: 'accent-agent'      },
  { to: '/timeline',           label: 'Incident Timeline', Icon: Clock,        accent: 'accent-timeline'   },
  { to: '/heatmap',            label: 'Heatmap',        Icon: Grid3x3,         accent: 'accent-heatmap'    },
  { to: '/predict',            label: 'Predictive AI',  Icon: TrendingUp,      accent: 'accent-failure'    },
  { to: '/settings',           label: 'Settings',       Icon: SettingsIcon,    accent: 'accent-dashboard'  },
]

export default function Sidebar() {
  return (
    <aside className="hidden md:flex md:flex-col w-64 glass m-3 mr-0 p-4 sticky top-3 self-start h-[calc(100vh-1.5rem)]">
      {/* Logo */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-2.5 mb-6 px-1"
      >
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-mint-500 to-lavender-500
                        flex items-center justify-center shadow-glow animate-pulse-glow">
          <Zap className="w-5 h-5 text-white" />
        </div>
        <div className="leading-tight">
          <div className="font-bold text-ink-900">Smart Grid AI</div>
          <div className="text-xs text-ink-300">Energy Intelligence</div>
        </div>
      </motion.div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto pr-1 space-y-1">
        {NAV.map(({ to, label, Icon, accent }, idx) => (
          <motion.div
            key={to}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.025 }}
          >
            <NavLink
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                'nav-pill ' + (isActive ? 'nav-pill-active' : '')
              }
              style={({ isActive }) => isActive
                ? { boxShadow: `0 0 0 1px rgb(var(--accent-rgb, 94 230 200) / 0.0)` }
                : undefined
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className="w-4.5 h-4.5"
                    style={{ color: isActive ? `var(--tw-${accent})` : undefined,
                             width: 18, height: 18 }}
                  />
                  <span>{label}</span>
                  {isActive && (
                    <span
                      className="ml-auto w-1.5 h-1.5 rounded-full"
                      style={{ background: `var(--tw-${accent})` }}
                    />
                  )}
                </>
              )}
            </NavLink>
          </motion.div>
        ))}
      </nav>

      <div className="text-[10px] text-ink-300 px-1 mt-3">
        v0.1.0 · sandbox demo
      </div>
    </aside>
  )
}
