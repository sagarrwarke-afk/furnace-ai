import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getSensitivities,
  updateSensitivity,
  trainModel,
  listModels,
  activateModel,
} from '../api/client'
import type { SensitivityItem, TrainModelResponse, ModelItem } from '../types'

function f(v: number | null | undefined, d = 3): string {
  if (v == null) return '—'
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
      Loading…
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

  // Flatten all items for display
  const allItems = data.groups.flatMap(g => g.sensitivities)
  const params = [...new Set(allItems.map(i => `${i.parameter}|${i.sensitivity_type}`))]

  // Build column headers (groups)
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
                      <span className="text-[#4A4A4A]">—</span>
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

function ModelRegistry() {
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
    <div className="text-[#9E9E9E] text-sm py-4 text-center">Loading models…</div>
  )

  if (!data?.models.length) return (
    <p className="text-[#4A4A4A] text-sm italic py-4">No models trained yet.</p>
  )

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[#234060]">
            {['Model', 'Tech', 'Feed', 'Target', 'R² Test', 'MAPE%', 'Trained', 'Status', ''].map(h => (
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
                <td className="py-2.5 pr-3 text-[#D4D4D4] font-mono">
                  {r2 != null ? r2.toFixed(4) : '—'}
                </td>
                <td className="py-2.5 pr-3 text-[#D4D4D4] font-mono">
                  {mape != null ? mape.toFixed(2) : '—'}
                </td>
                <td className="py-2.5 pr-3 text-[#4A4A4A]">
                  {m.trained_at ? new Date(m.trained_at).toLocaleDateString() : '—'}
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

export default function SensitivityManager() {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [trainForm, setTrainForm] = useState({ technology: 'Lummus', feed_type: 'Ethane' })
  const [trainFile, setTrainFile] = useState<File | null>(null)
  const [trainResult, setTrainResult] = useState<TrainModelResponse | null>(null)
  const [trainError, setTrainError] = useState<string | null>(null)
  const [saveStatus, setSaveStatus] = useState<string | null>(null)

  const updateMutation = useMutation({
    mutationFn: ({ id, value }: { id: number; value: number }) => updateSensitivity({ id, value }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sensitivities'] })
      setSaveStatus('Saved')
      setTimeout(() => setSaveStatus(null), 2000)
    },
    onError: () => setSaveStatus('Save failed'),
  })

  const trainMutation = useMutation({
    mutationFn: () => {
      if (!trainFile) throw new Error('No file selected')
      return trainModel(trainFile, trainForm.technology, trainForm.feed_type)
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

      {/* Train New Model */}
      <div className="bg-[#001730] border border-[#234060] rounded-lg p-5">
        <h2 className="text-[#D4D4D4] font-semibold text-sm mb-4">Train New Soft Sensor Model</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
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
            </div>

            {/* CSV Upload */}
            <div>
              <label className="block text-xs text-[#9E9E9E] mb-1.5">Training Data (CSV)</label>
              <div
                className="border border-dashed border-[#234060] rounded-lg p-4 text-center cursor-pointer hover:border-[#00B4CC] transition-colors"
                onClick={() => fileRef.current?.click()}
              >
                {trainFile ? (
                  <div className="text-[#D4D4D4] text-sm">{trainFile.name}</div>
                ) : (
                  <div className="text-[#4A4A4A] text-sm">Click to select CSV file</div>
                )}
                <div className="text-[#4A4A4A] text-xs mt-1">
                  Cols: feed, shc, cot, cop, cit, feed_ethane_pct, feed_propane_pct, thickness, yield, tmt, conversion…
                </div>
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={e => setTrainFile(e.target.files?.[0] ?? null)}
              />
            </div>

            <button
              onClick={() => trainMutation.mutate()}
              disabled={!trainFile || trainMutation.isPending}
              className="w-full bg-[#00B4CC] hover:bg-[#009BB0] disabled:opacity-50 text-[#001E35] font-semibold py-2 rounded text-sm transition-colors"
            >
              {trainMutation.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                  Training…
                </span>
              ) : 'Train Model'}
            </button>

            {trainError && (
              <div className="bg-[#E30613]/10 border border-[#E30613]/40 rounded p-3 text-[#E30613] text-xs">
                {trainError}
              </div>
            )}
          </div>

          {/* Training results */}
          <div>
            {trainResult ? (
              <div className="space-y-3">
                <div className="text-[#22C55E] text-sm font-semibold">
                  Training complete — {trainResult.targets_trained.length} targets
                </div>
                <div className="text-xs text-[#4A4A4A]">
                  {trainResult.technology} {trainResult.feed_type}
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-[#234060]">
                        {['Target', 'R² Train', 'R² Test', 'MAE', 'MAPE%', 'N Train'].map(h => (
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
                            {m.mape_pct != null ? m.mape_pct.toFixed(2) : '—'}
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
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-32 text-[#4A4A4A] text-sm">
                Train a model to see accuracy metrics here
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Model Registry */}
      <div className="bg-[#001730] border border-[#234060] rounded-lg p-5">
        <h2 className="text-[#D4D4D4] font-semibold text-sm mb-4">Model Registry</h2>
        <ModelRegistry />
      </div>
    </div>
  )
}
