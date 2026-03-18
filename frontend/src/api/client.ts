import axios from 'axios'
import type {
  UploadResponse,
  Snapshot,
  FleetOverview,
  OptimizeRequest,
  OptimizeResponse,
  FurnaceDetail,
  WhatIfRequest,
  WhatIfResponse,
  SensitivityListResponse,
  SensitivityUpdateRequest,
  TrainModelResponse,
  ModelListResponse,
  ActivateModelResponse,
  EconomicParamsResponse,
  ConstraintsResponse,
  BenchmarkResponse,
} from '../types'

const api = axios.create({
  baseURL: 'http://localhost:8000',
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

// ── Furnace Detail ────────────────────────────────────────────────────────────

export async function getFurnaceDetail(furnaceId: string, uploadId = 'latest'): Promise<FurnaceDetail> {
  const res = await api.get<FurnaceDetail>(`/api/furnace/${furnaceId}`, {
    params: { upload_id: uploadId },
  })
  return res.data
}

// ── What-If ───────────────────────────────────────────────────────────────────

export async function runWhatIf(req: WhatIfRequest): Promise<WhatIfResponse> {
  const res = await api.post<WhatIfResponse>('/api/whatif', req)
  return res.data
}

// ── Sensitivity ───────────────────────────────────────────────────────────────

export async function getSensitivities(): Promise<SensitivityListResponse> {
  const res = await api.get<SensitivityListResponse>('/api/sensitivity')
  return res.data
}

export async function updateSensitivity(req: SensitivityUpdateRequest): Promise<void> {
  await api.put('/api/sensitivity', req)
}

// ── Training & Models ─────────────────────────────────────────────────────────

export async function trainModel(
  file: File,
  technology: string,
  feedType: string,
  algorithm: string = 'Ridge',
): Promise<TrainModelResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('technology', technology)
  form.append('feed_type', feedType)
  form.append('algorithm', algorithm)
  const res = await api.post<TrainModelResponse>('/api/train-model', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
  return res.data
}

export async function benchmarkModels(
  file: File,
  technology: string,
  feedType: string,
  algorithms: string[],
): Promise<BenchmarkResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('technology', technology)
  form.append('feed_type', feedType)
  form.append('algorithms', algorithms.join(','))
  const res = await api.post<BenchmarkResponse>('/api/benchmark-models', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,  // 5 min — benchmarking can be slow
  })
  return res.data
}

export async function getAvailableAlgorithms(): Promise<{ algorithms: string[] }> {
  const res = await api.get<{ algorithms: string[] }>('/api/available-algorithms')
  return res.data
}

export async function listModels(): Promise<ModelListResponse> {
  const res = await api.get<ModelListResponse>('/api/models')
  return res.data
}

export async function activateModel(modelId: number): Promise<ActivateModelResponse> {
  const res = await api.put<ActivateModelResponse>(`/api/models/${modelId}/activate`)
  return res.data
}

// ── Config ────────────────────────────────────────────────────────────────────

export async function getEconomics(): Promise<EconomicParamsResponse> {
  const res = await api.get<EconomicParamsResponse>('/api/config/economics')
  return res.data
}

export async function updateEconomics(params: { param_name: string; value: number }[]): Promise<EconomicParamsResponse> {
  const res = await api.put<EconomicParamsResponse>('/api/config/economics', { params })
  return res.data
}

export async function getConstraints(): Promise<ConstraintsResponse> {
  const res = await api.get<ConstraintsResponse>('/api/config/constraints')
  return res.data
}

export async function updateConstraints(constraints: { constraint_name: string; limit_value: number }[]): Promise<ConstraintsResponse> {
  const res = await api.put<ConstraintsResponse>('/api/config/constraints', { constraints })
  return res.data
}
