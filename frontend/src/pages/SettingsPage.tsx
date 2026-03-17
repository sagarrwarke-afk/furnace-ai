import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getEconomics, updateEconomics, getConstraints, updateConstraints } from '../api/client'
import type { EconomicParamItem, ConstraintItem } from '../types'

const ECON_LABELS: Record<string, string> = {
  ethylene_price: 'Ethylene Price',
  propylene_price: 'Propylene Price',
  ethane_feed_cost: 'Ethane Feed Cost',
  propane_feed_cost: 'Propane Feed Cost',
  fuel_gas_cost: 'Fuel Gas Cost',
  decoke_cost: 'Decoke Cost',
  vhp_steam_cost: 'VHP Steam Cost',
}

const CONSTRAINT_LABELS: Record<string, string> = {
  feed_valve: 'Feed Valve',
  fgv: 'FGV Opening',
  damper: 'Damper Opening',
  tmt_alarm: 'TMT Alarm',
  tmt_warning: 'TMT Warning',
  c2_splitter_max: 'C2 Splitter Max Load',
  cgc_suction_max: 'CGC Suction Pressure Max',
}

function SaveButton({ onClick, isPending, saved }: {
  onClick: () => void
  isPending: boolean
  saved: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={isPending}
      className="flex items-center gap-2 px-4 py-1.5 bg-[#00B4CC] hover:bg-[#009BB0] disabled:opacity-50 text-[#001E35] font-semibold rounded text-sm transition-colors"
    >
      {isPending ? (
        <>
          <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
          Saving…
        </>
      ) : saved ? (
        <>
          <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
          Saved
        </>
      ) : 'Save Changes'}
    </button>
  )
}

function EconomicsSection() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['economics'],
    queryFn: getEconomics,
  })

  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (data) {
      const init: Record<string, string> = {}
      data.params.forEach(p => { init[p.param_name] = String(p.value) })
      setDrafts(init)
    }
  }, [data])

  const mutation = useMutation({
    mutationFn: () => {
      const params = Object.entries(drafts).map(([param_name, v]) => ({
        param_name,
        value: parseFloat(v),
      }))
      return updateEconomics(params)
    },
    onSuccess: () => {
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
  })

  if (isLoading) return <div className="text-[#9E9E9E] text-sm py-4">Loading economics…</div>
  if (error) return <div className="text-[#E30613] text-sm py-4">Failed to load economic parameters.</div>

  return (
    <div className="bg-[#001730] border border-[#234060] rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-[#D4D4D4] font-semibold text-sm">Economic Parameters</h2>
          <p className="text-[#4A4A4A] text-xs mt-0.5">Used by the fleet optimizer profit calculation</p>
        </div>
        <SaveButton onClick={() => mutation.mutate()} isPending={mutation.isPending} saved={saved} />
      </div>

      <table className="w-full">
        <thead>
          <tr className="border-b border-[#234060]">
            <th className="text-left text-xs text-[#4A4A4A] py-2 font-normal">Parameter</th>
            <th className="text-left text-xs text-[#4A4A4A] py-2 font-normal w-36">Value</th>
            <th className="text-left text-xs text-[#4A4A4A] py-2 font-normal w-20">Unit</th>
            <th className="text-left text-xs text-[#4A4A4A] py-2 font-normal">Last Updated</th>
          </tr>
        </thead>
        <tbody>
          {data?.params.map((p, idx) => (
            <tr
              key={p.param_name}
              className={`border-b border-[#234060]/50 ${idx % 2 === 0 ? 'bg-[#001730]' : 'bg-[#1A2B3C]/30'}`}
            >
              <td className="py-3 text-sm text-[#D4D4D4]">
                {ECON_LABELS[p.param_name] ?? p.param_name}
              </td>
              <td className="py-3">
                <input
                  type="number"
                  step="any"
                  value={drafts[p.param_name] ?? ''}
                  onChange={e => setDrafts(prev => ({ ...prev, [p.param_name]: e.target.value }))}
                  className="w-32 bg-[#1A2B3C] border border-[#234060] text-[#D4D4D4] rounded px-2 py-1 text-sm font-mono focus:outline-none focus:border-[#00B4CC]"
                />
              </td>
              <td className="py-3 text-xs text-[#9E9E9E]">{p.unit ?? ''}</td>
              <td className="py-3 text-xs text-[#4A4A4A]">
                {p.updated_at ? new Date(p.updated_at).toLocaleString() : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {mutation.isError && (
        <div className="mt-3 text-[#E30613] text-xs">Failed to save. Check values and try again.</div>
      )}
    </div>
  )
}

function ConstraintsSection() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['constraints'],
    queryFn: getConstraints,
  })

  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (data) {
      const init: Record<string, string> = {}
      data.constraints.forEach(c => { init[c.constraint_name] = String(c.limit_value) })
      setDrafts(init)
    }
  }, [data])

  const mutation = useMutation({
    mutationFn: () => {
      const constraints = Object.entries(drafts).map(([constraint_name, v]) => ({
        constraint_name,
        limit_value: parseFloat(v),
      }))
      return updateConstraints(constraints)
    },
    onSuccess: () => {
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
  })

  if (isLoading) return <div className="text-[#9E9E9E] text-sm py-4">Loading constraints…</div>
  if (error) return <div className="text-[#E30613] text-sm py-4">Failed to load constraint limits.</div>

  return (
    <div className="bg-[#001730] border border-[#234060] rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-[#D4D4D4] font-semibold text-sm">Constraint Limits</h2>
          <p className="text-[#4A4A4A] text-xs mt-0.5">Equipment safety and process limits used by optimizer</p>
        </div>
        <SaveButton onClick={() => mutation.mutate()} isPending={mutation.isPending} saved={saved} />
      </div>

      <table className="w-full">
        <thead>
          <tr className="border-b border-[#234060]">
            <th className="text-left text-xs text-[#4A4A4A] py-2 font-normal">Constraint</th>
            <th className="text-left text-xs text-[#4A4A4A] py-2 font-normal w-36">Limit</th>
            <th className="text-left text-xs text-[#4A4A4A] py-2 font-normal w-20">Unit</th>
            <th className="text-left text-xs text-[#4A4A4A] py-2 font-normal">Last Updated</th>
          </tr>
        </thead>
        <tbody>
          {data?.constraints.map((c, idx) => (
            <tr
              key={c.constraint_name}
              className={`border-b border-[#234060]/50 ${idx % 2 === 0 ? 'bg-[#001730]' : 'bg-[#1A2B3C]/30'}`}
            >
              <td className="py-3 text-sm text-[#D4D4D4]">
                {CONSTRAINT_LABELS[c.constraint_name] ?? c.constraint_name}
              </td>
              <td className="py-3">
                <input
                  type="number"
                  step="any"
                  value={drafts[c.constraint_name] ?? ''}
                  onChange={e => setDrafts(prev => ({ ...prev, [c.constraint_name]: e.target.value }))}
                  className="w-32 bg-[#1A2B3C] border border-[#234060] text-[#D4D4D4] rounded px-2 py-1 text-sm font-mono focus:outline-none focus:border-[#00B4CC]"
                />
              </td>
              <td className="py-3 text-xs text-[#9E9E9E]">{c.unit ?? ''}</td>
              <td className="py-3 text-xs text-[#4A4A4A]">
                {c.updated_at ? new Date(c.updated_at).toLocaleString() : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {mutation.isError && (
        <div className="mt-3 text-[#E30613] text-xs">Failed to save. Check values and try again.</div>
      )}
    </div>
  )
}

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <EconomicsSection />
      <ConstraintsSection />
    </div>
  )
}
