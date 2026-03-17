// ── Upload / Snapshots ───────────────────────────────────────────────────────

export interface UploadResponse {
  upload_id: number
  filename: string
  rows_inserted: number
  uploaded_at: string
  preview: Record<string, unknown>[]
}

export interface Snapshot {
  upload_id: number
  filename: string
  uploaded_by: string
  uploaded_at: string
  row_count: number
  validation_ok: boolean
}

// ── Fleet Overview ────────────────────────────────────────────────────────────

export interface FleetKPIs {
  total_feed_tph: number
  total_ethylene_tph: number
  total_propylene_tph: number
  online_count: number
  protect_count: number
  decoke_count: number
  total_furnaces: number
}

export interface FurnaceEntry {
  furnace_id: string
  feed_rate: number | null
  cot: number | null
  shc: number | null
  tmt_max: number | null
  yield: number | null
  conversion: number | null
  propylene: number | null
  coking_rate: number | null
  feed_valve_pct: number | null
  fgv_pct: number | null
  damper_pct: number | null
  sec: number | null
  run_days_elapsed: number | null
  run_days_total: number | null
  status: string
  feed_ethane_pct: number | null
  feed_propane_pct: number | null
  technology: string
  feed_type: string
  ethylene_tph: number
  propylene_tph: number
  rank: number
}

export interface FleetOverview {
  upload_id: number
  kpis: FleetKPIs
  ethane_furnaces: FurnaceEntry[]
  propane_furnaces: FurnaceEntry[]
}

// ── Furnace Detail ────────────────────────────────────────────────────────────

export interface ConstraintStatus {
  value: number | null
  limit?: number
  alarm?: number
  warning?: number
  ok: boolean
}

export interface FurnaceDetail {
  furnace_id: string
  feed_rate: number | null
  cot: number | null
  shc: number | null
  cop: number | null
  cit: number | null
  tmt_max: number | null
  yield: number | null
  conversion: number | null
  coking_rate: number | null
  propylene: number | null
  feed_valve_pct: number | null
  fgv_pct: number | null
  damper_pct: number | null
  sec: number | null
  run_days_elapsed: number | null
  run_days_total: number | null
  status: string
  feed_ethane_pct: number | null
  feed_propane_pct: number | null
  technology: string
  feed_type: string
  design_capacity: number | null
  coke_thickness: number[]
  constraints: {
    feed_valve: ConstraintStatus
    fgv: ConstraintStatus
    damper: ConstraintStatus
    tmt_max: ConstraintStatus
  }
}

// ── What-If Simulator ─────────────────────────────────────────────────────────

export interface WhatIfRequest {
  furnace_id: string
  upload_id: string
  delta_cot: number
  delta_shc: number
  delta_feed: number
  ethane_feed_purity: number
  propane_feed_purity: number
}

export interface WhatIfResponse {
  furnace_id: string
  technology: string
  feed_type: string
  baseline: {
    cot: number | null
    shc: number | null
    feed_rate: number | null
    yield: number | null
    conversion: number | null
    tmt_max: number | null
    propylene: number | null
    run_days: number | null
    coking_rate: number | null
    sec: number | null
    net_margin_M: number | null
  }
  predicted: {
    cot: number | null
    shc: number | null
    feed_rate: number | null
    yield: number | null
    conversion: number | null
    tmt_max: number | null
    propylene: number | null
    run_days: number | null
    coking_rate: number | null
    sec: number | null
    net_margin_M: number | null
  }
  deltas: {
    yield: number | null
    conversion: number | null
    tmt_max: number | null
    propylene: number | null
    run_days: number | null
    profit_M: number | null
    ethylene_tpy: number | null
  }
  warnings: {
    tmt_warning: boolean
    tmt_alarm: boolean
  }
}

// ── Sensitivity Manager ───────────────────────────────────────────────────────

export interface SensitivityItem {
  id: number
  technology: string
  feed_type: string
  parameter: string
  sensitivity_type: string
  value: number
  unit: string | null
  source: string | null
  updated_at: string | null
}

export interface SensitivityGroup {
  technology: string
  feed_type: string
  sensitivities: SensitivityItem[]
}

export interface SensitivityListResponse {
  groups: SensitivityGroup[]
}

export interface SensitivityUpdateRequest {
  id: number
  value: number
}

// ── Model Training & Registry ─────────────────────────────────────────────────

export interface TargetMetrics {
  r2_train: number
  r2_test: number
  mae: number
  mape_pct: number | null
  n_train: number
  n_test: number
}

export interface TrainModelResponse {
  model_ids: number[]
  technology: string
  feed_type: string
  targets_trained: string[]
  metrics: Record<string, TargetMetrics>
  extracted_sensitivities: Record<string, number>
}

export interface ModelItem {
  id: number
  model_name: string
  technology: string
  feed_type: string
  target: string
  algorithm: string
  hyperparams: Record<string, unknown> | null
  metrics: Record<string, unknown> | null
  active: boolean
  trained_at: string | null
  created_at: string | null
}

export interface ModelListResponse {
  models: ModelItem[]
}

export interface ActivateModelResponse {
  id: number
  model_name: string
  active: boolean
  sensitivities_copied: number
}

// ── Config ────────────────────────────────────────────────────────────────────

export interface EconomicParamItem {
  id: number
  param_name: string
  value: number
  unit: string | null
  updated_at: string | null
}

export interface EconomicParamsResponse {
  params: EconomicParamItem[]
}

export interface ConstraintItem {
  id: number
  constraint_name: string
  limit_value: number
  unit: string | null
  updated_at: string | null
}

export interface ConstraintsResponse {
  constraints: ConstraintItem[]
}

// ── Optimizer ─────────────────────────────────────────────────────────────────

export interface OptimizeRequest {
  upload_id: string
  delta_fresh_ethane: number
  delta_fresh_propane: number
  ethane_feed_purity: number
  propane_feed_purity: number
  c2_splitter_load: number
}

export interface FurnaceOptResult {
  furnace_id?: string
  technology?: string
  feed_type?: string
  role?: string
  baseline_feed?: number
  optFeed?: number
  dFeed?: number
  dc?: number
  ds?: number
  ethGain?: number
  propGain?: number
  profitGain?: number
  uptimeGain?: number
  runDelta?: number
  feed_eth_pct?: number
  feed_prop_pct?: number
}

export interface FleetTotals {
  ethGain?: number
  propGain?: number
  profitGain?: number
  netProfit?: number
  uptimeGain?: number
  energy_cost_M?: number
  cgc_vhp_delta_tph?: number
  c2s_vhp_delta_tph?: number
}

export interface OptimizeResponse {
  run_id: number
  snapshot_id: number
  run_at: string
  per_furnace: Record<string, FurnaceOptResult>
  fleet_totals: FleetTotals
  config_used?: Record<string, unknown>
}
