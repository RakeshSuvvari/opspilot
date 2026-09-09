import type { SystemInfo } from '../types'

export function SystemBar({ system }: { system: SystemInfo | null }) {
  const ok = system?.agent.status === 'ok'
  return (
    <div className="system-bar">
      <div className="brand-row">
        <div className="brand-mark">OP</div>
        <div>
          <div className="brand">OpsPilot</div>
          <div className="subtitle">Agentic Kubernetes Incident Response</div>
        </div>
      </div>
      <div className="system-pills">
        <span className={`pill ${ok ? 'pill-ok' : 'pill-warn'}`}>{ok ? 'Agent online' : 'Agent unavailable'}</span>
        {system?.agent.model && <span className="pill">{system.agent.model}</span>}
        {system?.agent.rag_enabled && <span className="pill">RAG</span>}
        {system?.agent.github_enabled && <span className="pill">GitHub</span>}
        {system?.agent.remediation_enabled && <span className="pill pill-action">HITL remediation</span>}
      </div>
    </div>
  )
}
