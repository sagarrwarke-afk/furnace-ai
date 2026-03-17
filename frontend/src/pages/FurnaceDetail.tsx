import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getFurnaceDetail } from '../api/client'
import type { FurnaceDetail, ConstraintStatus } from '../types'

const FURNACE_IDS = ['AF-01', 'AF-02', 'AF-03', 'AF-04', 'AF-05', 'AF-06', 'AF-07', 'AF-08']

function f(v: number | null | undefined, d = 1): string {
  if (v == null) return '—'
  return v.toFixed(d)
}

function statusColors(status: string) {
  if (status.includes('decoke')) return { bg: 'bg-[#E30613]/20', text: 'text-[#E30613]', dot: 'bg-[#E30613]' }
  if (status.includes('protect')) return { bg: 'bg-[#F5C800]/20', text: 'text-[#F5C800]', dot: 'bg-[#F5C800]' }
  return { bg: 'bg-[#00B4CC]/20', text: 'text-[#00B4CC]', dot: 'bg-[#00B4CC]' }
}

function ConstraintBar({ label, value, limit, warning, alarm, unit }: {
  label: string
  value: number | null
  limit?: number
  warning?: number
  alarm?: number
  unit: string
}) {
  const maxVal = alarm ?? limit ?? 100
  const pct = value != null ? Math.min((value / maxVal) * 100, 100) : 0
  const isAlarm = alarm != null && value != null && value >= alarm
  const isWarn = warning != null && value != null && value >= warning && !isAlarm
  const color = isAlarm ? 'bg-[#E30613]' : isWarn ? 'bg-[#F5C800]' : 'bg-[#00B4CC]'

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-[#9E9E9E]">{label}</span>
        <span className={isAlarm ? 'text-[#E30613]' : isWarn ? 'text-[#F5C800]' : 'text-[#D4D4D4]'}>
          {f(value, 1)}{unit}
          {limit != null && <span className="text-[#4A4A4A] ml-1">/ {limit}{unit}</span>}
        </span>
      </div>
      <div className="h-2 bg-[#001730] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {warning != null && (
        <div className="flex gap-3 text-[10px] text-[#4A4A4A]">
          {warning != null && <span>Warn: {warning}{unit}</span>}
          {alarm != null && <span>Alarm: {alarm}{unit}</span>}
        </div>
      )}
    </div>
  )
}

function CokeChart({ thickness }: { thickness: number[] }) {
  const maxVal = Math.max(...thickness, 1)
  const coils = thickness.map((v, i) => ({ label: `C${i + 1}`, value: v }))

  return (
    <div className="space-y-2">
      {coils.map(({ label, value }) => {
        const pct = (value / maxVal) * 100
        const color = value > 8 ? 'bg-[#E30613]' : value > 5 ? 'bg-[#F5C800]' : 'bg-[#00B4CC]'
        return (
          <div key={label} className="flex items-center gap-2">
            <span className="text-[#9E9E9E] text-xs w-6 shrink-0">{label}</span>
            <div className="flex-1 h-4 bg-[#001730] rounded overflow-hidden">
              <div className={`h-full rounded ${color} transition-all`} style={{ width: `${pct}%` }} />
            </div>
            <span className="text-[#D4D4D4] text-xs w-10 text-right shrink-0">{f(value, 1)} mm</span>
          </div>
        )
      })}
    </div>
  )
}

