import { useQuery } from '@tanstack/react-query'
import { getFleet } from '../api/client'
import type { FurnaceEntry, FleetKPIs } from '../types'

// ── Helpers ──────────────────────────────────────────────────────────────────

function f(v: number | null | undefined, d = 1): string {
  if (v === null || v === undefined) return '—'
  return Number(v).toFixed(d)
}

function statusColors(status: string): { bg: string; text: string; dot: string } {
  const s = (status ?? '').toLowerCase()
  if (s.includes('decoke'))
    return { bg: 'bg-[#4A1010]/40', text: 'text-[#E30613]', dot: 'bg-[#E30613]' }
  if (s.includes('protect'))
    return { bg: 'bg-[#4A3800]/40', text: 'text-[#F5C800]', dot: 'bg-[#F5C800]' }
  return { bg: 'bg-[#003F6B]/40', text: 'text-[#00B4CC]', dot: 'bg-[#00B4CC]' }
}

function tmtColor(tmt: number | null): string {
  if (tmt === null || tmt === undefined) return 'text-[#9E9E9E]'
  if (tmt > 1060) return 'text-[#E30613]'
  if (tmt > 1045) return 'text-[#F5C800]'
  return 'text-[#00B4CC]'
}

// ── KPI bar ───────────────────────────────────────────────────────────────────

function KPICard({ label, value, unit, accent = false }: {
  label: string; value: string; unit: string; accent?: boolean
}) {
  return (
    <div className="rounded border border-[#234060] bg-[#1E3347] p-4">
      <p className="text-[#9E9E9E] text-xs mb-1">{label}</p>
      <p className={`text-2xl font-bold ${accent ? 'text-[#00B4CC]' : 'text-[#D4D4D4]'}`}>{value}</p>
      <p className="text-[#4A4A4A] text-xs mt-0.5">{unit}</p>
    </div>
  )
}

function KPIBar({ kpis }: { kpis: FleetKPIs }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      <KPICard label="Total Feed" value={f(kpis.total_feed_tph, 1)} unit="t/hr" />
      <KPICard label="Ethylene Out" value={f(kpis.total_ethylene_tph, 2)} unit="t/hr" accent />
      <KPICard label="Propylene Out" value={f(kpis.total_propylene_tph, 2)} unit="t/hr" />
      <KPICard label="Online" value={String(kpis.online_count)} unit={`/ ${kpis.total_furnaces} furnaces`} />
      <KPICard label="Protected" value={String(kpis.protect_count)} unit="furnaces" />
      <KPICard label="Decoking" value={String(kpis.decoke_count)} unit="furnaces" />
    </div>
  )
}

// ── Furnace card ──────────────────────────────────────────────────────────────

function FurnaceCard({ fur }: { fur: FurnaceEntry }) {
  const sc = statusColors(fur.status)
  const tmt = tmtColor(fur.tmt_max)
  const status = (fur.status ?? '').toLowerCase()

  return (
    <div className={`rounded border border-[#234060] p-4 flex flex-col gap-3 ${sc.bg}`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${sc.dot}`} />
            <span className="font-bold text-[#D4D4D4] text-base">{fur.furnace_id}</span>
            <span className="text-[10px] text-[#9E9E9E]">{fur.technology ?? ''}</span>
            {fur.prediction_source === 'model' && (
              <span className="text-[9px] text-[#00B4CC] bg-[#00B4CC]/10 px-1.5 py-0.5 rounded font-semibold" title={`Soft sensors predicted by ${fur.algorithm ?? 'ML Model'}`}>
                ML
              </span>
            )}
          </div>
          <div className="text-[10px] text-[#9E9E9E] mt-0.5">{fur.feed_type ?? ''} feed</div>
        </div>
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${sc.text} border ${sc.dot === 'bg-[#E30613]' ? 'border-[#E30613]/40' : sc.dot === 'bg-[#F5C800]' ? 'border-[#F5C800]/40' : 'border-[#00B4CC]/40'}`}>
          {status.includes('decoke') ? 'DECOKE'
            : status.includes('protect') ? 'PROTECT'
            : 'HEALTHY'}
        </span>
      </div>

      {/* Metrics */}
      {status.includes('decoke') ? (
        <div className="text-[#4A4A4A] text-xs text-center py-4">Furnace offline — decoking</div>
      ) : (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
          {[
            { label: 'Feed Rate', value: `${f(fur.feed_rate, 1)} t/hr` },
            { label: 'COT', value: `${f(fur.cot, 1)} °C` },
            { label: 'SHC', value: f(fur.shc, 2) },
            { label: 'Yield', value: `${f(fur.yield, 1)} %` },
            { label: 'Conv', value: `${f(fur.conversion, 1)} %` },
            { label: 'Propylene', value: `${f(fur.propylene, 1)} %` },
            { label: 'Run Days', value: `${fur.run_days_elapsed ?? '—'} d` },
            { label: 'Eth. Out', value: `${f(fur.ethylene_tph, 2)} t/hr` },
          ].map(({ label, value }) => (
            <div key={label}>
              <span className="text-[#4A4A4A] text-[10px]">{label}</span>
              <span className="text-[#D4D4D4] text-xs ml-1">{value}</span>
            </div>
          ))}
        </div>
      )}

      {/* TMT row */}
      {!status.includes('decoke') && (
        <div className="flex items-center justify-between border-t border-[#234060] pt-2">
          <span className="text-[#4A4A4A] text-[10px]">TMT max</span>
          <span className={`text-sm font-bold ${tmt}`}>{f(fur.tmt_max, 0)} °C</span>
        </div>
      )}
    </div>
  )
}

