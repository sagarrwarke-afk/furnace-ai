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
