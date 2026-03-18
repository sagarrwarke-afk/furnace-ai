import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getSensitivities,
  updateSensitivity,
  trainModel,
  listModels,
  activateModel,
  benchmarkModels,
  getAvailableAlgorithms,
} from '../api/client'
import type {
  SensitivityItem,
  TrainModelResponse,
  BenchmarkResponse,
} from '../types'

function f(v: number | null | undefined, d = 3): string {
  if (v == null) return '\u2014'
  return v.toFixed(d)
}

function EditableCell({ item, onSave }: {
  item: SensitivityItem
  onSave: (id: number, value: number) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(String(item.value))

  const commit = () => {
    const v = parseFloat(draft)
    if (!isNaN(v) && v !== item.value) onSave(item.id, v)
    setEditing(false)
  }

  if (editing) {
    return (
      <input
        autoFocus
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') setEditing(false) }}
        className="w-24 bg-[#001E35] border border-[#00B4CC] text-[#D4D4D4] rounded px-1.5 py-0.5 text-xs font-mono focus:outline-none"
      />
    )
  }

  return (
    <span
      onClick={() => { setDraft(String(item.value)); setEditing(true) }}
      className="cursor-pointer hover:text-[#00B4CC] font-mono text-xs border-b border-dashed border-[#234060] hover:border-[#00B4CC] transition-colors"
      title="Click to edit"
    >
      {f(item.value)}
    </span>
  )
}

function SensitivityTable({ onSave }: { onSave: (id: number, value: number) => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['sensitivities'],
    queryFn: getSensitivities,
  })

  if (isLoading) return (
    <div className="flex items-center gap-2 text-[#9E9E9E] py-8 justify-center text-sm">
      <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
      </svg>
      Loading...
    </div>
  )

  if (error) return (
    <div className="bg-[#E30613]/10 border border-[#E30613]/40 rounded p-4 text-[#E30613] text-sm">
      Failed to load sensitivities.
    </div>
  )

  if (!data?.groups.length) return (
    <p className="text-[#4A4A4A] text-sm italic py-4">No sensitivity data found.</p>
  )

  const allItems = data.groups.flatMap(g => g.sensitivities)
  const params = [...new Set(allItems.map(i => `${i.parameter}|${i.sensitivity_type}`))]
  const groups = data.groups

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[#234060]">
            <th className="text-left text-[#4A4A4A] py-2 pr-4 font-normal w-40">Parameter</th>
            <th className="text-left text-[#4A4A4A] py-2 pr-3 font-normal w-24">Type</th>
            {groups.map(g => (
              <th key={`${g.technology}-${g.feed_type}`} className="text-right text-[#4A4A4A] py-2 px-3 font-normal">
                {g.technology} {g.feed_type}
              </th>
            ))}
            <th className="text-left text-[#4A4A4A] py-2 pl-3 font-normal">Unit</th>
          </tr>
        </thead>
        <tbody>
          {params.map((paramKey, idx) => {
            const [parameter, sensitivity_type] = paramKey.split('|')
            const rowItems = groups.map(g =>
              g.sensitivities.find(s => s.parameter === parameter && s.sensitivity_type === sensitivity_type)
            )
            const unit = rowItems.find(Boolean)?.unit ?? ''
            return (
              <tr
                key={paramKey}
                className={`border-b border-[#234060]/50 ${idx % 2 === 0 ? 'bg-[#001730]' : 'bg-[#1A2B3C]/30'}`}
              >
                <td className="py-2.5 pr-4 text-[#D4D4D4]">{parameter}</td>
                <td className="py-2.5 pr-3 text-[#4A4A4A]">{sensitivity_type}</td>
                {rowItems.map((item, gi) => (
                  <td key={gi} className="py-2.5 px-3 text-right">
                    {item ? (
                      <div className="flex items-center justify-end gap-1.5">
                        <EditableCell item={item} onSave={onSave} />
                        {item.source === 'model' && (
                          <span className="text-[#00B4CC] text-[9px] opacity-60" title="Extracted from model">M</span>
                        )}
                      </div>
                    ) : (
                      <span className="text-[#4A4A4A]">{'\u2014'}</span>
                    )}
                  </td>
                ))}
                <td className="py-2.5 pl-3 text-[#4A4A4A]">{unit}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ModelRegistryTable() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['models'],
    queryFn: listModels,
  })

  const activateMutation = useMutation({
    mutationFn: (id: number) => activateModel(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['models'] })
      qc.invalidateQueries({ queryKey: ['sensitivities'] })
    },
  })

  if (isLoading) return (
    <div className="text-[#9E9E9E] text-sm py-4 text-center">Loading models...</div>
  )

  if (!data?.models.length) return (
    <p className="text-[#4A4A4A] text-sm italic py-4">No models trained yet.</p>
  )

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[#234060]">
            {['Model', 'Tech', 'Feed', 'Target', 'Algorithm', 'R\u00B2 Test', 'MAPE%', 'Trained', 'Status', ''].map(h => (
              <th key={h} className="text-left text-[#4A4A4A] py-2 pr-3 font-normal">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.models.map((m, idx) => {
            const metrics = m.metrics as Record<string, number> | null
            const r2 = metrics?.r2_test
            const mape = metrics?.mape_pct
            return (
              <tr
                key={m.id}
                className={`border-b border-[#234060]/50 ${idx % 2 === 0 ? 'bg-[#001730]' : 'bg-[#1A2B3C]/30'}`}
              >
                <td className="py-2.5 pr-3 text-[#D4D4D4] font-mono">{m.model_name}</td>
                <td className="py-2.5 pr-3 text-[#9E9E9E]">{m.technology}</td>
                <td className="py-2.5 pr-3 text-[#9E9E9E]">{m.feed_type}</td>
                <td className="py-2.5 pr-3 text-[#9E9E9E]">{m.target}</td>
                <td className="py-2.5 pr-3 text-[#9E9E9E]">{m.algorithm}</td>
                <td className="py-2.5 pr-3 text-[#D4D4D4] font-mono">
                  {r2 != null ? r2.toFixed(4) : '\u2014'}
                </td>
                <td className="py-2.5 pr-3 text-[#D4D4D4] font-mono">
                  {mape != null ? mape.toFixed(2) : '\u2014'}
                </td>
                <td className="py-2.5 pr-3 text-[#4A4A4A]">
                  {m.trained_at ? new Date(m.trained_at).toLocaleDateString() : '\u2014'}
                </td>
                <td className="py-2.5 pr-3">
                  {m.active ? (
                    <span className="text-[#00B4CC] text-[10px] bg-[#00B4CC]/10 px-1.5 py-0.5 rounded">Active</span>
                  ) : (
                    <span className="text-[#4A4A4A] text-[10px]">Inactive</span>
                  )}
                </td>
                <td className="py-2.5">
                  {!m.active && (
                    <button
                      onClick={() => activateMutation.mutate(m.id)}
                      disabled={activateMutation.isPending}
                      className="text-[#00B4CC] hover:text-[#009BB0] text-[10px] disabled:opacity-50 transition-colors"
                    >
                      Activate
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Benchmark Results Table
// ---------------------------------------------------------------------------

function BenchmarkResultsPanel({ result }: { result: BenchmarkResponse }) {
  const TARGETS = ['yield_c2h4', 'tmt', 'coking_rate', 'conversion', 'propylene']
  const TARGET_LABELS: Record<string, string> = {
    yield_c2h4: 'Yield',
    tmt: 'TMT',
    coking_rate: 'Coking',
    conversion: 'Conv.',
    propylene: 'Prop.',
  }

  return (
    <div className="space-y-4">
      {/* Grid analysis */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(result.grid_analysis).map(([variable, n]) => (
          <span key={variable} className="text-[10px] bg-[#1A2B3C] text-[#9E9E9E] px-2 py-1 rounded">
            {variable}: {n} levels
          </span>
        ))}
        <span className="text-[10px] bg-[#234060] text-[#4A4A4A] px-2 py-1 rounded">
          {result.n_rows.toLocaleString()} rows
        </span>
      </div>

      {/* Algorithm comparison table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[#234060]">
              <th className="text-left text-[#4A4A4A] py-2 pr-3 font-normal">Algorithm</th>
              {TARGETS.map(t => (
                <th key={t} className="text-right text-[#4A4A4A] py-2 px-2 font-normal">
                  R{'\u00B2'} {TARGET_LABELS[t] ?? t}
                </th>
              ))}
              <th className="text-right text-[#4A4A4A] py-2 px-2 font-normal">Interp. R{'\u00B2'}</th>
              <th className="text-right text-[#4A4A4A] py-2 px-2 font-normal">Score</th>
              <th className="text-center text-[#4A4A4A] py-2 pl-2 font-normal"></th>
            </tr>
          </thead>
          <tbody>
            {result.algorithms.map((algo, idx) => {
              const isRec = algo.recommended
              return (
                <tr
                  key={algo.algorithm}
                  className={`border-b border-[#234060]/50 ${
                    isRec
                      ? 'bg-[#00B4CC]/5 border-l-2 border-l-[#00B4CC]'
                      : idx % 2 === 0
                        ? 'bg-[#001730]'
                        : 'bg-[#1A2B3C]/30'
                  }`}
                >
                  <td className="py-2.5 pr-3 text-[#D4D4D4] font-medium">
                    {algo.algorithm}
                    {isRec && (
                      <span className="ml-2 text-[#00B4CC] text-[9px]" title="Recommended">
                        {'\u2605'}
                      </span>
                    )}
                  </td>
                  {TARGETS.map(t => {
                    const m = algo.metrics[t]
                    const r2 = m?.r2
                    return (
                      <td key={t} className="py-2.5 px-2 text-right font-mono text-[#D4D4D4]">
                        {r2 != null ? r2.toFixed(4) : '\u2014'}
                      </td>
                    )
                  })}
                  <td className="py-2.5 px-2 text-right font-mono">
                    <span className={algo.interpolation_r2 != null && algo.interpolation_r2 > 0.9
                      ? 'text-[#22C55E]'
                      : algo.interpolation_r2 != null && algo.interpolation_r2 > 0.7
                        ? 'text-[#F5C800]'
                        : 'text-[#E30613]'
                    }>
                      {algo.interpolation_r2 != null ? algo.interpolation_r2.toFixed(4) : '\u2014'}
                    </span>
                  </td>
                  <td className="py-2.5 px-2 text-right font-mono text-[#00B4CC] font-semibold">
                    {algo.overall_score.toFixed(4)}
                  </td>
                  <td className="py-2.5 pl-2 text-center">
                    {isRec && (
                      <span className="text-[#00B4CC] bg-[#00B4CC]/10 px-2 py-0.5 rounded text-[10px]">
                        Best
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Recommendation */}
      <div className="bg-[#00B4CC]/5 border border-[#00B4CC]/30 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[#00B4CC] text-sm font-semibold">
            {'\u2605'} Recommended: {result.recommended_algorithm}
          </span>
        </div>
        <p className="text-[#9E9E9E] text-xs leading-relaxed">
          {result.recommendation_reason}
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function SensitivityManager() {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)

  // Form state
  const [trainForm, setTrainForm] = useState({ technology: 'Lummus', feed_type: 'Ethane' })
  const [trainFile, setTrainFile] = useState<File | null>(null)
  const [saveStatus, setSaveStatus] = useState<string | null>(null)

  // Algorithm selection
  const [selectedAlgorithms, setSelectedAlgorithms] = useState<string[]>([])

  // Benchmark state
  const [benchmarkResult, setBenchmarkResult] = useState<BenchmarkResponse | null>(null)
  const [benchmarkError, setBenchmarkError] = useState<string | null>(null)

  // Train state
  const [trainAlgorithm, setTrainAlgorithm] = useState<string>('Ridge')
  const [trainResult, setTrainResult] = useState<TrainModelResponse | null>(null)
  const [trainError, setTrainError] = useState<string | null>(null)

  // Fetch available algorithms
  const { data: algoData } = useQuery({
    queryKey: ['available-algorithms'],
    queryFn: getAvailableAlgorithms,
  })

  // Default: all algorithms checked
  useEffect(() => {
    if (algoData?.algorithms && selectedAlgorithms.length === 0) {
      setSelectedAlgorithms([...algoData.algorithms])
    }
  }, [algoData])

  const updateMutation = useMutation({
    mutationFn: ({ id, value }: { id: number; value: number }) => updateSensitivity({ id, value }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sensitivities'] })
      setSaveStatus('Saved')
      setTimeout(() => setSaveStatus(null), 2000)
    },
    onError: () => setSaveStatus('Save failed'),
  })

  const benchmarkMutation = useMutation({
    mutationFn: () => {
      if (!trainFile) throw new Error('No file selected')
      if (selectedAlgorithms.length === 0) throw new Error('Select at least one algorithm')
      return benchmarkModels(trainFile, trainForm.technology, trainForm.feed_type, selectedAlgorithms)
    },
    onSuccess: (data) => {
      setBenchmarkResult(data)
      setBenchmarkError(null)
      // Pre-fill train algorithm with recommendation
      setTrainAlgorithm(data.recommended_algorithm)
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Benchmark failed. Check CSV format and algorithm selection.'
      setBenchmarkError(msg)
      setBenchmarkResult(null)
    },
  })

  const trainMutation = useMutation({
    mutationFn: () => {
      if (!trainFile) throw new Error('No file selected')
      return trainModel(trainFile, trainForm.technology, trainForm.feed_type, trainAlgorithm)
    },
    onSuccess: (data) => {
      setTrainResult(data)
      setTrainError(null)
      qc.invalidateQueries({ queryKey: ['models'] })
      qc.invalidateQueries({ queryKey: ['sensitivities'] })
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Training failed. Check CSV format.'
      setTrainError(msg)
      setTrainResult(null)
    },
  })

  const toggleAlgorithm = (algo: string) => {
    setSelectedAlgorithms(prev =>
      prev.includes(algo) ? prev.filter(a => a !== algo) : [...prev, algo]
    )
  }

  return (
    <div className="space-y-6">
      {/* Sensitivities table */}
      <div className="bg-[#001730] border border-[#234060] rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-[#D4D4D4] font-semibold text-sm">Sensitivity Coefficients</h2>
            <p className="text-[#4A4A4A] text-xs mt-0.5">Click any value to edit inline. Changes save automatically.</p>
          </div>
          {saveStatus && (
            <span className={`text-xs px-2 py-1 rounded ${saveStatus === 'Saved' ? 'text-[#22C55E] bg-[#22C55E]/10' : 'text-[#E30613] bg-[#E30613]/10'}`}>
              {saveStatus}
            </span>
          )}
        </div>
        <SensitivityTable onSave={(id, value) => updateMutation.mutate({ id, value })} />
      </div>

      {/* ============================================================ */}
      {/* Model Benchmark & Training (Two-step flow) */}
      {/* ============================================================ */}
      <div className="bg-[#001730] border border-[#234060] rounded-lg p-5">
        <h2 className="text-[#D4D4D4] font-semibold text-sm mb-1">Soft Sensor Model Setup</h2>
        <p className="text-[#4A4A4A] text-xs mb-5">
          Step 1: Upload simulation data and benchmark algorithms. Step 2: Train and activate the best model.
        </p>

        <div className="space-y-5">
          {/* Top row: Technology + Feed + File */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-[#9E9E9E] mb-1.5">Technology</label>
              <select
                value={trainForm.technology}
                onChange={e => setTrainForm(p => ({ ...p, technology: e.target.value }))}
                className="w-full bg-[#1A2B3C] border border-[#234060] text-[#D4D4D4] rounded px-3 py-1.5 text-sm focus:outline-none focus:border-[#00B4CC]"
              >
                <option value="Lummus">Lummus</option>
                <option value="Technip">Technip</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-[#9E9E9E] mb-1.5">Feed Type</label>
              <select
                value={trainForm.feed_type}
                onChange={e => setTrainForm(p => ({ ...p, feed_type: e.target.value }))}
                className="w-full bg-[#1A2B3C] border border-[#234060] text-[#D4D4D4] rounded px-3 py-1.5 text-sm focus:outline-none focus:border-[#00B4CC]"
              >
                <option value="Ethane">Ethane</option>
                <option value="Propane">Propane</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-[#9E9E9E] mb-1.5">Simulation Data (CSV)</label>
              <div
                className="border border-dashed border-[#234060] rounded px-3 py-1.5 text-center cursor-pointer hover:border-[#00B4CC] transition-colors"
                onClick={() => fileRef.current?.click()}
              >
                {trainFile ? (
                  <span className="text-[#D4D4D4] text-sm">{trainFile.name}</span>
                ) : (
                  <span className="text-[#4A4A4A] text-sm">Click to select CSV</span>
                )}
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={e => {
                  setTrainFile(e.target.files?.[0] ?? null)
                  setBenchmarkResult(null)
                  setTrainResult(null)
                }}
              />
            </div>
          </div>

          {/* Algorithm checkboxes */}
          <div>
            <label className="block text-xs text-[#9E9E9E] mb-2">Algorithms to Benchmark</label>
            <div className="flex flex-wrap gap-3">
              {(algoData?.algorithms ?? ['Ridge', 'RandomForest', 'GradientBoosting', 'XGBoost', 'LightGBM']).map(algo => (
                <label key={algo} className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={selectedAlgorithms.includes(algo)}
                    onChange={() => toggleAlgorithm(algo)}
                    className="w-3.5 h-3.5 rounded border-[#234060] bg-[#1A2B3C] text-[#00B4CC] focus:ring-[#00B4CC] focus:ring-offset-0 cursor-pointer"
                  />
                  <span className="text-sm text-[#9E9E9E] group-hover:text-[#D4D4D4] transition-colors">
                    {algo}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Step 1: Benchmark button */}
          <button
            onClick={() => benchmarkMutation.mutate()}
            disabled={!trainFile || selectedAlgorithms.length === 0 || benchmarkMutation.isPending}
            className="bg-[#234060] hover:bg-[#2A5080] disabled:opacity-50 text-[#D4D4D4] font-semibold py-2 px-6 rounded text-sm transition-colors"
          >
            {benchmarkMutation.isPending ? (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                Benchmarking {selectedAlgorithms.length} algorithm{selectedAlgorithms.length > 1 ? 's' : ''}...
              </span>
            ) : (
              `Benchmark ${selectedAlgorithms.length} Algorithm${selectedAlgorithms.length > 1 ? 's' : ''}`
            )}
          </button>

          {benchmarkError && (
            <div className="bg-[#E30613]/10 border border-[#E30613]/40 rounded p-3 text-[#E30613] text-xs">
              {benchmarkError}
            </div>
          )}

          {/* Benchmark Results */}
          {benchmarkResult && (
            <div className="border-t border-[#234060] pt-5">
              <h3 className="text-[#D4D4D4] font-semibold text-sm mb-4">
                Benchmark Results: {benchmarkResult.technology} {benchmarkResult.feed_type}
              </h3>
              <BenchmarkResultsPanel result={benchmarkResult} />

              {/* Step 2: Train & Activate */}
              <div className="mt-5 pt-5 border-t border-[#234060]">
                <h3 className="text-[#D4D4D4] font-semibold text-sm mb-3">
                  Train Production Model
                </h3>
                <div className="flex items-end gap-4">
                  <div className="flex-1 max-w-xs">
                    <label className="block text-xs text-[#9E9E9E] mb-1.5">Algorithm</label>
                    <select
                      value={trainAlgorithm}
                      onChange={e => setTrainAlgorithm(e.target.value)}
                      className="w-full bg-[#1A2B3C] border border-[#234060] text-[#D4D4D4] rounded px-3 py-1.5 text-sm focus:outline-none focus:border-[#00B4CC]"
                    >
                      {benchmarkResult.algorithms.map(a => (
                        <option key={a.algorithm} value={a.algorithm}>
                          {a.algorithm}
                          {a.recommended ? ' (Recommended)' : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    onClick={() => trainMutation.mutate()}
                    disabled={trainMutation.isPending}
                    className="bg-[#00B4CC] hover:bg-[#009BB0] disabled:opacity-50 text-[#001E35] font-semibold py-2 px-6 rounded text-sm transition-colors"
                  >
                    {trainMutation.isPending ? (
                      <span className="flex items-center gap-2">
                        <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                        </svg>
                        Training...
                      </span>
                    ) : (
                      `Train & Save ${trainAlgorithm}`
                    )}
                  </button>
                </div>

                {trainError && (
                  <div className="mt-3 bg-[#E30613]/10 border border-[#E30613]/40 rounded p-3 text-[#E30613] text-xs">
                    {trainError}
                  </div>
                )}

                {trainResult && (
                  <div className="mt-4 space-y-3">
                    <div className="text-[#22C55E] text-sm font-semibold flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      Training complete {'\u2014'} {trainResult.algorithm} model, {trainResult.targets_trained.length} targets
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-[#234060]">
                            {['Target', 'R\u00B2 Train', 'R\u00B2 Test', 'MAE', 'MAPE%', 'N Train'].map(h => (
                              <th key={h} className="text-left text-[#4A4A4A] py-1.5 pr-2 font-normal">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(trainResult.metrics).map(([target, m]) => (
                            <tr key={target} className="border-b border-[#234060]/50">
                              <td className="py-1.5 pr-2 text-[#D4D4D4]">{target}</td>
                              <td className="py-1.5 pr-2 font-mono text-[#D4D4D4]">{m.r2_train.toFixed(4)}</td>
                              <td className="py-1.5 pr-2 font-mono text-[#00B4CC]">{m.r2_test.toFixed(4)}</td>
                              <td className="py-1.5 pr-2 font-mono text-[#9E9E9E]">{m.mae.toFixed(3)}</td>
                              <td className="py-1.5 pr-2 font-mono text-[#9E9E9E]">
                                {m.mape_pct != null ? m.mape_pct.toFixed(2) : '\u2014'}
                              </td>
                              <td className="py-1.5 pr-2 text-[#4A4A4A]">{m.n_train}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {Object.keys(trainResult.extracted_sensitivities).length > 0 && (
                      <div className="text-xs text-[#9E9E9E]">
                        {Object.keys(trainResult.extracted_sensitivities).length} sensitivities extracted from model
                      </div>
                    )}
                    <p className="text-xs text-[#4A4A4A]">
                      Go to Model Registry below to activate this model for production use.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Model Registry */}
      <div className="bg-[#001730] border border-[#234060] rounded-lg p-5">
        <h2 className="text-[#D4D4D4] font-semibold text-sm mb-4">Model Registry</h2>
        <ModelRegistryTable />
      </div>
    </div>
  )
}
