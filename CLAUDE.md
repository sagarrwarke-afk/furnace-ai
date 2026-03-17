# Ethylene Furnace Fleet Optimization — AI Dashboard

## Project Overview
Full-stack web app for ethylene cracking furnace fleet optimization. Plant engineers upload furnace operating data via Excel, the system runs soft sensor models and a fleet optimizer, and displays results on a React dashboard.

## Tech Stack
- Database: PostgreSQL 16
- Backend: FastAPI (Python 3.11), SQLAlchemy, openpyxl
- ML Engine: scikit-learn GBR (GradientBoostingRegressor)
- Frontend: React 18 + TypeScript + Vite + Tailwind CSS + Shadcn/UI
- Charts: Recharts
- Data fetching: TanStack React Query
- Deployment: Docker Compose

## Architecture
No real-time historian connection. User uploads Excel with furnace data → FastAPI parses → stores in PostgreSQL → Dashboard reads from DB → Optimizer runs on request → Results saved to DB.

See `docs/fullstack_architecture_v2.md` for full architecture.
See `engine/furnace_runlength_forecasting.py` for the complete Python engine with soft sensor models, runlength forecaster, economic calculator, and fleet optimizer.

## Project Structure
```
furnace-ai/
├── CLAUDE.md                  ← this file
├── docs/
│   └── fullstack_architecture_v2.md
├── engine/
│   └── furnace_runlength_forecasting.py
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/          # SQLAlchemy ORM
│   │   ├── schemas/         # Pydantic request/response
│   │   ├── routers/         # API endpoints
│   │   ├── engine/          # Copied from engine/ folder
│   │   └── services/        # Business logic
│   ├── templates/
│   │   └── furnace_template.xlsx
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/             # API client + React Query hooks
│   │   ├── components/      # Reusable UI components
│   │   ├── pages/           # Page components
│   │   ├── types/           # TypeScript interfaces
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── init.sql                  # Database schema + seed data
└── docker-compose.yml
```

## Fleet Configuration (8 Furnaces)

| ID | Tech | Feed | FR t/hr | COT°C | SHC | Conv% | Yield% | TMTmax | RunDays | FGV% | Status | FeedEth% |
|----|------|------|---------|-------|-----|-------|--------|--------|---------|------|--------|----------|
| AF-01 | Lummus | Ethane | 54 | 838 | 0.33 | 64.8 | 49.2 | 1058 | 45 | 72 | online (protect) | 97.09 |
| AF-02 | Lummus | Ethane | 56 | 835 | 0.32 | 63.5 | 48.8 | 1045 | 62 | 68 | online (healthy) | 97.09 |
| AF-03 | Lummus | Propane | 76 | 830 | 0.35 | 77.4 | 29.1 | 1052 | 89 | 65 | online (healthy) | 7.83 |
| AF-04 | Lummus | Propane | 52 | 842 | 0.34 | 82.0 | 31.5 | 1068 | 28 | 78 | online (protect) | 7.7 |
| AF-05 | Lummus | Propane | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | decoke | 0 |
| AF-06 | Lummus | Propane | 68 | 832 | 0.35 | 78.2 | 29.8 | 1048 | 95 | 66 | online (healthy) | 7.83 |
| AF-07 | Lummus | Propane | 72 | 828 | 0.36 | 76.0 | 28.5 | 1040 | 110 | 60 | online (healthy) | 2.04 |
| AF-08 | Technip | Ethane | 30 | 830 | 0.32 | 64.0 | 34.2 | 1010 | 120 | 58 | online (healthy) | 98.57 |

Protection triggers: runDays < 60 OR tmtMax > 1060°C
Ethane furnaces: AF-01, AF-02, AF-08 (AF-08 is Technip design)
Propane furnaces: AF-03, AF-04, AF-06, AF-07

## Sensitivities (per °C COT increase)

| Parameter | Lummus Ethane | Lummus Propane | Technip Ethane | Unit |
|-----------|-------------|---------------|---------------|------|
| Ethylene yield | +0.218 | +0.218 | +0.200 | %/°C |
| Propylene | -0.017 | -0.136 | -0.015 | %/°C |
| Conversion | +0.480 | +0.405 | +0.450 | %/°C |
| TMT | +1.66 | +1.54 | +1.70 | °C/°C |
| Run length | -3.0 | -2.5 | -4.5 | d/°C |
| Run per SHC (per 0.01) | +10.0 | +7.5 | +12.0 | d/0.01 |
| Coking rate | +1.05 | +0.45 | +0.80 | units/°C |

## Composition Sensitivities (per 1% change in ethane fraction)
| Parameter | Value | Unit |
|-----------|-------|------|
| Yield | +0.22 | %yield / %ethane |
| Propylene | -0.16 | %prop / %ethane |
| Conversion | -0.05 | %conv / %ethane |
| SEC | -0.015 | SEC / %ethane |
| Coking rate | +0.08 | rate / %ethane |

## Feed Purity (User Input)
- ethane_feed_purity: % ethane in feed going to ethane furnaces (fresh+recycle mixed, from analyzer)
- propane_feed_purity: % propane in feed going to propane furnaces (fresh+recycle mixed, from analyzer)
- Sensitivities interpolated between pure ethane and pure propane based on actual purity
- When trained soft sensor models available, pass actual composition to model.predict()

## Cross-Feed Recycle Fractions
When furnace conversion drops (lower COT), extra unreacted gas exits:
- Ethane furnace unreacted: 95% ethane, 3% propane, 2% other
- Propane furnace unreacted: 15% ethane, 78% propane, 7% other

Ethane from ANY furnace → C2 splitter → ethane furnaces
Propane from ANY furnace → depropanizer → propane furnaces
This creates cross-feed: propane furnace protection generates ethane for ethane furnaces (15%)

