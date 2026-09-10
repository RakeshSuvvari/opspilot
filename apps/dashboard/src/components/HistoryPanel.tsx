import type { InvestigationHistoryItem } from '../types'

interface Props {
  items: InvestigationHistoryItem[]
  loading: boolean
  selectedId?: string | null
  onSelect: (investigationId: string) => void
  onRefresh: () => void
}

function formatTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

export function HistoryPanel({ items, loading, selectedId, onSelect, onRefresh }: Props) {
  return (
    <section className="panel history-panel">
      <div className="panel-title history-title">
        <div>
          <div className="eyebrow">PostgreSQL history</div>
          <h2>Incident history</h2>
        </div>
        <button className="secondary-button" type="button" onClick={onRefresh} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {!loading && items.length === 0 && (
        <div className="history-empty">
          No persisted investigations yet. Run an investigation after <code>make db-init</code> to populate history.
        </div>
      )}

      <div className="history-list">
        {items.map((item) => (
          <button
            className={`history-row ${selectedId === item.investigation_id ? 'selected' : ''}`}
            type="button"
            key={item.investigation_id}
            onClick={() => onSelect(item.investigation_id)}
          >
            <div className="history-row-top">
              <span className={`status status-${item.status}`}>{item.status.replace('_', ' ')}</span>
              <span className="history-mode">{item.run_mode}</span>
              <time>{formatTime(item.completed_at)}</time>
            </div>
            <strong>{item.summary}</strong>
            <p>{item.root_cause}</p>
            <div className="history-meta">
              <code>{item.investigation_id}</code>
              <span>{item.namespace}</span>
              <span>{item.evidence_score}/100 evidence</span>
              <span>{Math.round(item.elapsed_ms / 1000)}s</span>
              <span>{item.total_tokens.toLocaleString()} tokens</span>
            </div>
          </button>
        ))}
      </div>
    </section>
  )
}
