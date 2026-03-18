import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { runWhatIf } from '../api/client'
import type { WhatIfResponse } from '../types'

const FURNACE_IDS = ['AF-01', 'AF-02', 'AF-03', 'AF-04', 'AF-05', 'AF-06', 'AF-07', 'AF-08']

const DEFAULT_FORM = {
  furnace_id: 'AF-01',
  delta_cot: 0,
  delta_shc: 0,
  delta_feed: 0,
  ethane_feed_purity: 92,
  propane_feed_purity: 85,
}

function f(v: number | null | undefined, d = 1): string {
  if (v == null) return '—'
  return v.toFixed(d)
}

function fDelta(v: number | null | undefined, d = 2): string {
  if (v == null) return '—'
  const s = v >= 0 ? '+' : ''
  return `${s}${v.toFixed(d)}`
}

function deltaColor(v: number | null | undefined, positiveGood = true): string {
  if (v == null || v === 0) return 'text-[#9E9E9E]'
  const good = positiveGood ? v > 0 : v < 0
  return good ? 'text-[#22C55E]' : 'text-[#E30613]'
}

function SliderInput({ label, unit, value, min, max, step, onChange }: {
  label: string; unit: string; value: number; min: number; max: number
  step: number; onChange: (v: number) => void
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-[#9E9E9E]">{label}</span>
        <span className="text-[#00B4CC] font-mono">
          {value >= 0 ? '+' : ''}{value} {unit}
        </span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="w-full h-1.5 bg-[#234060] rounded appearance-none cursor-pointer accent-[#00B4CC]"
      />
      <div className="flex justify-between text-[10px] text-[#4A4A4A]">
        <span>{min}{unit}</span><span>0</span><span>+{max}{unit}</span>
      </div>
    </div>
  )
}

function ResultRow({ label, baseline, predicted, delta, unit, positiveGood = true, decimals = 2 }: {
  label: string; baseline: number | null; predicted: number | null
  delta: number | null; unit: string; positiveGood?: boolean; decimals?: number
}) {
  return (
    <tr className="border-b border-[#234060] last:border-0">
      <td className="py-2.5 text-[#9E9E9E] text-sm">{label}</td>
      <td className="py-2.5 text-right text-[#D4D4D4] font-mono text-sm">{f(baseline, decimals)} {unit}</td>
      <td className="py-2.5 text-right text-[#D4D4D4] font-mono text-sm">{f(predicted, decimals)} {unit}</td>
      <td className={`py-2.5 text-right font-mono text-sm font-semibold ${deltaColor(delta, positiveGood)}`}>
        {fDelta(delta, decimals)} {unit}
      </td>
    </tr>
  )
}

export default function WhatIfSimulator() {
  const [form, setForm] = useState(DEFAULT_FORM)
  const [result, setResult] = useState<WhatIfResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const set = (key: keyof typeof DEFAULT_FORM) => (v: number | string) =>
    setForm(prev => ({ ...prev, [key]: v }))

  const mutation = useMutation({
    mutationFn: () => runWhatIf({ ...form, upload_id: 'latest' }),
    onSuccess: (data) => { setResult(data); setError(null) },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Simulation failed. Ensure data has been uploaded.'
      setError(msg)
      setResult(null)
    },
  })

  const handleReset = () => { setForm(DEFAULT_FORM); setResult(null); setError(null) }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Inputs */}
        <div className="bg-[#001730] border border-[#234060] rounded-lg p-5 space-y-5">
          <h2 className="text-[#D4D4D4] font-semibold text-sm">Simulation Inputs</h2>

          <div>
            <label className="block text-xs text-[#9E9E9E] mb-1.5">Furnace</label>
            <select
              value={form.furnace_id}
              onChange={e => set('furnace_id')(e.target.value)}
              className="w-full bg-[#1A2B3C] border border-[#234060] text-[#D4D4D4] rounded px-3 py-1.5 text-sm focus:outline-none focus:border-[#00B4CC]"
            >
              {FURNACE_IDS.map(id => <option key={id} value={id}>{id}</option>)}
            </select>
          </div>

          <SliderInput label="ΔCOT (Coil Outlet Temperature)" unit="°C"
            value={form.delta_cot} min={-5} max={5} step={0.5}
            onChange={v => set('delta_cot')(v)} />

          <SliderInput label="ΔSHC (Steam-to-Hydrocarbon)" unit=""
            value={form.delta_shc} min={-0.05} max={0.05} step={0.01}
            onChange={v => set('delta_shc')(v)} />

          <SliderInput label="ΔFeed Rate" unit="t/hr"
            value={form.delta_feed} min={-10} max={10} step={0.5}
            onChange={v => set('delta_feed')(v)} />

          <div className="grid grid-cols-2 gap-3 pt-1 border-t border-[#234060]">
            <div>
              <label className="block text-xs text-[#9E9E9E] mb-1.5">Ethane Purity %</label>
              <input type="number" min={50} max={100} step={0.1}
                value={form.ethane_feed_purity}
                onChange={e => set('ethane_feed_purity')(parseFloat(e.target.value))}
                className="w-full bg-[#1A2B3C] border border-[#234060] text-[#D4D4D4] rounded px-3 py-1.5 text-sm focus:outline-none focus:border-[#00B4CC]"
              />
            </div>
            <div>
              <label className="block text-xs text-[#9E9E9E] mb-1.5">Propane Purity %</label>
              <input type="number" min={50} max={100} step={0.1}
                value={form.propane_feed_purity}
                onChange={e => set('propane_feed_purity')(parseFloat(e.target.value))}
                className="w-full bg-[#1A2B3C] border border-[#234060] text-[#D4D4D4] rounded px-3 py-1.5 text-sm focus:outline-none focus:border-[#00B4CC]"
              />
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="flex-1 bg-[#00B4CC] hover:bg-[#009BB0] disabled:opacity-50 text-[#001E35] font-semibold py-2 rounded text-sm transition-colors"
            >
              {mutation.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                  Simulating…
                </span>
              ) : 'Run Simulation'}
            </button>
            <button onClick={handleReset}
              className="px-4 py-2 border border-[#234060] text-[#9E9E9E] hover:text-[#D4D4D4] hover:border-[#4A4A4A] rounded text-sm transition-colors">
              Reset
            </button>
          </div>

          {error && (
            <div className="bg-[#E30613]/10 border border-[#E30613]/40 rounded p-3 text-[#E30613] text-xs">{error}</div>
          )}
        </div>

        {/* Results */}
        <div className="bg-[#001730] border border-[#234060] rounded-lg p-5">
          <h2 className="text-[#D4D4D4] font-semibold text-sm mb-4">Predicted Outcomes</h2>

          {!result && !mutation.isPending && (
            <div className="flex flex-col items-center justify-center h-48 text-[#4A4A4A] text-sm">
              <svg className="w-10 h-10 mb-2 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Adjust inputs and run simulation to see predictions
            </div>
          )}

          {mutation.isPending && (
            <div className="flex flex-col items-center justify-center h-48 text-[#9E9E9E] text-sm gap-3">
              <svg className="w-8 h-8 animate-spin text-[#00B4CC]" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              Running simulation…
            </div>
          )}

          {result && (
            <div className="space-y-4">
              <div className="flex items-center gap-3 text-xs flex-wrap">
                <span className="text-[#4A4A4A]">{result.furnace_id} · {result.technology} {result.feed_type}</span>
                {result.prediction_source === 'model' ? (
                  <span className="text-[#00B4CC] bg-[#00B4CC]/10 px-2 py-0.5 rounded" title="Predictions from trained ML model (per-coil)">
                    Predicted by: {result.algorithm ?? 'ML Model'}
                  </span>
                ) : (
                  <span className="text-[#9E9E9E] bg-[#234060] px-2 py-0.5 rounded" title="Predictions from linear sensitivity coefficients">
                    Predicted by: Sensitivities
                  </span>
                )}
                {result.warnings?.tmt_alarm && (
                  <span className="text-[#E30613] bg-[#E30613]/10 px-2 py-0.5 rounded">TMT ALARM</span>
                )}
                {!result.warnings?.tmt_alarm && result.warnings?.tmt_warning && (
                  <span className="text-[#F5C800] bg-[#F5C800]/10 px-2 py-0.5 rounded">TMT Warning</span>
                )}
              </div>

              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#234060]">
                    <th className="text-left text-xs text-[#4A4A4A] pb-2 font-normal">Parameter</th>
                    <th className="text-right text-xs text-[#4A4A4A] pb-2 font-normal">Baseline</th>
                    <th className="text-right text-xs text-[#4A4A4A] pb-2 font-normal">Predicted</th>
                    <th className="text-right text-xs text-[#4A4A4A] pb-2 font-normal">Delta</th>
                  </tr>
                </thead>
                <tbody>
                  <ResultRow label="Ethylene Yield" unit="%" decimals={2}
                    baseline={result.baseline.yield} predicted={result.predicted.yield}
                    delta={result.deltas.yield} positiveGood={true} />
                  <ResultRow label="Conversion" unit="%" decimals={2}
                    baseline={result.baseline.conversion} predicted={result.predicted.conversion}
                    delta={result.deltas.conversion} positiveGood={true} />
                  <ResultRow label="Propylene" unit="%" decimals={2}
                    baseline={result.baseline.propylene} predicted={result.predicted.propylene}
                    delta={result.deltas.propylene} positiveGood={true} />
                  <ResultRow label="TMT Max" unit="°C" decimals={1}
                    baseline={result.baseline.tmt_max} predicted={result.predicted.tmt_max}
                    delta={result.deltas.tmt_max} positiveGood={false} />
                  <ResultRow label="Run Life" unit="d" decimals={0}
                    baseline={result.baseline.run_days} predicted={result.predicted.run_days}
                    delta={result.deltas.run_days} positiveGood={true} />
                  <ResultRow label="Net Margin" unit="M$/yr" decimals={3}
                    baseline={result.baseline.net_margin_M} predicted={result.predicted.net_margin_M}
                    delta={result.deltas.profit_M} positiveGood={true} />
                </tbody>
              </table>

              <div className="grid grid-cols-2 gap-3 pt-3 border-t border-[#234060]">
                {[
                  { label: 'Yield Δ', value: result.deltas.yield, unit: '%', pos: true, d: 2 },
                  { label: 'Run Life Δ', value: result.deltas.run_days, unit: 'd', pos: true, d: 0 },
                  { label: 'TMT Δ', value: result.deltas.tmt_max, unit: '°C', pos: false, d: 1 },
                  { label: 'Profit Δ', value: result.deltas.profit_M, unit: 'M$/yr', pos: true, d: 3 },
                ].map(({ label, value, unit, pos, d }) => (
                  <div key={label} className="bg-[#1A2B3C] rounded p-3">
                    <div className="text-xs text-[#9E9E9E] mb-1">{label}</div>
                    <div className={`font-mono text-lg font-semibold ${deltaColor(value, pos)}`}>
                      {fDelta(value, d)}{unit}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