## Optimizer Logic (4 Phases)

### Phase 1: Distribute Fresh Feed
Extra fresh feed allocated to matching feed-type furnaces only. Priority by marginal profit per ton. Protected furnaces get max 25% of valve headroom.

### Phase 2: Protect Stressed Furnaces
COT reduction (-0.5 to -5°C) + SHC increase on furnaces with runDays < 60 or TMT > 1060. Generates recycle as byproduct. Run life extends.

### Phase 3: Cross-Feed Recycle Redistribution
Ethane recycle → C2 splitter → healthy ethane furnaces.
Propane recycle → depropanizer → healthy propane furnaces.
Secondary recycle absorbed by ↑COT (+1-2°C) on receiving furnaces.

### Phase 4: Economics
Annual ethylene, propylene, feed cost, energy cost, decoke cost per furnace. Profit = revenue - costs. Sum across fleet.

## Iterative COT Optimization
Iterates COT from -0.5 to -5.0°C in 0.5°C steps for each protected furnace (10×10 = 100 combinations for 2 protected). Full cross-feed model runs each combination. Maximum fleet profit selected.

### Optimal Result (zero fresh feed):
AF-01 ↓COT -0.5°C | AF-04 ↓COT -3.0°C | Fleet Profit +$1.211M/yr

## Economic Parameters
| Parameter | Value |
|-----------|-------|
| Ethylene price | $1,050/ton |
| Propylene price | $900/ton |
| Fuel gas cost | $8.5/GJ |
| Ethane feed cost | $350/ton |
| Propane feed cost | $320/ton |
| Decoke cost | $150,000/event |
| Decoke downtime | 3 days |
| VHP steam cost | $25/ton |

## Constraint Limits
| Constraint | Limit |
|-----------|-------|
| Feed valve | 85% |
| FGV | 85% |
| Damper | 88% |
| TMT alarm | 1075°C |
| TMT warning | 1060°C |
| C2 splitter max | 90% |
| CGC suction max | 0.45 bar |

## Energy Impacts
### CGC (per t/hr extra feed)
- Ethane furnace: +1.93 t/hr cracked gas → +64 kW → +0.247 t/hr VHP → +$0.052M/yr
- Propane furnace: +2.35 t/hr cracked gas → +78 kW → +0.300 t/hr VHP → +$0.063M/yr

### C2 Splitter (per t/hr extra ethane to C2 splitter)
- Condenser duty: +0.134 MW
- Refrigeration power: +0.054 MW
- VHP steam: +0.203 t/hr
- Cost: +$0.043M/yr

## Database Tables
### Input (from Excel upload)
- furnace_snapshot: per-furnace operating data at a timestamp
- downstream_status: C2 splitter, CGC data
- feed_composition: per-furnace feed analysis
- upload_history: tracks every Excel upload

### Config (editable from UI)
- furnace_config: static furnace properties
- sensitivity_config: sensitivities (user-editable, or extracted from model)
- economic_params: prices, costs
- constraint_limits: valve/TMT/splitter limits
- cross_feed_config: ethane/propane fractions in unreacted stream
- model_registry: pickled sklearn models with metrics

### Output (written by optimizer/models)
- optimizer_results: per-run results with per_furnace JSONB
- soft_sensor_predictions: model predictions vs actuals
- runlength_forecast: day-by-day projection
- audit_log: all user actions

## Soft Sensor Models
- 4 model sets: Lummus-Ethane, Lummus-Propane, Technip-Ethane, Technip-Propane
- Independent variables (X): feed, shc, cot, cop, cit, feed_ethane_pct, feed_propane_pct, thickness
- Target variables (Y): yield, coking_rate, tmt, conversion, propylene, acetylene, benzene, methane, hydrogen, etc.
- Algorithm: GradientBoostingRegressor (200 trees, depth 5, lr 0.1)
- Typical accuracy: R² > 0.99, MAPE < 1%

## Excel Upload Template (2 sheets)
### Sheet 1: Furnace Data
Columns: timestamp, furnace_id, feed_rate, cot, shc, cop, cit, tmt_max, yield, conversion, coking_rate, propylene, feed_valve_pct, fgv_pct, damper_pct, sec, run_days_elapsed, run_days_total, status, feed_ethane_pct, feed_propane_pct, coke_thickness_1..8

### Sheet 2: Downstream
Columns: timestamp, c2_splitter_load_pct, cgc_suction_bar, cgc_power_mw, cgc_vhp_steam_tph

## API Endpoints
- POST /api/upload — parse Excel, validate, store snapshot
- GET /api/upload/template — download Excel template
- GET /api/snapshots — list uploads
- GET /api/snapshots/latest — latest snapshot
- GET /api/fleet?snapshot_id=latest — fleet overview
- GET /api/furnace/{id} — furnace detail
- POST /api/optimize — run FleetOptimizer
- POST /api/whatif — single furnace simulation
- GET/PUT /api/sensitivity — manage sensitivities
- POST /api/train-model — train soft sensor from CSV
- GET /api/models — model registry
- PUT /api/models/{id}/activate — activate model
- GET/PUT /api/config/economics — economic params
- GET/PUT /api/config/constraints — constraint limits

## Frontend Pages
1. Data Upload — drag-drop Excel, preview, validate, confirm
2. Fleet Overview — furnace cards, ranking table, KPIs
3. Furnace Detail — coil TMT heatmap, constraint panel
4. What-If Simulator — COT/SHC sliders, predict yield/conv/run
5. Feed Planning — optimizer with feed type, purity, delta feed inputs
6. Sensitivity Manager — edit sensitivities, train models, model registry
7. Settings — economic params, constraint limits
