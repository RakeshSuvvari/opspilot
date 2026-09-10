export type IncidentStatus = 'healthy' | 'degraded' | 'incident' | 'insufficient_evidence'
export type Confidence = 'low' | 'medium' | 'high'
export type RemediationJobStatus = 'queued' | 'running' | 'awaiting_approval' | 'completed' | 'failed' | 'cancelled'

export interface EvidenceItem {
  source: string
  resource: string
  observation: string
  supports: string
}

export interface TimelineEvent {
  timestamp: string
  event: string
}

export interface ChangeCorrelation {
  repository?: string | null
  current_revision?: string | null
  previous_revision?: string | null
  commit_sha?: string | null
  pull_request_number?: number | null
  summary: string
  causal_link: string
}

export interface ApprovalRequest {
  call_id?: string | null
  tool_name: string
  arguments: Record<string, unknown>
  risk: string
  reason: string
}

export interface RemediationAction {
  call_id?: string | null
  tool_name: string
  resource: string
  arguments: Record<string, unknown>
  approved: boolean
  status: string
  result?: unknown
}

export interface EvidenceAssessment {
  evidence_score: number
  confidence_score: number
  confidence: Confidence
  model_confidence: Confidence
  live_source_count: number
  knowledge_used: boolean
  change_intelligence_used: boolean
  corroborated: boolean
  reasons: string[]
}

export interface RunMetrics {
  investigation_id: string
  started_at: string
  completed_at: string
  elapsed_ms: number
  model_requests: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  tool_call_count: number
  unique_tool_count: number
  approval_requests: number
  approved_actions: number
  rejected_actions: number
}

export interface IncidentReport {
  namespace: string
  status: IncidentStatus
  affected_resources: string[]
  summary: string
  root_cause: string
  confidence: Confidence
  evidence: EvidenceItem[]
  timeline: TimelineEvent[]
  remediation: string[]
  follow_up_checks: string[]
  change_correlation?: ChangeCorrelation | null
  tools_used: string[]
  assessment: EvidenceAssessment
  metrics: RunMetrics
  remediation_actions: RemediationAction[]
}

export interface RemediationJob {
  job_id: string
  status: RemediationJobStatus
  query: string
  namespace: string
  created_at: string
  updated_at: string
  pending_approval?: ApprovalRequest | null
  report?: IncidentReport | null
  error?: string | null
}

export interface SystemInfo {
  gateway: { status: string; version: string }
  agent: {
    status: string
    version?: string
    model?: string
    phase?: number
    rag_enabled?: boolean
    github_enabled?: boolean
    remediation_enabled?: boolean
    history_enabled?: boolean
    history_available?: boolean
  }
  tools: string[]
}

export interface InvestigationHistoryItem {
  investigation_id: string
  job_id?: string | null
  query: string
  namespace: string
  run_mode: 'investigate' | 'remediate'
  status: IncidentStatus
  confidence: Confidence
  summary: string
  root_cause: string
  evidence_score: number
  completed_at: string
  elapsed_ms: number
  total_tokens: number
  tool_call_count: number
}

export interface InvestigationHistoryDetail extends InvestigationHistoryItem {
  report: IncidentReport
}
