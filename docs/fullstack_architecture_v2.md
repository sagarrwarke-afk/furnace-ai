# Ethylene Furnace AI — Full Stack Architecture (Excel Upload Based)

## System Overview

```
User exports DCS data → Excel → Upload via React UI → FastAPI parses → PostgreSQL
                                                                           │
                                          React Dashboard ← FastAPI ← DB reads
```

No historian integration needed. User uploads Excel with furnace data at any timestamp. Dashboard reads from DB.

## Key Change from v1

- NO OPC-UA / historian connection
- NO real-time data ingestion service  
- User uploads Excel with process data (exported from DCS/PI manually)
- Each upload = one "snapshot" in time
- Dashboard shows latest snapshot by default, user can switch between snapshots
- All optimizer/model results tied to a snapshot_id

## Data Flow

1. User exports data from DCS/PI to Excel (or fills downloadable template)
2. User opens Dashboard → "Upload Data" page
3. Drags Excel file → Backend parses, validates, shows preview
4. User confirms → Data saved to furnace_snapshot table with timestamp
5. Dashboard auto-refreshes → Fleet Overview shows latest snapshot
6. User goes to Feed Planning → inputs fresh feed delta, purity
7. Optimizer runs against latest snapshot → results displayed + saved to DB
8. User can browse historical snapshots and compare optimizer results

## Database Tables

### Input Tables
- **furnace_snapshot** — per-furnace operating data at a timestamp (from Excel)
- **downstream_status** — C2 splitter, CGC status (from same Excel sheet 2)
- **feed_composition** — per-furnace feed analysis
- **upload_history** — tracks every Excel upload (filename, user, validation status)

### Config Tables  
- **furnace_config** — static: technology, feed type, passes, coils, limits
- **sensitivity_config** — user-editable sensitivities (per °C COT, per 0.01 SHC)
- **economic_params** — ethylene price, feed costs, VHP steam cost, decoke cost
- **constraint_limits** — valve limits, TMT alarm, C2 splitter max
- **cross_feed_config** — ethane/propane fractions in unreacted stream
- **model_registry** — pickled sklearn models with metrics

### Output Tables
- **optimizer_results** — per-run results with per_furnace JSONB and fleet_totals
- **soft_sensor_predictions** — model predictions vs actuals per snapshot
- **runlength_forecast** — day-by-day projection per furnace
- **audit_log** — all user actions

## Excel Upload Template

Two sheets:

**Sheet 1 — Furnace Data:** timestamp, furnace_id, feed_rate, cot, shc, cop, cit, tmt_max, yield, conversion, coking_rate, propylene, feed_valve_pct, fgv_pct, damper_pct, sec, run_days_elapsed, run_days_total, status, feed_ethane_pct, feed_propane_pct, coke_thickness_1..8

**Sheet 2 — Downstream:** timestamp, c2_splitter_load_pct, cgc_suction_bar, cgc_power_mw, cgc_vhp_steam_tph

## API Endpoints

### Upload
- POST /api/upload — parse Excel, validate, store snapshot
- GET /api/upload/template — download blank Excel template
- GET /api/snapshots — list all uploads
- GET /api/snapshots/{id} — get snapshot data
- GET /api/snapshots/latest — latest snapshot

### Dashboard
- GET /api/fleet?snapshot_id=latest — fleet overview + rankings
- GET /api/furnace/{id}?snapshot_id=latest — furnace detail

### Optimizer
- POST /api/optimize — run FleetOptimizer on a snapshot
- GET /api/optimize/history — past optimizer runs
- POST /api/whatif — single furnace what-if simulation

### Sensitivity & Models
- GET /api/sensitivity — current sensitivities
- PUT /api/sensitivity — user edits a sensitivity value
- POST /api/train-model — train GBR from CSV upload or snapshot range
- GET /api/models — model registry
- PUT /api/models/{id}/activate — activate a model for optimizer

### Config
- GET/PUT /api/config/economics — prices and costs
- GET/PUT /api/config/constraints — valve/TMT/splitter limits

## Frontend Pages

1. **Data Upload** — drag-drop Excel, preview, validate, confirm, upload history
2. **Fleet Overview** — furnace cards, ranking table, KPIs (from latest snapshot)
3. **Furnace Detail** — coil TMT heatmap, constraint panel (snapshot selector)
4. **What-If Simulator** — COT/SHC/feed sliders, predict yield/conversion/run
5. **Feed Planning** — optimizer with feed type, purity, delta feed inputs
6. **Sensitivity Manager** — view/edit sensitivities, train models, model registry
7. **Settings** — economic params, constraint limits

## Build Plan with Claude (6 sessions)

**Session 1:** "Create PostgreSQL init.sql with all tables, indexes, seed data from this architecture."

**Session 2:** "Create FastAPI project. Upload router: parse Excel with openpyxl, validate, store to DB. Template download endpoint."

**Session 3:** "Create /api/fleet, /api/furnace, /api/optimize endpoints using FleetOptimizer class. Read config from DB."

**Session 4:** "Create /api/train-model and /api/sensitivity endpoints. Model training from CSV, pickle storage, sensitivity extraction."

**Session 5:** "Create React frontend: Upload page, Fleet Overview, Furnace Detail, Feed Planning."

**Session 6:** "Create Sensitivity Manager page, Settings page. Docker Compose deployment."

## Tech Stack

PostgreSQL 16 | FastAPI (Python) | scikit-learn GBR | React + TypeScript + Tailwind + Shadcn/UI | TanStack React Query | Recharts | openpyxl | Docker Compose
