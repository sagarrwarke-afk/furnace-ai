# Ethylene Furnace Fleet Optimization — AI Dashboard

## Project Overview
Full-stack web app for ethylene cracking furnace fleet optimization. Plant engineers upload furnace operating data via Excel, the system runs soft sensor models and a fleet optimizer, and displays results on a React dashboard.

## Tech Stack
- Database: PostgreSQL 16
- Backend: FastAPI (Python 3.11), SQLAlchemy, openpyxl
- ML Engine: Multi-algorithm (Ridge, RandomForest, GradientBoosting, XGBoost, LightGBM) with benchmark-driven selection
- Frontend: React 18 + TypeScript + Vite + Tailwind CSS + Shadcn/UI
- Charts: Recharts
- Data fetching: TanStack React Query
- Deployment: Docker Compose

## Architecture
No real-time historian connection. Two data flows:

1. **Operating Data**: User uploads Excel with furnace data → FastAPI parses → stores in PostgreSQL → Dashboard reads from DB → Optimizer runs on request → Results saved to DB.
2. **ML Models**: User uploads simulation CSV → Benchmark compares algorithms → User trains selected algorithm → Model pickled to DB → Activated model provides predictions in What-If, Fleet Overview, and Optimizer (with sensitivity-based fallback when no model).

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
│   │   │   └── training.py  # benchmark, train, model registry endpoints
│   │   ├── engine/          # Copied from engine/ folder
│   │   │   └── model_benchmark.py  # Multi-algo ML benchmark engine
│   │   └── services/        # Business logic
│   │       ├── training.py  # benchmark_models, train_model, load_active_models
│   │       └── optimizer.py # Model-aware what-if & fleet optimizer
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
- When active ML model exists: actual composition passed as feed_ethane_pct/feed_propane_pct features to model.predict()
- When no model (fallback): sensitivities interpolated between pure ethane and pure propane based on actual purity

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
- model_registry: pickled sklearn models with metrics, algorithm name, is_active flag, extracted sensitivities

### Output (written by optimizer/models)
- optimizer_results: per-run results with per_furnace JSONB
- soft_sensor_predictions: model predictions vs actuals
- runlength_forecast: day-by-day projection
- audit_log: all user actions

## Soft Sensor Models

### Model Architecture
- 4 model sets: Lummus-Ethane, Lummus-Propane, Technip-Ethane, Technip-Propane
- Each model set contains 5 independent target models (one per target)
- Base features (X, 8): feed, shc, cot, cop, cit, thickness, feed_ethane_pct, feed_propane_pct
- Target variables (Y, 5): yield_c2h4, coking_rate, tmt, conversion, propylene
- 13 engineered features auto-generated from base features (total 21 features)
- StandardScaler applied to all features before model training

### Available Algorithms (user selects via benchmark)
| Algorithm | Type | Config |
|-----------|------|--------|
| Ridge | Linear | alpha=1.0 (recommended for grid-structured simulation data) |
| RandomForest | Tree ensemble | 200 trees, depth 10 |
| GradientBoosting | Tree ensemble | 200 trees, depth 5, lr 0.1 |
| XGBoost | Tree ensemble | 300 trees, depth 6, lr 0.1, subsample 0.8 |
| LightGBM | Tree ensemble | 300 trees, 31 leaves, lr 0.1 |

### Engineered Features (13)
Auto-generated from 8 base features to capture nonlinear interactions:
- Interactions: cot×shc, cot×feed, shc×feed, ethane×cot, propane×cot
- Quadratic: cot², shc², thickness²
- Log transforms: log(cot), log(feed), log(thickness)
- Derived: cot−cit delta, feed_purity_ratio (ethane/(propane+1))

### Why Ridge is Recommended
Simulation data is generated on a sparse grid (discrete COT/SHC/feed levels). Tree-based models produce staircase artifacts when interpolating between grid points. Ridge regression with engineered features provides smooth, physically plausible interpolation. This is confirmed by hold-out interpolation testing (remove one grid level, predict it).

### Benchmark Scoring
```
Score = 0.4 × mean_test_R² + 0.4 × mean_interpolation_R² + 0.2 × smoothness_bonus
```
- Linear models (Ridge) get smoothness bonus = +0.05
- Tree models get smoothness bonus = 0
- Interpolation test: removes one grid level per feature, trains on remaining, predicts held-out level

