import type { IncidentReport, RemediationJob, SystemInfo } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const body = (await response.json()) as { detail?: string; error?: string }
      message = body.detail || body.error || message
    } catch {
      // Preserve HTTP status text when the body is not JSON.
    }
    throw new Error(message)
  }
  return (await response.json()) as T
}

export const api = {
  system: () => request<SystemInfo>('/system'),
  investigate: (query: string, namespace: string) =>
    request<IncidentReport>('/investigations', {
      method: 'POST',
      body: JSON.stringify({ query, namespace }),
    }),
  startRemediation: (query: string, namespace: string) =>
    request<RemediationJob>('/remediations', {
      method: 'POST',
      body: JSON.stringify({ query, namespace }),
    }),
  remediation: (jobId: string) => request<RemediationJob>(`/remediations/${jobId}`),
  decide: (jobId: string, approved: boolean, callId?: string | null) =>
    request<RemediationJob>(`/remediations/${jobId}/decision`, {
      method: 'POST',
      body: JSON.stringify({ approved, call_id: callId || null }),
    }),
}
