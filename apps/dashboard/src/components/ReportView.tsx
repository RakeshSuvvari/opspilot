import type { CSSProperties } from 'react'
import type { IncidentReport } from '../types'

function number(value: number) {
  return new Intl.NumberFormat().format(value)
}

function duration(ms: number) {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}

export function ReportView({ report }: { report: IncidentReport }) {
  return (
    <div className="report-stack">
      <section className="hero-report">
        <div>
          <div className="eyebrow">{report.metrics.investigation_id}</div>
          <div className="status-line">
            <span className={`status status-${report.status}`}>{report.status.replace('_', ' ')}</span>
            <span className="confidence">{report.confidence} confidence</span>
          </div>
          <h2>{report.summary}</h2>
          <p className="root-cause"><strong>Root cause:</strong> {report.root_cause}</p>
        </div>
        <div className="score-ring" style={{ '--score': `${report.assessment.evidence_score}%` } as CSSProperties}>
          <div><strong>{report.assessment.evidence_score}</strong><span>Evidence</span></div>
        </div>
      </section>

      <section className="metric-grid">
        <div className="metric"><span>Elapsed</span><strong>{duration(report.metrics.elapsed_ms)}</strong></div>
        <div className="metric"><span>Tokens</span><strong>{number(report.metrics.total_tokens)}</strong></div>
        <div className="metric"><span>Tool calls</span><strong>{report.metrics.tool_call_count}</strong></div>
        <div className="metric"><span>Live sources</span><strong>{report.assessment.live_source_count}</strong></div>
      </section>

      <div className="two-column">
        <section className="panel">
          <div className="panel-title"><h3>Evidence</h3><span>{report.evidence.length}</span></div>
          <div className="evidence-list">
            {report.evidence.map((item, index) => (
              <article className="evidence-item" key={`${item.resource}-${index}`}>
                <div className="evidence-meta"><span>{item.source}</span><code>{item.resource}</code></div>
                <p>{item.observation}</p>
                <small>{item.supports}</small>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-title"><h3>Incident timeline</h3><span>{report.timeline.length}</span></div>
          <ol className="timeline">
            {report.timeline.map((entry, index) => (
              <li key={`${entry.timestamp}-${index}`}>
                <time>{new Date(entry.timestamp).toLocaleString()}</time>
                <p>{entry.event}</p>
              </li>
            ))}
          </ol>
        </section>
      </div>

      {report.change_correlation && (
        <section className="panel correlation-panel">
          <div className="panel-title"><h3>Deployment / source correlation</h3></div>
          <div className="correlation-grid">
            <div><span>Repository</span><strong>{report.change_correlation.repository || '—'}</strong></div>
            <div><span>Current revision</span><code>{report.change_correlation.current_revision?.slice(0, 12) || '—'}</code></div>
            <div><span>Previous revision</span><code>{report.change_correlation.previous_revision?.slice(0, 12) || '—'}</code></div>
            <div><span>Pull request</span><strong>{report.change_correlation.pull_request_number ? `#${report.change_correlation.pull_request_number}` : '—'}</strong></div>
          </div>
          <p>{report.change_correlation.summary}</p>
          <small>{report.change_correlation.causal_link}</small>
        </section>
      )}

      <div className="two-column">
        <section className="panel">
          <div className="panel-title"><h3>Recommended remediation</h3></div>
          <ul className="check-list">{report.remediation.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
        <section className="panel">
          <div className="panel-title"><h3>Follow-up checks</h3></div>
          <ul className="check-list">{report.follow_up_checks.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
      </div>

      {report.remediation_actions.length > 0 && (
        <section className="panel">
          <div className="panel-title"><h3>Remediation actions</h3><span>{report.remediation_actions.length}</span></div>
          <div className="action-list">
            {report.remediation_actions.map((action, index) => (
              <div className="action-row" key={`${action.call_id || action.tool_name}-${index}`}>
                <div><strong>{action.tool_name}</strong><code>{action.resource}</code></div>
                <span className={`action-status ${action.approved ? 'approved' : 'rejected'}`}>{action.status}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="panel compact-panel">
        <div className="panel-title"><h3>Tools used</h3><span>{report.tools_used.length}</span></div>
        <div className="tool-list">{report.tools_used.map((tool) => <code key={tool}>{tool}</code>)}</div>
      </section>
    </div>
  )
}
