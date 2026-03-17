import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { downloadTemplate, uploadCsv, listSnapshots } from '../api/client'
import type { UploadResponse, Snapshot } from '../types'

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmt(val: unknown): string {
  if (val === null || val === undefined) return '—'
  return String(val)
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

// ── Preview table ─────────────────────────────────────────────────────────────

function PreviewTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows || rows.length === 0) return null
  const cols = Object.keys(rows[0])
  return (
    <div className="overflow-x-auto rounded border border-[#234060] mt-4">
      <table className="text-xs min-w-full">
        <thead>
          <tr className="bg-[#1A2B3C]">
            {cols.map((c) => (
              <th key={c} className="px-3 py-2 text-[#9E9E9E] whitespace-nowrap">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? 'bg-[#001E35]' : 'bg-[#1A2B3C]'}>
              {cols.map((c) => (
                <td key={c} className="px-3 py-1.5 text-[#D4D4D4] whitespace-nowrap">{fmt(row[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Upload history ────────────────────────────────────────────────────────────

function UploadHistory({ snapshots }: { snapshots: Snapshot[] }) {
  return (
    <div className="overflow-x-auto rounded border border-[#234060]">
      <table className="text-xs min-w-full">
        <thead>
          <tr className="bg-[#1A2B3C]">
            {['ID', 'Filename', 'Uploaded by', 'Date', 'Rows', 'Valid'].map((h) => (
              <th key={h} className="px-3 py-2 text-[#9E9E9E] whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {snapshots.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-3 py-6 text-center text-[#4A4A4A]">No uploads yet</td>
            </tr>
          ) : snapshots.map((s, i) => (
            <tr key={s.upload_id} className={i % 2 === 0 ? 'bg-[#001E35]' : 'bg-[#1A2B3C]'}>
              <td className="px-3 py-1.5 text-[#9E9E9E]">#{s.upload_id}</td>
              <td className="px-3 py-1.5 text-[#D4D4D4]">{s.filename}</td>
              <td className="px-3 py-1.5 text-[#9E9E9E]">{s.uploaded_by}</td>
              <td className="px-3 py-1.5 text-[#9E9E9E] whitespace-nowrap">{fmtDate(s.uploaded_at)}</td>
              <td className="px-3 py-1.5 text-[#D4D4D4] text-right">{s.row_count}</td>
              <td className="px-3 py-1.5">
                <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                  s.validation_ok
                    ? 'bg-[#003F6B] text-[#00B4CC]'
                    : 'bg-[#4A1010] text-[#E30613]'
                }`}>
                  {s.validation_ok ? 'OK' : 'FAIL'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Drop zone ─────────────────────────────────────────────────────────────────

function DropZone({
  onFile,
  selectedFile,
}: {
  onFile: (f: File) => void
  selectedFile: File | null
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) onFile(file)
  }

  return (
    <div
      className={`relative flex flex-col items-center justify-center gap-3 rounded border-2 border-dashed py-12 px-6 cursor-pointer transition-colors ${
        dragging
          ? 'border-[#00B4CC] bg-[#003F6B]/30'
          : 'border-[#234060] bg-[#1A2B3C] hover:border-[#00B4CC]/60'
      }`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) onFile(f)
        }}
      />
      <svg className="w-10 h-10 text-[#234060]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      {selectedFile ? (
        <div className="text-center">
          <p className="text-[#00B4CC] font-medium text-sm">{selectedFile.name}</p>
          <p className="text-[#9E9E9E] text-xs mt-1">{(selectedFile.size / 1024).toFixed(1)} KB — click to change</p>
        </div>
      ) : (
        <div className="text-center">
          <p className="text-[#D4D4D4] text-sm">Drop a CSV file here or click to browse</p>
          <p className="text-[#4A4A4A] text-xs mt-1">Only .csv files accepted</p>
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function UploadPage() {
  const qc = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<UploadResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: snapshots = [], isLoading: snapsLoading } = useQuery({
    queryKey: ['snapshots'],
    queryFn: listSnapshots,
  })

  const uploadMutation = useMutation({
    mutationFn: (f: File) => uploadCsv(f),
    onSuccess: (data) => {
      setResult(data)
      setError(null)
      qc.invalidateQueries({ queryKey: ['snapshots'] })
      qc.invalidateQueries({ queryKey: ['fleet'] })
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? (err as Error)?.message
        ?? 'Upload failed'
      setError(msg)
    },
  })

  const handleConfirm = () => {
    if (!file) return
    setResult(null)
    setError(null)
    uploadMutation.mutate(file)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header actions */}
      <div className="flex items-center justify-between">
        <p className="text-[#9E9E9E] text-sm">Upload furnace operating data in CSV format.</p>
        <button
          onClick={downloadTemplate}
          className="flex items-center gap-2 px-4 py-2 rounded border border-[#234060] text-[#00B4CC] text-sm font-medium hover:bg-[#003F6B]/30 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Download Template
        </button>
      </div>

      {/* Drop zone */}
      <DropZone onFile={setFile} selectedFile={file} />

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 p-4 rounded border border-[#E30613]/40 bg-[#4A1010]/30">
          <svg className="w-5 h-5 text-[#E30613] shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd" />
          </svg>
          <div>
            <p className="text-[#E30613] font-medium text-sm">Upload Error</p>
            <p className="text-[#9E9E9E] text-xs mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Success preview */}
      {result && (
        <div className="space-y-3">
          <div className="flex items-center gap-3 p-4 rounded border border-[#00B4CC]/40 bg-[#003F6B]/20">
            <svg className="w-5 h-5 text-[#00B4CC] shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd" />
            </svg>
            <div>
              <p className="text-[#00B4CC] font-medium text-sm">
                Upload #{result.upload_id} successful — {result.rows_inserted} rows inserted
              </p>
              <p className="text-[#9E9E9E] text-xs mt-0.5">Showing first 10 rows preview</p>
            </div>
          </div>
          <PreviewTable rows={result.preview} />
        </div>
      )}

      {/* Confirm button */}
      {file && !result && (
        <div className="flex justify-end">
          <button
            onClick={handleConfirm}
            disabled={uploadMutation.isPending}
            className="flex items-center gap-2 px-6 py-2.5 rounded bg-[#00B4CC] text-[#002147] font-semibold text-sm hover:bg-[#33C8DE] disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {uploadMutation.isPending ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Uploading...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                Confirm Upload
              </>
            )}
          </button>
        </div>
      )}

      {/* Upload history */}
      <div>
        <h2 className="text-[#D4D4D4] font-semibold text-sm mb-3">Upload History</h2>
        {snapsLoading ? (
          <p className="text-[#4A4A4A] text-xs">Loading...</p>
        ) : (
          <UploadHistory snapshots={snapshots} />
        )}
      </div>
    </div>
  )
}
