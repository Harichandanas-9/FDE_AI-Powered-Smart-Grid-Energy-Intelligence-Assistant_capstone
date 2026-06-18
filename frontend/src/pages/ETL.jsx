/**
 * ETL page — manages CSV datasets on the backend and drives the Extract-Transform-Load pipeline.
 * Operators can upload new CSVs, run ETL on existing files, track per-file processing status,
 * and delete datasets. Last-run metadata is persisted to sessionStorage across navigations.
 */
import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, Database, Play, Trash2, FileText, CheckCircle2, AlertCircle,
  RefreshCw, ListChecks, UploadCloud, HardDrive, Clock, XCircle,
} from 'lucide-react'
import GlassCard from '../components/cards/GlassCard.jsx'
import IngestionManager from '../components/IngestionManager.jsx'
import {
  ListDatasets, UploadDataset, DeleteDataset, ProcessDataset, ClearEtlCache,
} from '../services/api.js'

/** Converts a byte count to a human-readable string (B / KB / MB). */
function fmtSize(b) {
  if (!b) return '0 B'
  if (b < 1024) return b + ' B'
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB'
  return (b / 1024 / 1024).toFixed(1) + ' MB'
}

/** Converts an elapsed millisecond count to a compact relative string (e.g. "4m ago"). */
function fmtAgo(ms) {
  const s = Math.floor(ms / 1000)
  if (s < 60)   return s + 's ago'
  if (s < 3600) return Math.floor(s / 60) + 'm ago'
  return Math.floor(s / 3600) + 'h ago'
}

/** Renders a coloured pill (Processing / Completed / Failed) for a file's ETL status. */
function StatusBadge({ status, error }) {
  if (status === 'processing') return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-700">
      <RefreshCw className="w-3 h-3 animate-spin" /> Processing
    </span>
  )
  if (status === 'completed') return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-mint-100 text-mint-700">
      <CheckCircle2 className="w-3 h-3" /> Completed
    </span>
  )
  if (status === 'failed') return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-700"
          title={error || ''}>
      <XCircle className="w-3 h-3" /> Failed
    </span>
  )
  return null
}

