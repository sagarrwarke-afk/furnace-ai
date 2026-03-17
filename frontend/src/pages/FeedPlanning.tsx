import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { runOptimizer, downloadOptResult } from '../api/client'
import type { OptimizeResponse, FurnaceOptResult } from '../types'

// ── Helpers ──────────────────────────────────────────────────────────────────

function f(v: number | null | undefined, d = 2): string {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  if (!isFinite(n)) return '—'
  return n.toFixed(d)
}

function fSign(v: number | null | undefined, d = 2): string {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  if (!isFinite(n)) return '—'
  return (n >= 0 ? '+' : '') + n.toFixed(d)
}

function signColor(v: number | null | undefined): string {
  if (v === null || v === undefined) return 'text-[#9E9E9E]'
  return Number(v) >= 0 ? 'text-[#00B4CC]' : 'text-[#E30613]'
}

// ── Input row helper ──────────────────────────────────────────────────────────

function InputRow({
  label,
  unit,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 0.5,
}: {
  label: string
  unit: string
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  step?: number
}) {
  return (
    <div className="flex items-center gap-3">
      <label className="text-[#9E9E9E] text-xs w-44 shrink-0">{label}</label>
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-24 rounded border border-[#234060] bg-[#1A2B3C] text-[#D4D4D4] text-sm px-2 py-1.5 text-right focus:outline-none focus:border-[#00B4CC]"
      />
      <span className="text-[#4A4A4A] text-xs">{unit}</span>
    </div>
  )
}

// ── KPI cards ─────────────────────────────────────────────────────────────────

function KPICard({
  label,
  value,
  unit,
  color = 'text-[#D4D4D4]',
  large = false,
}: {
  label: string
  value: string
  unit: string
  color?: string
  large?: boolean
}) {
  return (
    <div className="rounded border border-[#234060] bg-[#1E3347] p-4">
      <p className="text-[#9E9E9E] text-xs mb-1">{label}</p>
      <p className={`font-bold ${large ? 'text-3xl' : 'text-xl'} ${color}`}>{value}</p>
      <p className="text-[#4A4A4A] text-[10px] mt-0.5">{unit}</p>
    </div>
  )
}

// ── Per-furnace results table ─────────────────────────────────────────────────

function ResultsTable({ perFurnace }: { perFurnace: Record<string, FurnaceOptResult> }) {
  const rows = Object.entries(perFurnace).sort(([a], [b]) => a.localeCompare(b))

  return (
    <div className="overflow-x-auto rounded border border-[#234060]">
      <table className="text-xs min-w-full">
        <thead>
          <tr className="bg-[#1A2B3C]">
            {[
              'Furnace', 'Technology', 'Feed Type', 'Role',
              'Base Feed', 'Opt Feed', 'ΔFeed', 'ΔCOT', 'ΔSHC',
              'Eth. Gain (tpy)', 'Prop. Gain (tpy)',
              'Profit ($M/yr)', 'Uptime (days)',
            ].map((h) => (
              <th key={h} className="px-3 py-2 text-[#9E9E9E] whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([fid, r], i) => (
            <tr key={fid} className={i % 2 === 0 ? 'bg-[#001E35]' : 'bg-[#1A2B3C]'}>
              <td className="px-3 py-2 font-medium text-[#D4D4D4]">{fid}</td>
              <td className="px-3 py-2 text-[#9E9E9E]">{r.technology ?? '—'}</td>
              <td className="px-3 py-2 text-[#9E9E9E]">{r.feed_type ?? '—'}</td>
              <td className="px-3 py-2">
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                  r.role === 'protect' ? 'bg-[#4A3800]/40 text-[#F5C800]'
                  : r.role === 'receive_recycle' ? 'bg-[#003F6B]/40 text-[#00B4CC]'
                  : r.role === 'decoke' ? 'bg-[#4A1010]/40 text-[#E30613]'
                  : 'bg-[#1A2B3C] text-[#9E9E9E]'
                }`}>
                  {r.role ?? '—'}
                </span>
              </td>
              <td className="px-3 py-2 text-[#D4D4D4] text-right">{f(r.baseline_feed, 1)}</td>
              <td className="px-3 py-2 text-[#D4D4D4] text-right">{f(r.optFeed, 1)}</td>
              <td className={`px-3 py-2 text-right font-medium ${signColor(r.dFeed)}`}>{fSign(r.dFeed, 1)}</td>
              <td className={`px-3 py-2 text-right font-medium ${signColor(r.dc)}`}>{fSign(r.dc, 1)}</td>
              <td className={`px-3 py-2 text-right font-medium ${signColor(r.ds)}`}>{fSign(r.ds, 3)}</td>
              <td className={`px-3 py-2 text-right font-medium ${signColor(r.ethGain)}`}>{fSign(r.ethGain, 0)}</td>
              <td className={`px-3 py-2 text-right font-medium ${signColor(r.propGain)}`}>{fSign(r.propGain, 0)}</td>
              <td className={`px-3 py-2 text-right font-medium ${signColor(r.profitGain)}`}>{fSign(r.profitGain, 3)}</td>
              <td className={`px-3 py-2 text-right font-medium ${signColor(r.uptimeGain)}`}>{fSign(r.uptimeGain, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

const DEFAULT_FORM = {
  delta_fresh_ethane: 0,
  delta_fresh_propane: 0,
  ethane_feed_purity: 92,
  propane_feed_purity: 85,
  c2_splitter_load: 82,
}

export default function FeedPlanning() {
  const [form, setForm] = useState(DEFAULT_FORM)
  const [result, setResult] = useState<OptimizeResponse | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)

  const set = (key: keyof typeof DEFAULT_FORM) => (v: number) =>
    setForm((prev) => ({ ...prev, [key]: v }))

  const mutation = useMutation({
    mutationFn: () =>
      runOptimizer({ upload_id: 'latest', ...form }),
    onSuccess: (data) => {
      setResult(data)
      setApiError(null)
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? (err as Error)?.message
        ?? 'Optimization failed'
      setApiError(msg)
    },
  })

  const totals = result?.fleet_totals ?? {}

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Input panel */}
      <div className="rounded border border-[#234060] bg-[#1E3347] p-5">
        <h2 className="text-[#D4D4D4] font-semibold text-sm mb-4">Optimizer Inputs</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-10 gap-y-3">
          {/* Feed deltas */}
          <div className="space-y-3">
            <p className="text-[#9E9E9E] text-[11px] uppercase tracking-widest mb-2">Fresh Feed</p>
            <InputRow
              label="Extra Fresh Ethane"
              unit="t/hr"
              value={form.delta_fresh_ethane}
              onChange={set('delta_fresh_ethane')}
              min={0} max={30} step={0.5}
            />
            <InputRow
              label="Extra Fresh Propane"
              unit="t/hr"
              value={form.delta_fresh_propane}
              onChange={set('delta_fresh_propane')}
              min={0} max={30} step={0.5}
            />
          </div>

          {/* Process conditions */}
          <div className="space-y-3">
            <p className="text-[#9E9E9E] text-[11px] uppercase tracking-widest mb-2">Process Conditions</p>
            <InputRow
              label="Ethane Feed Purity"
              unit="%"
              value={form.ethane_feed_purity}
              onChange={set('ethane_feed_purity')}
              min={50} max={100} step={0.1}
            />
            <InputRow
              label="Propane Feed Purity"
              unit="%"
              value={form.propane_feed_purity}
              onChange={set('propane_feed_purity')}
              min={50} max={100} step={0.1}
            />
            <InputRow
              label="C2 Splitter Load"
              unit="%"
              value={form.c2_splitter_load}
              onChange={set('c2_splitter_load')}
              min={0} max={100} step={1}
            />
          </div>
        </div>

        {/* Action */}
        <div className="mt-5 flex items-center gap-4">
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="flex items-center gap-2 px-8 py-2.5 rounded bg-[#00B4CC] text-[#002147] font-bold text-sm hover:bg-[#33C8DE] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {mutation.isPending ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Optimizing...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                OPTIMIZE
              </>
            )}
          </button>
          {result && (
            <button
              onClick={() => downloadOptResult(result.run_id)}
              className="flex items-center gap-2 px-4 py-2.5 rounded border border-[#234060] text-[#00B4CC] text-sm hover:bg-[#003F6B]/30 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Download Excel
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {apiError && (
        <div className="flex items-start gap-3 p-4 rounded border border-[#E30613]/40 bg-[#4A1010]/30">
          <svg className="w-5 h-5 text-[#E30613] shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd" />
          </svg>
          <div>
            <p className="text-[#E30613] font-medium text-sm">Optimization Error</p>
            <p className="text-[#9E9E9E] text-xs mt-1">{apiError}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-5">
          {/* KPI cards */}
          <div>
            <h2 className="text-[#9E9E9E] text-xs font-semibold uppercase tracking-wider mb-3">
              Fleet Results — Run #{result.run_id}
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
              <KPICard
                label="Ethylene Gain"
                value={fSign(totals.ethGain, 0)}
                unit="tpy"
                color={signColor(totals.ethGain)}
              />
              <KPICard
                label="Propylene Gain"
                value={fSign(totals.propGain, 0)}
                unit="tpy"
                color={signColor(totals.propGain)}
              />
              <KPICard
                label="Uptime Gain"
                value={fSign(totals.uptimeGain, 1)}
                unit="days"
                color={signColor(totals.uptimeGain)}
              />
              <KPICard
                label="Gross Profit"
                value={fSign(totals.profitGain, 3)}
                unit="$M/yr"
                color={signColor(totals.profitGain)}
              />
              <KPICard
                label="CGC VHP Δ"
                value={fSign(totals.cgc_vhp_delta_tph, 2)}
                unit="t/hr VHP"
                color="text-[#9E9E9E]"
              />
              <KPICard
                label="C2S VHP Δ"
                value={fSign(totals.c2s_vhp_delta_tph, 2)}
                unit="t/hr VHP"
                color="text-[#9E9E9E]"
              />
              <KPICard
                label="NET PROFIT"
                value={fSign(totals.netProfit, 3)}
                unit="$M/yr"
                color={signColor(totals.netProfit)}
                large
              />
            </div>
          </div>

          {/* Per-furnace table */}
          <div>
            <h2 className="text-[#9E9E9E] text-xs font-semibold uppercase tracking-wider mb-3">
              Per-Furnace Actions
            </h2>
            <ResultsTable perFurnace={result.per_furnace} />
          </div>
        </div>
      )}
    </div>
  )
}
