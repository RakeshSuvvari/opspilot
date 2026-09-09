import type { ChangeEvent, FormEvent } from 'react'

export type RunMode = 'investigate' | 'remediate'

interface Props {
  query: string
  namespace: string
  mode: RunMode
  busy: boolean
  remediationEnabled: boolean
  onQuery: (value: string) => void
  onNamespace: (value: string) => void
  onMode: (value: RunMode) => void
  onSubmit: () => void
}

export function InvestigationForm(props: Props) {
  const submit = (event: FormEvent) => {
    event.preventDefault()
    props.onSubmit()
  }

  return (
    <form className="query-card" onSubmit={submit}>
      <div className="form-row form-row-top">
        <div>
          <div className="eyebrow">Incident command</div>
          <h1>Investigate the cluster</h1>
        </div>
        <div className="mode-toggle" role="group" aria-label="Run mode">
          <button type="button" className={props.mode === 'investigate' ? 'active' : ''} onClick={() => props.onMode('investigate')}>
            Investigate
          </button>
          <button
            type="button"
            className={props.mode === 'remediate' ? 'active danger-mode' : ''}
            disabled={!props.remediationEnabled}
            onClick={() => props.onMode('remediate')}
          >
            Remediate
          </button>
        </div>
      </div>
      <textarea
        value={props.query}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => props.onQuery(event.target.value)}
        placeholder="Example: Diagnose why payment is restarting and identify the safest corrective action."
        rows={4}
        required
      />
      <div className="form-row">
        <label>
          Namespace
          <input value={props.namespace} onChange={(event: ChangeEvent<HTMLInputElement>) => props.onNamespace(event.target.value)} required />
        </label>
        <button className="primary-button" disabled={props.busy || props.query.trim().length < 3} type="submit">
          {props.busy ? 'Running…' : props.mode === 'remediate' ? 'Start remediation' : 'Run investigation'}
        </button>
      </div>
      {props.mode === 'remediate' && (
        <p className="form-note">Mutating Kubernetes actions remain paused until you approve the exact tool call and arguments.</p>
      )}
    </form>
  )
}