// ── Ranking table ─────────────────────────────────────────────────────────────

function RankTable({ furnaces, label }: { furnaces: FurnaceEntry[]; label: string }) {
  return (
    <div>
      <h3 className="text-[#9E9E9E] text-xs font-semibold uppercase tracking-wider mb-2">{label}</h3>
      <div className="overflow-x-auto rounded border border-[#234060]">
        <table className="text-xs min-w-full">
          <thead>
            <tr className="bg-[#1A2B3C]">
              {['#', 'Furnace', 'Feed (t/hr)', 'COT', 'Yield%', 'C2H4 (t/hr)', 'TMT', 'Run Days', 'Status'].map((h) => (
                <th key={h} className="px-3 py-2 text-[#9E9E9E] whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {furnaces.map((fur, i) => {
              const sc = statusColors(fur.status)
              const tmt = tmtColor(fur.tmt_max)
              return (
                <tr key={fur.furnace_id} className={i % 2 === 0 ? 'bg-[#001E35]' : 'bg-[#1A2B3C]'}>
                  <td className="px-3 py-2 text-[#4A4A4A]">{fur.rank}</td>
                  <td className="px-3 py-2 font-medium text-[#D4D4D4]">
                    {fur.furnace_id}
                    {fur.prediction_source === 'model' && (
                      <span className="ml-1 text-[8px] text-[#00B4CC] bg-[#00B4CC]/10 px-1 py-0.5 rounded font-semibold" title={`ML: ${fur.algorithm}`}>ML</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-[#D4D4D4]">{f(fur.feed_rate, 1)}</td>
                  <td className="px-3 py-2 text-[#D4D4D4]">{f(fur.cot, 1)}</td>
                  <td className="px-3 py-2 text-[#D4D4D4]">{f(fur.yield, 1)}</td>
                  <td className="px-3 py-2 text-[#00B4CC] font-medium">{f(fur.ethylene_tph, 2)}</td>
                  <td className={`px-3 py-2 font-medium ${tmt}`}>{f(fur.tmt_max, 0)}</td>
                  <td className="px-3 py-2 text-[#D4D4D4]">{fur.run_days_elapsed ?? '—'}</td>
                  <td className="px-3 py-2">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${sc.text}`}>
                      {(fur.status ?? '').toUpperCase()}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function FleetOverview() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['fleet'],
    queryFn: () => getFleet('latest'),
    refetchInterval: 60_000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-[#9E9E9E]">
          <svg className="w-5 h-5 animate-spin text-[#00B4CC]" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading fleet data...
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="text-[#E30613] text-sm">
          {(error as Error)?.message?.includes('404')
            ? 'No data uploaded yet. Go to Data Upload to load furnace data.'
            : 'Failed to load fleet data. Is the backend running?'}
        </div>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 rounded border border-[#234060] text-[#00B4CC] text-sm hover:bg-[#003F6B]/30"
        >
          Retry
        </button>
      </div>
    )
  }

  const allFurnaces = [...data.ethane_furnaces, ...data.propane_furnaces]

  return (
    <div className="space-y-6">
      {/* KPI row */}
      <KPIBar kpis={data.kpis} />

      {/* Furnace cards */}
      <div>
        <h2 className="text-[#9E9E9E] text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-2">
          Furnace Cards — Upload #{data.upload_id}
          {data.has_active_models && (
            <span className="text-[10px] text-[#00B4CC] bg-[#00B4CC]/10 px-2 py-0.5 rounded normal-case font-normal">
              ML models active — soft sensor values are model-predicted
            </span>
          )}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {allFurnaces.map((fur) => (
            <FurnaceCard key={fur.furnace_id} fur={fur} />
          ))}
        </div>
      </div>

      {/* Ranking tables */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <RankTable furnaces={data.ethane_furnaces} label="Ethane Furnace Ranking" />
        <RankTable furnaces={data.propane_furnaces} label="Propane Furnace Ranking" />
      </div>
    </div>
  )
}
