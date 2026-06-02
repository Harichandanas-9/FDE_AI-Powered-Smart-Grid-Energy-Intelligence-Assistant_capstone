import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Database, RefreshCw, CheckCircle2, Trash2 } from 'lucide-react'
import GlassCard from './cards/GlassCard.jsx'
import { ListDatasets, ProcessDataset, ResetIndex, ValidateRetrieval } from '../services/api.js'

export default function IngestionManager({ onIngested }) {
  const [datasets,  setDS]    = useState([])
  const [sel,       setSel]   = useState('smart_grid_stability_augmented.csv')
  const [busy,      setBusy]  = useState('')
  const [notif,     setNotif] = useState(null)
  const [validation,setVal]   = useState(null)
  const [vectorsIdx,setVec]   = useState(null)

  const note = (text, kind = 'ok', ms = 6000) => {
    setNotif({ text, kind })
    if (ms) setTimeout(() => setNotif(null), ms)
  }

  const load = async () => {
    try {
      const d = await ListDatasets()
      const files = d.files || []
      setDS(files)
      // Keep selection valid — default to first known file
      if (files.length && !files.find(f => f.filename === sel)) {
        setSel(files[0].filename)
      }
      setVec(d.vectors_indexed ?? null)
    } catch { /* backend not yet ready */ }
  }

  useEffect(() => { load() }, [])

  const ingest = async (reset) => {
    if (!sel) return note('Please select a dataset first.', 'err')
    setBusy(reset ? 'reingest' : 'ingest')
    try {
      const r = await ProcessDataset(sel)
      if (r && r.status === 'error') {
        note(`Ingestion failed at step "${r.step}": ${r.detail}`, 'err', 12000)
      } else {
        const n = r?.ingest_report?.chunks_written ?? r?.chunks ?? '?'
        note(`✅ Ingested "${sel}" — ${n} chunks written${r?.vectors_total ? ', ' + r.vectors_total + ' vectors indexed' : ''}`, 'ok', 8000)
        if (onIngested) onIngested()
      }
      await load()
    } catch (e) {
      note(e.friendly || e.message || 'Ingestion failed', 'err', 10000)
    } finally { setBusy('') }
  }

  const resetIdx = async () => {
    setBusy('reset')
    try {
      const r = await ResetIndex()
      note(r.message || 'Vector index reset', r.status === 'ok' ? 'ok' : 'err')
      await load()
    } catch (e) { note(e.friendly || 'Reset failed', 'err') }
    finally { setBusy('') }
  }

  const validate = async () => {
    setBusy('validate'); setVal(null)
    try {
      const r = await ValidateRetrieval()
      setVal(r)
      note(`Retrieval ${r.status} — ${r.n_results} hits — ${r.latency_ms} ms`,
           r.status === 'error' ? 'err' : 'ok')
    } catch (e) { note(e.friendly || 'Validation failed', 'err') }
    finally { setBusy('') }
  }

  const selectCls = 'w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 outline-none focus:ring-2 focus:ring-mint-400'

  return (
    <div className="space-y-3">
      {/* Notification banner */}
      {notif && (
        <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
          className={'rounded-xl border-l-4 px-4 py-2.5 text-sm ' +
            (notif.kind === 'err'
              ? 'border-red-400 bg-red-50 text-red-700'
              : 'border-mint-500 bg-mint-50 text-mint-700')}>
          {notif.text}
        </motion.div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* LEFT: Data Ingestion */}
        <GlassCard title="Data Ingestion" accent="#4DA8FF"
                   subtitle="Select a dataset and click Ingest to process it">

          {/* Dataset selector */}
          <div className="mb-4">
            <label className="block text-xs font-medium text-ink-500 mb-1.5">Dataset</label>
            <select className={selectCls} value={sel}
                    onChange={(e) => setSel(e.target.value)}>
              {(datasets.length
                ? datasets
                : [
                    { filename: 'smart_grid_stability_augmented.csv' },
                    { filename: 'household_power_consumption.csv' },
                    { filename: 'electric_power_consumption.csv' },
                  ]
              ).map((d) => (
                <option key={d.filename} value={d.filename}>{d.filename}</option>
              ))}
            </select>
          </div>

          {/* Status chip */}
          {vectorsIdx !== null && (
            <p className="text-xs text-ink-400 mb-3">
              <span className="font-medium text-mint-700">{vectorsIdx}</span> vectors currently indexed
            </p>
          )}

          {/* Action buttons */}
          <div className="flex flex-wrap gap-2">
            <button onClick={() => ingest(false)} disabled={!!busy}
                    className="btn-primary flex items-center gap-2">
              <RefreshCw className={'w-4 h-4 ' + (busy === 'ingest' ? 'animate-spin' : '')} />
              {busy === 'ingest' ? 'Ingesting…' : 'Ingest'}
            </button>
            <button onClick={() => ingest(true)} disabled={!!busy}
                    className="btn-secondary flex items-center gap-2">
              <RefreshCw className={'w-4 h-4 ' + (busy === 'reingest' ? 'animate-spin' : '')} />
              {busy === 'reingest' ? 'Re-ingesting…' : 'Re-Ingest'}
            </button>
          </div>
        </GlassCard>

        {/* RIGHT: Index Management */}
        <GlassCard title="Index Management & Validation" accent="#6FE38A"
                   subtitle="Reset the vector index or verify retrieval works">
          <div className="flex flex-wrap gap-2 mb-3">
            <button onClick={resetIdx} disabled={!!busy}
                    className="btn-secondary !text-red-600 !border-red-200 flex items-center gap-2">
              <Trash2 className={'w-4 h-4 ' + (busy === 'reset' ? 'animate-spin' : '')} />
              Reset Index
            </button>
            <button onClick={validate} disabled={!!busy}
                    className="btn-primary flex items-center gap-2">
              <CheckCircle2 className={'w-4 h-4 ' + (busy === 'validate' ? 'animate-spin' : '')} />
              Validate Retrieval
            </button>
          </div>

          {validation && (
            <div className="surface p-3 text-xs space-y-2 mt-2">
              <div className="flex items-center gap-2">
                <span className={'pill ' + (validation.status === 'ok' ? 'pill-low' : 'pill-high')}>
                  {validation.status}
                </span>
                <span className="text-ink-500">{validation.n_results} hits · {validation.latency_ms} ms</span>
              </div>
              {(validation.results || []).slice(0, 3).map((r, i) => (
                <div key={i} className="border-t border-white/40 pt-1">
                  <div className="font-mono text-ink-400 truncate">{r.id}</div>
                  <div className="text-ink-600 line-clamp-2">{r.preview}</div>
                </div>
              ))}
              {validation.message && <div className="text-red-600">{validation.message}</div>}
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  )
}