export default function ETL() {
  const [tab, setTab] = useState(
    () => sessionStorage.getItem('etl_tab') || 'existing'
  )
  useEffect(() => { sessionStorage.setItem('etl_tab', tab) }, [tab])

  const [data, setData]             = useState(null)
  const [busy, setBusy]             = useState(false)
  const [processingFile, setPF]     = useState(null)
  const [deletingFile, setDF]       = useState(null)
  const [progress, setProgress]     = useState(0)
  const [fileStatus, setFileStatus] = useState({}) // filename -> {status:'completed'|'failed'|'processing', error?}
  const [notification, setNotif]    = useState(null) // {kind:'info'|'ok'|'err', text}
  const [lastRun, setLastRun]       = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('etl_lastRun') || 'null') }
    catch { return null }
  })
  const [agoTick, setAgoTick]   = useState(0)
  const fileInput               = useRef(null)

  // Tick "Xs ago" label
  useEffect(() => {
    if (!lastRun) return
    const id = setInterval(() => setAgoTick((t) => t + 1), 1000)
    return () => clearInterval(id)
  }, [lastRun])

  const load = async () => {
    setBusy(true)
    try { setData(await ListDatasets()) } finally { setBusy(false) }
  }
  useEffect(() => { load() }, [])

  // Restore persisted file statuses
  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem('etl_fileStatus') || '{}')
      setFileStatus(saved)
    } catch {}
  }, [])

  /** Updates a file's status in state and mirrors it to sessionStorage so it survives tab switches. */
  const updateFileStatus = (fname, status, error) => {
    setFileStatus((prev) => {
      const next = { ...prev, [fname]: { status, error } }
      sessionStorage.setItem('etl_fileStatus', JSON.stringify(next))
      return next
    })
  }

  const showNotif = (text, kind = 'info', duration = 6000) => {
    setNotif({ text, kind })
    if (duration > 0) setTimeout(() => setNotif(null), duration)
  }

  const onUpload = async (file) => {
    if (!file) return
    setBusy(true); setProgress(0)
    try {
      const r = await UploadDataset(file, setProgress)
      showNotif('Uploaded ' + r.filename + ' · ' + fmtSize(r.size_bytes), 'ok')
      await load()
      setTab('existing')
    } catch (e) {
      showNotif(e.friendly || 'Upload failed', 'err')
    } finally { setBusy(false); setProgress(0) }
  }

  const onProcess = async (fname) => {
    if (processingFile) {
      showNotif('Already processing ' + processingFile + ' — please wait.', 'err')
      return
    }
    setPF(fname)
    updateFileStatus(fname, 'processing')
    showNotif('ETL Processing Started for ' + fname, 'info', 0) // 0 = stay until replaced

    try {
      const r = await ProcessDataset(fname)
      const duration = r.duration_seconds ?? 0
      const run = {
        file: fname, duration, finishedAt: Date.now(),
        chunks: r.ingest_report?.chunks_written ?? 0,
        vectors: r.vectors_total ?? 0,
      }
      setLastRun(run)
      sessionStorage.setItem('etl_lastRun', JSON.stringify(run))
      updateFileStatus(fname, 'completed')
      try { ClearEtlCache() } catch {}
      localStorage.setItem('etl_completed_at', String(Date.now()))
      showNotif('ETL Completed Successfully · ' + run.chunks + ' chunks · ' + run.vectors + ' vectors in ' + Math.round(duration) + 's', 'ok')
      await load()
    } catch (e) {
      const errMsg = e.friendly || e.message || 'ETL Failed'
      updateFileStatus(fname, 'failed', errMsg)
      showNotif('ETL Failed · ' + errMsg, 'err')
    } finally {
      setPF(null)
    }
  }

  const onDelete = async (fname) => {
    if (!confirm('Delete ' + fname + '?')) return
    setDF(fname)
    try {
      await DeleteDataset(fname)
      showNotif('Deleted ' + fname, 'ok')
      setFileStatus((prev) => {
        const next = { ...prev }
        delete next[fname]
        sessionStorage.setItem('etl_fileStatus', JSON.stringify(next))
        return next
      })
      await load()
    } catch (e) {
      showNotif(e.friendly || 'Delete failed', 'err')
    } finally { setDF(null) }
  }

  const files = data?.files || []
  const persistedCount = files.length

  return (
    <div className="space-y-4 animate-fade-up">
      <IngestionManager onIngested={load} />
      {/* Header */}
      <div className="flex flex-wrap items-end gap-3 px-1">
        <h2 className="text-xl font-bold text-ink-900">ETL · Datasets</h2>
        <span className="text-xs text-ink-300 inline-flex items-center gap-1">
          <HardDrive className="w-3.5 h-3.5 text-mint-700" />
          {persistedCount} CSV(s) persisted on backend disk · stays across tab navigation & restarts
        </span>
        <div className="ml-auto flex items-center gap-2">
          {/* Inline notification in top-right (where the old timer was) */}
          <AnimatePresence>
            {notification && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-sm font-medium glass-strong max-w-xs"
              >
                {notification.kind === 'ok'   && <CheckCircle2 className="w-4 h-4 text-mint-700 shrink-0" />}
                {notification.kind === 'err'  && <XCircle      className="w-4 h-4 text-red-600 shrink-0" />}
                {notification.kind === 'info' && <RefreshCw    className="w-4 h-4 text-blue-500 shrink-0 animate-spin" />}
                <span className="truncate text-xs">{notification.text}</span>
                <button onClick={() => setNotif(null)} className="text-ink-300 hover:text-ink-700 shrink-0 ml-1">
                  <XCircle className="w-3.5 h-3.5" />
                </button>
              </motion.div>
            )}
          </AnimatePresence>
          {/* Last-run badge when no notification */}
          {lastRun && !processingFile && !notification && (
            <div className="text-xs bg-lavender-100 text-lavender-700 font-semibold px-3 py-1.5 rounded-full
                            flex items-center gap-1.5"
                 title={'Completed at ' + new Date(lastRun.finishedAt).toLocaleTimeString()}>
              <CheckCircle2 className="w-3.5 h-3.5" />
              Last run: {Math.round(lastRun.duration)}s
              <span className="text-ink-500 font-normal">· {fmtAgo(Date.now() - lastRun.finishedAt)}</span>
            </div>
          )}
          <button onClick={load} className="btn-secondary !py-1.5">
            <RefreshCw className={'w-4 h-4 ' + (busy ? 'animate-spin' : '')} />
            Reload
          </button>
        </div>
      </div>

      {/* Sub-tabs */}
      <div className="glass-strong p-1 inline-flex rounded-xl gap-1">
        <button onClick={() => setTab('existing')}
                className={'px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 ' +
                  (tab === 'existing' ? 'bg-mint-500 text-ink-900' : 'text-ink-500 hover:bg-white/60')}>
          <ListChecks className="w-4 h-4" />
          Existing datasets ({persistedCount})
        </button>
        <button onClick={() => setTab('upload')}
                className={'px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 ' +
                  (tab === 'upload' ? 'bg-orange-500 text-white' : 'text-ink-500 hover:bg-white/60')}
                style={tab === 'upload' ? { background: '#FFA552' } : undefined}>
          <UploadCloud className="w-4 h-4" />
          Upload new
        </button>
      </div>

      {/* EXISTING TAB */}
      {tab === 'existing' && (
        <GlassCard
          title="Available datasets on disk"
          subtitle="Click Run ETL on any file — no upload needed if it is already in the datasets/ folder."
          accent="#5EE6C8"
        >
          {!data ? (
            <div className="space-y-2">
              {[0,1,2].map(i => <div key={i} className="h-14 skeleton rounded-xl" />)}
            </div>
          ) : files.length === 0 ? (
            <div className="text-center py-8">
              <Database className="w-8 h-8 text-ink-300 mx-auto mb-2" />
              <p className="text-sm text-ink-500 mb-3">No CSVs found in the datasets folder yet.</p>
              <button onClick={() => setTab('upload')} className="btn-accent" style={{ background: '#FFA552' }}>
                <Upload className="w-4 h-4" /> Upload your first CSV
              </button>
            </div>
          ) : (
            <ul className="space-y-2">
              {files.map((f) => {
                const isProcessing = processingFile === f.filename
                const isDeleting   = deletingFile === f.filename
                const delDisabled  = isDeleting || isProcessing
                const fStatus      = fileStatus[f.filename]
                return (
                  <li key={f.filename}
                      className={'surface flex items-center gap-3 p-3 transition-all ' +
                        (isProcessing ? 'ring-2 ring-mint-500 shadow-card-hover' : 'hover:shadow-card-hover')}>
                    <FileText className="w-5 h-5 text-mint-700 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="font-medium text-ink-900 truncate">{f.filename}</div>
                      <div className="text-xs text-ink-300">
                        {f.source_key} · {fmtSize(f.size_bytes)} ·{' '}
                        {f.is_known ? 'recognized schema' : 'unknown schema'}
                      </div>
                    </div>

                    {/* ETL status badge */}
                    {fStatus && <StatusBadge status={fStatus.status} error={fStatus.error} />}

                    <button
                      onClick={(e) => { e.stopPropagation(); onDelete(f.filename) }}
                      disabled={delDisabled || !['household_power_consumption.csv','electric_power_consumption.csv'].includes(f.filename) === false}
                      className="btn-secondary !py-1.5 !px-3 hover:!bg-orange-300"
                      title="Delete from datasets folder">
                      {isDeleting
                        ? <RefreshCw className="w-4 h-4 animate-spin" />
                        : <Trash2 className="w-4 h-4" />}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </GlassCard>
      )}

      {/* UPLOAD TAB */}
      {tab === 'upload' && (
        <GlassCard
          title="Upload a new CSV"
          subtitle={'Allowed filenames: ' + (data?.allowed_filenames || []).join(' · ')}
          accent="#FFA552"
        >
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) onUpload(f) }}
            className="border-2 border-dashed border-orange-300/70 rounded-2xl p-8
                       flex flex-col items-center justify-center text-center bg-white/40"
          >
            <UploadCloud className="w-10 h-10 text-orange-500 mb-3" />
            <p className="text-sm text-ink-700 font-medium">Drag & drop a CSV here, or</p>
            <button onClick={() => fileInput.current?.click()}
                    className="btn-accent mt-3" style={{ background: '#FFA552' }}>
              <Upload className="w-4 h-4" /> Choose file
            </button>
            <input ref={fileInput} type="file" accept=".csv,.txt" hidden
                   onChange={(e) => onUpload(e.target.files?.[0])} />
            {progress > 0 && progress < 100 && (
              <div className="w-full mt-4 h-1 bg-mint-100 rounded-full overflow-hidden">
                <div className="h-full bg-orange-500" style={{ width: progress + '%' }} />
              </div>
            )}
            <p className="text-xs text-ink-300 mt-3">
              Files saved on the backend at: <code>{data?.data_dir}</code>
            </p>
            <p className="text-xs text-ink-300">
              After upload, go to the <b>Existing</b> tab and click <b>Run ETL</b>.
            </p>
          </div>
        </GlassCard>
      )}


    </div>
  )
}
