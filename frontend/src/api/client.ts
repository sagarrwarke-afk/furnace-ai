import axios from 'axios'
import type {
  UploadResponse,
  Snapshot,
  FleetOverview,
  OptimizeRequest,
  OptimizeResponse,
} from '../types'

const api = axios.create({
  baseURL: 'http://localhost:8001',
  timeout: 60000,
})

// ── Upload ───────────────────────────────────────────────────────────────────

export async function downloadTemplate(): Promise<void> {
  const res = await api.get('/api/upload/template', { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([res.data]))
  const a = document.createElement('a')
  a.href = url
  a.download = 'furnace_template.csv'
  a.click()
  window.URL.revokeObjectURL(url)
}

export async function uploadCsv(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await api.post<UploadResponse>('/api/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function listSnapshots(): Promise<Snapshot[]> {
  const res = await api.get<Snapshot[]>('/api/snapshots')
  return res.data
}

// ── Fleet ────────────────────────────────────────────────────────────────────

export async function getFleet(uploadId = 'latest'): Promise<FleetOverview> {
  const res = await api.get<FleetOverview>('/api/fleet', {
    params: { upload_id: uploadId },
  })
  return res.data
}

// ── Optimizer ─────────────────────────────────────────────────────────────────

export async function runOptimizer(req: OptimizeRequest): Promise<OptimizeResponse> {
  const res = await api.post<OptimizeResponse>('/api/optimize', req)
  return res.data
}

export async function downloadOptResult(runId: number): Promise<void> {
  const res = await api.get(`/api/optimize/${runId}/download`, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(new Blob([res.data]))
  const a = document.createElement('a')
  a.href = url
  a.download = `optimizer_run_${runId}.xlsx`
  a.click()
  window.URL.revokeObjectURL(url)
}
