/**
 * Settings page — lets operators set their display name and optional JWT token
 * (both persisted to localStorage) and shows the live backend health/component status.
 */
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Save, Trash2 } from 'lucide-react'
import GlassCard from '../components/cards/GlassCard.jsx'
import { Health, Me } from '../services/api.js'

const inputCls = 'w-full bg-white/80 border border-white/60 rounded-xl px-3 py-2 outline-none mb-3'

export default function Settings() {
  const [op, setOp]       = useState(localStorage.getItem('operator_name') || '')
  const [token, setToken] = useState(localStorage.getItem('jwt_token') || '')
  const [me, setMe]       = useState(null)
  const [health, setHealth] = useState(null)

  useEffect(() => {
    Health().then(setHealth).catch(() => {})
    Me().then(setMe).catch(() => {})
  }, [])

  /** Persists operator name and JWT to localStorage, then re-fetches /auth/me to validate the token. */
  const save = () => {
    localStorage.setItem('operator_name', op)
    localStorage.setItem('jwt_token', token)
    Me().then(setMe).catch(() => setMe(null))
  }
  /** Removes the stored JWT token and clears the current identity display. */
  const clearToken = () => { localStorage.removeItem('jwt_token'); setToken(''); setMe(null) }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 animate-fade-up">
      <GlassCard title="Operator profile" accent="#5EE6C8" subtitle="Identifies you in audit logs">
        <label className="block text-xs text-ink-300 mb-1">Operator name</label>
        <input value={op} onChange={(e) => setOp(e.target.value)}
               placeholder="Hani - Operations" className={inputCls} />
        <label className="block text-xs text-ink-300 mb-1">
          JWT token <span className="text-ink-300">(only needed when multi-tenancy is enabled)</span>
        </label>
        <textarea value={token} onChange={(e) => setToken(e.target.value)}
                  placeholder="paste a JWT from POST /auth/login"
                  className={inputCls + ' font-mono text-xs h-24'} />
        <div className="flex gap-2">
          <button onClick={save} className="btn-primary"><Save className="w-4 h-4" /> Save</button>
          <button onClick={clearToken} className="btn-secondary"><Trash2 className="w-4 h-4" /> Clear token</button>
        </div>
        {me && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 surface p-3 text-xs">
            <div><b>username:</b> {me.username}</div>
            <div><b>tenant_id:</b> {me.tenant_id}</div>
            <div><b>role:</b> {me.role}</div>
          </motion.div>
        )}
      </GlassCard>

      <GlassCard title="Backend health" accent="#4DA8FF">
        {!health ? <p className="text-sm text-ink-300">checking...</p> : (
          <ul className="space-y-1 text-sm">
            <li><b>status</b> - {health.status}</li>
            <li><b>version</b> - {health.version}</li>
            {Object.entries(health.components || {}).map(([k, v]) => (
              <li key={k}><span className="font-mono text-ink-500 w-32 inline-block">{k}</span> {v}</li>
            ))}
          </ul>
        )}
      </GlassCard>
    </div>
  )
}
