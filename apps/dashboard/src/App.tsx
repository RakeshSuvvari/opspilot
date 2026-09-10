import { useCallback, useEffect, useState } from 'react'
import { api } from './lib/api'
import { ApprovalPanel } from './components/ApprovalPanel'
import { HistoryPanel } from './components/HistoryPanel'
import { InvestigationForm, type RunMode } from './components/InvestigationForm'
import { ReportView } from './components/ReportView'
import { SystemBar } from './components/SystemBar'
import type { IncidentReport, InvestigationHistoryItem, RemediationJob, SystemInfo } from './types'

const DEFAULT_QUERY = 'Find the unhealthy workload, determine the root cause, and support the conclusion with live evidence.'
type WorkspaceView = 'live' | 'history'

export default function App() {
  const [system, setSystem] = useState<SystemInfo | null>(null)
  const [query, setQuery] = useState(DEFAULT_QUERY)
  const [namespace, setNamespace] = useState('opspilot-demo')
  const [mode, setMode] = useState<RunMode>('investigate')
  const [view, setView] = useState<WorkspaceView>('live')
  const [busy, setBusy] = useState(false)
  const [deciding, setDeciding] = useState(false)
  const [report, setReport] = useState<IncidentReport | null>(null)
  const [job, setJob] = useState<RemediationJob | null>(null)
  const [history, setHistory] = useState<InvestigationHistoryItem[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refreshSystem = useCallback(async () => {
    try {
      setSystem(await api.system())
    } catch {
      setSystem(null)
    }
  }, [])

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      setHistory(await api.history(30))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load incident history')
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshSystem()
    const timer = window.setInterval(() => void refreshSystem(), 15000)
    return () => window.clearInterval(timer)
  }, [refreshSystem])

  useEffect(() => {
    if (view === 'history') void refreshHistory()
  }, [view, refreshHistory])

  useEffect(() => {
    if (!job || ['completed', 'failed', 'cancelled'].includes(job.status)) return
    let cancelled = false
    const poll = async () => {
      try {
        const next = await api.remediation(job.job_id)
        if (cancelled) return
        setJob(next)
        if (next.report) setReport(next.report)
        if (next.error) setError(next.error)
        if (!['completed', 'failed', 'cancelled'].includes(next.status)) {
          window.setTimeout(() => void poll(), next.status === 'awaiting_approval' ? 1500 : 1000)
        } else {
          setBusy(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to poll remediation job')
          setBusy(false)
        }
      }
    }
    const timer = window.setTimeout(() => void poll(), 500)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [job?.job_id])

  const submit = async () => {
    setError(null)
    setReport(null)
    setJob(null)
    setBusy(true)
    try {
      if (mode === 'investigate') {
        setReport(await api.investigate(query, namespace))
        setBusy(false)
      } else {
        setJob(await api.startRemediation(query, namespace))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
      setBusy(false)
    }
  }

  const decide = async (approved: boolean) => {
    if (!job?.pending_approval) return
    setDeciding(true)
    setError(null)
    try {
      const next = await api.decide(job.job_id, approved, job.pending_approval.call_id)
      setJob(next)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approval decision failed')
    } finally {
      setDeciding(false)
    }
  }

  const openHistory = async (investigationId: string) => {
    setSelectedHistoryId(investigationId)
    setError(null)
    try {
      const detail = await api.historyDetail(investigationId)
      setReport(detail.report)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to open investigation')
    }
  }

  const remediationEnabled = system?.agent.remediation_enabled === true
  const historyAvailable = system?.agent.history_available === true

  return (
    <main>
      <SystemBar system={system} />
      <div className="page-shell">
        <nav className="workspace-tabs" aria-label="OpsPilot workspace">
          <button type="button" className={view === 'live' ? 'active' : ''} onClick={() => { setView('live'); setSelectedHistoryId(null); setReport(null); setError(null) }}>
            Live investigation
          </button>
          <button type="button" className={view === 'history' ? 'active' : ''} onClick={() => { setView('history'); setSelectedHistoryId(null); setReport(null); setError(null) }}>
            Incident history
          </button>
          <span className={`history-health ${historyAvailable ? 'available' : ''}`}>
            {historyAvailable ? 'PostgreSQL history online' : 'History unavailable'}
          </span>
        </nav>

        {view === 'live' ? (
          <>
            <InvestigationForm
              query={query}
              namespace={namespace}
              mode={mode}
              busy={busy}
              remediationEnabled={remediationEnabled}
              onQuery={setQuery}
              onNamespace={setNamespace}
              onMode={setMode}
              onSubmit={() => void submit()}
            />

            {job && (
              <div className="job-strip">
                <span>Remediation job</span><code>{job.job_id}</code><strong>{job.status.replace('_', ' ')}</strong>
              </div>
            )}

            {job && <ApprovalPanel job={job} deciding={deciding} onDecision={(value) => void decide(value)} />}
            {error && <div className="error-banner">{error}</div>}
            {busy && !job?.pending_approval && <div className="loading-card"><span className="spinner" /> OpsPilot is collecting evidence and reasoning over the incident…</div>}
            {report && <ReportView report={report} />}
          </>
        ) : (
          <>
            {error && <div className="error-banner">{error}</div>}
            <HistoryPanel
              items={history}
              loading={historyLoading}
              selectedId={selectedHistoryId}
              onSelect={(id) => void openHistory(id)}
              onRefresh={() => void refreshHistory()}
            />
            {report && selectedHistoryId && <ReportView report={report} />}
          </>
        )}
      </div>
    </main>
  )
}