### Typical Accuracy (Ridge on Lummus-Ethane)
- Test R² > 0.95 on all 5 targets
- Interpolation R² > 0.97
- Composite score ~0.993

## ML Training & Activation Flow

### Two-Step UI Flow (Sensitivity Manager Page)
1. **Benchmark**: User selects technology + feed type, uploads simulation CSV, checks algorithm boxes → POST /api/benchmark-models → sees comparison table + recommendation
2. **Train & Activate**: User picks recommended (or any) algorithm → POST /api/train-model → sees per-target metrics → PUT /api/models/{id}/activate → model goes live

### What Happens on Training
1. CSV parsed → 8 base features extracted → 13 engineered features generated
2. 80/20 train-test split
3. StandardScaler fitted on training data
4. One model trained per target (5 models total)
5. Metrics computed (R² train/test, MAE, MAPE)
6. Model dict pickled and stored in model_registry table
7. Sensitivities extracted by perturbation and stored alongside model

### What Happens on Activation
1. Previous active model for same (technology, feed_type) deactivated
2. New model marked as active (is_active=true)
3. 13 sensitivities extracted from model by perturbation and copied to sensitivity_config table:
   - Per-COT (5): yield, coking_rate, tmt, conversion, propylene per °C
   - Per-SHC (1): coking_rate per 0.01 SHC
   - Per-ethane% (5): yield, coking_rate, tmt, conversion, propylene per 1% ethane
   - Per-thickness (2): tmt, coking_rate per 0.5mm thickness
4. These sensitivities replace any manual values and are used as fallback when model is unavailable

### Sensitivity Extraction by Perturbation
Model-derived sensitivities are computed by feeding perturbed inputs:
- COT: base_point with cot +1°C → delta per target
- SHC: base_point with shc +0.01 → delta for coking_rate
- Ethane: base_point with feed_ethane_pct +1% → delta per target
- Thickness: base_point with thickness +0.5mm → delta for tmt, coking_rate

## Per-Coil Prediction Architecture

Simulation data is per-coil (each coil has its own thickness), so furnace-level predictions use per-coil aggregation:

1. `feed_per_coil = furnace_feed_rate / num_coils`
2. For each coil: predict with that coil's thickness (8 coils typical)
3. Aggregate across coils:
   - TMT = MAX(coil predictions) — hottest coil limits furnace
   - Yield = MEAN(coil predictions) — average across coils
   - Conversion = MEAN(coil predictions)
   - Propylene = MEAN(coil predictions)
   - Coking rate = MAX(coil predictions) — worst coil determines decoke timing
4. Per-coil detail returned for coil-level analysis

## Prediction Source Fallback Logic

The system uses a dual-prediction architecture with automatic fallback:

### When Active Model Exists (for that technology + feed_type):
- **What-If**: `ModelBenchmark.predict_furnace()` computes both baseline and predicted values
- **Fleet Overview**: `model_predicted` field populated with model-calculated current values
- **Optimizer**: Active models passed to FleetOptimizer for model-based optimization
- Response includes `prediction_source: "model"` and `algorithm: "Ridge"` (or whichever)

### When No Active Model (fallback):
- **What-If**: Sensitivity-based linear deltas applied (Δyield = sensitivity × ΔCOT)
- **Fleet Overview**: `model_predicted` = null
- **Optimizer**: Uses sensitivity coefficients from sensitivity_config table
- Response includes `prediction_source: "sensitivity"` and `sensitivities_used: {...}`

### Run Length (Always Sensitivity-Based)
Run length is not a model target (not in simulation data). It always uses:
```
delta_run_days = (run_cot_sensitivity × delta_cot) + (run_shc_sensitivity × delta_shc / 0.01)
```

## Excel Upload Template (2 sheets)
### Sheet 1: Furnace Data
Columns: timestamp, furnace_id, feed_rate, cot, shc, cop, cit, tmt_max, yield, conversion, coking_rate, propylene, feed_valve_pct, fgv_pct, damper_pct, sec, run_days_elapsed, run_days_total, status, feed_ethane_pct, feed_propane_pct, coke_thickness_1..8