export default function FurnaceDetailPage() {
  const [selectedId, setSelectedId] = useState('AF-01')

  const { data, isLoading, error } = useQuery({
    queryKey: ['furnace', selectedId],
    queryFn: () => getFurnaceDetail(selectedId),
    enabled: !!selectedId,
  })

  const sc = data ? statusColors(data.status) : null

  return (
    <div className="space-y-5">
      {/* Furnace selector */}
      <div className="flex items-center gap-4">
        <label className="text-[#9E9E9E] text-sm">Furnace</label>
        <select
          value={selectedId}
          onChange={e => setSelectedId(e.target.value)}
          className="bg-[#1A2B3C] border border-[#234060] text-[#D4D4D4] rounded px-3 py-1.5 text-sm focus:outline-none focus:border-[#00B4CC]"
        >
          {FURNACE_IDS.map(id => (
            <option key={id} value={id}>{id}</option>
          ))}
        </select>
        {data && sc && (
          <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-xs ${sc.bg} ${sc.text}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${sc.dot}`} />
            {data.status}
          </div>
        )}
        {data && (
          <span className="text-[#4A4A4A] text-xs">{data.technology} · {data.feed_type}</span>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-[#9E9E9E] py-12 justify-center">
          <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
          Loading furnace data…
        </div>
      )}

      {error && (
        <div className="bg-[#E30613]/10 border border-[#E30613]/40 rounded p-4 text-[#E30613] text-sm">
          Failed to load furnace data. No snapshot uploaded yet or backend unavailable.
        </div>
      )}

      {data && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          {/* Key Metrics */}
          <div className="xl:col-span-2 space-y-5">
            <div className="bg-[#001730] border border-[#234060] rounded-lg p-5">
              <h2 className="text-[#D4D4D4] font-semibold text-sm mb-4">Key Metrics</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                {[
                  { label: 'Feed Rate', value: f(data.feed_rate, 1), unit: 't/hr' },
                  { label: 'COT', value: f(data.cot, 1), unit: '°C' },
                  { label: 'SHC', value: f(data.shc, 3), unit: '' },
                  { label: 'Yield', value: f(data.yield, 2), unit: '%' },
                  { label: 'Conversion', value: f(data.conversion, 1), unit: '%' },
                  { label: 'Propylene', value: f(data.propylene, 2), unit: '%' },
                  { label: 'TMT Max', value: f(data.tmt_max, 0), unit: '°C' },
                  { label: 'Run Days', value: f(data.run_days_elapsed, 0), unit: 'd elapsed' },
                  { label: 'Coking Rate', value: f(data.coking_rate, 3), unit: '' },
                  { label: 'COP', value: f(data.cop, 3), unit: 'barg' },
                  { label: 'CIT', value: f(data.cit, 1), unit: '°C' },
                  { label: 'SEC', value: f(data.sec, 3), unit: 'GJ/t' },
                ].map(({ label, value, unit }) => (
                  <div key={label} className="bg-[#1A2B3C] rounded p-3">
                    <div className="text-[#9E9E9E] text-xs mb-1">{label}</div>
                    <div className="text-[#D4D4D4] font-mono text-sm">
                      {value}
                      {unit && <span className="text-[#4A4A4A] ml-1 text-xs">{unit}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Constraint Status */}
            <div className="bg-[#001730] border border-[#234060] rounded-lg p-5">
              <h2 className="text-[#D4D4D4] font-semibold text-sm mb-4">Constraint Status</h2>
              <div className="space-y-4">
                <ConstraintBar
                  label="Feed Valve"
                  value={data.feed_valve_pct}
                  limit={data.constraints.feed_valve.limit ?? 85}
                  unit="%"
                />
                <ConstraintBar
                  label="FGV Opening"
                  value={data.fgv_pct}
                  limit={data.constraints.fgv.limit ?? 85}
                  unit="%"
                />
                <ConstraintBar
                  label="Damper"
                  value={data.damper_pct}
                  limit={data.constraints.damper.limit ?? 88}
                  unit="%"
                />
                <ConstraintBar
                  label="TMT Max"
                  value={data.tmt_max}
                  warning={data.constraints.tmt_max.warning ?? 1060}
                  alarm={data.constraints.tmt_max.alarm ?? 1075}
                  unit="°C"
                />
              </div>
            </div>
          </div>

          {/* Coke Thickness */}
          <div className="bg-[#001730] border border-[#234060] rounded-lg p-5">
            <h2 className="text-[#D4D4D4] font-semibold text-sm mb-1">Coke Thickness per Coil</h2>
            <p className="text-[#4A4A4A] text-xs mb-4">mm — from last pyrometer scan</p>
            {data.coke_thickness && data.coke_thickness.length > 0 ? (
              <CokeChart thickness={data.coke_thickness} />
            ) : (
              <p className="text-[#4A4A4A] text-sm italic">No coil thickness data available</p>
            )}

            {/* Feed composition */}
            <div className="mt-6 pt-4 border-t border-[#234060]">
              <h3 className="text-[#9E9E9E] text-xs mb-3">Feed Composition</h3>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-[#9E9E9E]">Ethane %</span>
                  <span className="text-[#D4D4D4] font-mono">{f(data.feed_ethane_pct, 2)}%</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-[#9E9E9E]">Propane %</span>
                  <span className="text-[#D4D4D4] font-mono">{f(data.feed_propane_pct, 2)}%</span>
                </div>
              </div>
            </div>

            {/* Design info */}
            {data.design_capacity != null && (
              <div className="mt-4 pt-4 border-t border-[#234060]">
                <h3 className="text-[#9E9E9E] text-xs mb-2">Design</h3>
                <div className="flex justify-between text-xs">
                  <span className="text-[#9E9E9E]">Capacity</span>
                  <span className="text-[#D4D4D4] font-mono">{f(data.design_capacity, 0)} t/hr</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
