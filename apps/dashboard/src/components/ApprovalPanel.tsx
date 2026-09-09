import type { RemediationJob } from '../types'

interface Props {
  job: RemediationJob
  deciding: boolean
  onDecision: (approved: boolean) => void
}

export function ApprovalPanel({ job, deciding, onDecision }: Props) {
  const approval = job.pending_approval
  if (job.status !== 'awaiting_approval' || !approval) return null

  return (
    <section className="approval-panel">
      <div className="approval-heading">
        <div>
          <div className="eyebrow">Human approval required</div>
          <h2>{approval.tool_name}</h2>
        </div>
        <span className={`risk-badge risk-${approval.risk.toLowerCase()}`}>{approval.risk} risk</span>
      </div>
      <p>{approval.reason}</p>
      <pre>{JSON.stringify(approval.arguments, null, 2)}</pre>
      <div className="approval-actions">
        <button disabled={deciding} className="secondary-button" onClick={() => onDecision(false)}>Reject</button>
        <button disabled={deciding} className="danger-button" onClick={() => onDecision(true)}>Approve exact action</button>
      </div>
    </section>
  )
}