### Sheet 2: Downstream
Columns: timestamp, c2_splitter_load_pct, cgc_suction_bar, cgc_power_mw, cgc_vhp_steam_tph

## API Endpoints

### Data
- POST /api/upload — parse Excel, validate, store snapshot
- GET /api/upload/template — download Excel template
- GET /api/snapshots — list uploads
- GET /api/snapshots/latest — latest snapshot

### Fleet & Furnace
- GET /api/fleet?upload_id=latest — fleet overview (includes `model_predicted` per furnace, `has_active_models` flag)
- GET /api/furnace/{id} — furnace detail
- POST /api/optimize — run FleetOptimizer (model-aware when active models exist)
- POST /api/whatif — single furnace simulation (returns `prediction_source`, `algorithm`)

### ML Models & Training
- GET /api/available-algorithms — returns list of installed algorithms (e.g. ["Ridge","RandomForest","GradientBoosting","XGBoost","LightGBM"])
- POST /api/benchmark-models — upload CSV + select algorithms → benchmark comparison with recommendation (multipart form: file, technology, feed_type, algorithms JSON)
- POST /api/train-model — train production model with chosen algorithm (multipart form: file, technology, feed_type, algorithm)
- GET /api/models — model registry (all models with metrics, algorithm, is_active)
- PUT /api/models/{id}/activate — activate model, extract & copy sensitivities to sensitivity_config

### Configuration
- GET/PUT /api/sensitivity — manage sensitivities (includes model-extracted values with source="model")
- GET/PUT /api/config/economics — economic params
- GET/PUT /api/config/constraints — constraint limits

## Frontend Pages
1. **Data Upload** — drag-drop Excel, preview, validate, confirm
2. **Fleet Overview** — furnace cards (with model_predicted overlay when available), ranking table, KPIs, `has_active_models` indicator
3. **Furnace Detail** — coil TMT heatmap, constraint panel
4. **What-If Simulator** — COT/SHC/feed sliders, predict yield/conv/run. Shows teal "Predicted by: {algorithm}" badge when model active, gray "Predicted by: Sensitivities" badge when using fallback
5. **Feed Planning** — optimizer with feed type, purity, delta feed inputs
6. **Sensitivity Manager** — two-step ML flow:
   - **Step 1 (Benchmark)**: Select technology + feed type, upload simulation CSV, check algorithm boxes, click "Benchmark N Algorithms". Shows grid analysis badges, per-target comparison table (R², interpolation R², MAPE), composite scores, star recommendation with reason
   - **Step 2 (Train & Activate)**: Algorithm dropdown (pre-filled with recommendation), "Train & Save" button, per-target training metrics table. Model registry table at bottom with Algorithm column, activate/deactivate buttons
   - **Sensitivity table**: Edit sensitivities manually or see model-extracted values (source=model)
7. **Settings** — economic params, constraint limits

## Key Frontend Files Changed for ML Integration
- `frontend/src/types/index.ts` — Added `BenchmarkTargetMetrics`, `BenchmarkAlgorithmResult`, `BenchmarkResponse`, `ModelPredicted` interfaces. Added `prediction_source`, `algorithm`, `model_predicted` fields to response types
- `frontend/src/api/client.ts` — Added `benchmarkModels()`, `getAvailableAlgorithms()`, updated `trainModel()` with algorithm param
- `frontend/src/pages/SensitivityManager.tsx` — Complete rewrite with two-step benchmark→train flow
- `frontend/src/pages/WhatIfSimulator.tsx` — Added prediction source badge in results panel

## Key Backend Files for ML Integration
- `backend/app/engine/model_benchmark.py` — Core ML engine: `ModelBenchmark` class with `run_benchmark()`, `run_interpolation_test()`, `recommend()`, `train_production_model()`, `predict()`, `predict_furnace()`
- `backend/app/services/training.py` — `benchmark_models()`, `train_model()`, `load_active_models()`, `predict_fleet_values()`, `_extract_sensitivities_from_model_dict()`
- `backend/app/services/optimizer.py` — `run_whatif()` with model-based prediction fallback, `run_optimizer()` with active model loading
- `backend/app/routers/training.py` — `/api/benchmark-models`, `/api/available-algorithms`, `/api/train-model` endpoints
- `backend/app/routers/fleet.py` — Fleet overview enriched with `model_predicted` values per furnace
