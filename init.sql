-- =============================================================================
-- Ethylene Furnace Fleet Optimization — Database Schema & Seed Data
-- PostgreSQL 16
-- =============================================================================

-- Clean slate
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS runlength_forecast CASCADE;
DROP TABLE IF EXISTS soft_sensor_predictions CASCADE;
DROP TABLE IF EXISTS optimizer_results CASCADE;
DROP TABLE IF EXISTS model_registry CASCADE;
DROP TABLE IF EXISTS cross_feed_config CASCADE;
DROP TABLE IF EXISTS constraint_limits CASCADE;
DROP TABLE IF EXISTS economic_params CASCADE;
DROP TABLE IF EXISTS sensitivity_config CASCADE;
DROP TABLE IF EXISTS furnace_config CASCADE;
DROP TABLE IF EXISTS feed_composition CASCADE;
DROP TABLE IF EXISTS downstream_status CASCADE;
DROP TABLE IF EXISTS coil_snapshot CASCADE;
DROP TABLE IF EXISTS furnace_snapshot CASCADE;
DROP TABLE IF EXISTS upload_history CASCADE;

-- =============================================================================
-- INPUT TABLES (from Excel upload)
-- =============================================================================

CREATE TABLE upload_history (
    id              SERIAL PRIMARY KEY,
    filename        VARCHAR(255) NOT NULL,
    uploaded_by     VARCHAR(100) DEFAULT 'system',
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    row_count       INTEGER,
    validation_ok   BOOLEAN DEFAULT TRUE,
    validation_msg  TEXT,
    snapshot_ts     TIMESTAMPTZ
);

CREATE TABLE furnace_snapshot (
    id                  SERIAL PRIMARY KEY,
    upload_id           INTEGER NOT NULL REFERENCES upload_history(id) ON DELETE CASCADE,
    snapshot_ts         TIMESTAMPTZ NOT NULL,
    furnace_id          VARCHAR(10) NOT NULL,
    feed_rate           NUMERIC(8,2),
    cot                 NUMERIC(6,2),
    shc                 NUMERIC(5,3),
    cop                 NUMERIC(6,2),
    cit                 NUMERIC(6,2),
    tmt_max             NUMERIC(6,1),
    yield               NUMERIC(5,2),
    conversion          NUMERIC(5,2),
    coking_rate         NUMERIC(6,3),
    propylene           NUMERIC(5,2),
    feed_valve_pct      NUMERIC(5,2),
    fgv_pct             NUMERIC(5,2),
    damper_pct          NUMERIC(5,2),
    sec                 NUMERIC(6,3),
    run_days_elapsed    INTEGER,
    run_days_total      INTEGER,
    status              VARCHAR(30),
    feed_ethane_pct     NUMERIC(6,3),
    feed_propane_pct    NUMERIC(6,3),
    coke_thickness_1    NUMERIC(6,3),
    coke_thickness_2    NUMERIC(6,3),
    coke_thickness_3    NUMERIC(6,3),
    coke_thickness_4    NUMERIC(6,3),
    coke_thickness_5    NUMERIC(6,3),
    coke_thickness_6    NUMERIC(6,3),
    coke_thickness_7    NUMERIC(6,3),
    coke_thickness_8    NUMERIC(6,3)
);

CREATE INDEX idx_snapshot_upload ON furnace_snapshot(upload_id);
CREATE INDEX idx_snapshot_ts ON furnace_snapshot(snapshot_ts);
CREATE INDEX idx_snapshot_furnace ON furnace_snapshot(furnace_id);

CREATE TABLE coil_snapshot (
    id              SERIAL PRIMARY KEY,
    upload_id       INTEGER NOT NULL REFERENCES upload_history(id) ON DELETE CASCADE,
    snapshot_ts     TIMESTAMPTZ NOT NULL,
    furnace_id      VARCHAR(10) NOT NULL,
    coil_number     SMALLINT NOT NULL,
    feed            NUMERIC(8,3),
    cot             NUMERIC(6,2),
    shc             NUMERIC(5,3),
    cop             NUMERIC(6,2),
    cit             NUMERIC(6,2),
    thickness       NUMERIC(6,3),
    delta_hours     NUMERIC(8,2)
);

CREATE INDEX idx_coil_snap_upload ON coil_snapshot(upload_id);
CREATE INDEX idx_coil_snap_furnace ON coil_snapshot(furnace_id);

CREATE TABLE downstream_status (
    id                      SERIAL PRIMARY KEY,
    upload_id               INTEGER NOT NULL REFERENCES upload_history(id) ON DELETE CASCADE,
    snapshot_ts             TIMESTAMPTZ NOT NULL,
    c2_splitter_load_pct    NUMERIC(5,2),
    cgc_suction_bar         NUMERIC(5,3),
    cgc_power_mw            NUMERIC(8,2),
    cgc_vhp_steam_tph       NUMERIC(8,3)
);

CREATE INDEX idx_downstream_upload ON downstream_status(upload_id);

CREATE TABLE feed_composition (
    id                  SERIAL PRIMARY KEY,
    upload_id           INTEGER NOT NULL REFERENCES upload_history(id) ON DELETE CASCADE,
    snapshot_ts         TIMESTAMPTZ NOT NULL,
    furnace_id          VARCHAR(10) NOT NULL,
    ethane_pct          NUMERIC(6,3),
    propane_pct         NUMERIC(6,3),
    butane_pct          NUMERIC(6,3),
    other_pct           NUMERIC(6,3)
);

CREATE INDEX idx_feedcomp_upload ON feed_composition(upload_id);

-- =============================================================================
-- CONFIG TABLES (editable from UI)
-- =============================================================================

CREATE TABLE furnace_config (
    id              SERIAL PRIMARY KEY,
    furnace_id      VARCHAR(10) NOT NULL UNIQUE,
    technology      VARCHAR(30) NOT NULL,
    feed_type       VARCHAR(20) NOT NULL,
    num_passes      INTEGER DEFAULT 4,
    num_coils       INTEGER DEFAULT 8,
    design_capacity NUMERIC(8,2),
    max_cot         NUMERIC(6,1) DEFAULT 860.0,
    min_cot         NUMERIC(6,1) DEFAULT 800.0,
    max_feed_rate   NUMERIC(8,2),
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sensitivity_config (
    id              SERIAL PRIMARY KEY,
    technology      VARCHAR(30) NOT NULL,
    feed_type       VARCHAR(20) NOT NULL,
    parameter       VARCHAR(50) NOT NULL,
    sensitivity_type VARCHAR(20) NOT NULL DEFAULT 'per_cot_degC',
    value           NUMERIC(10,4) NOT NULL,
    unit            VARCHAR(30),
    source          VARCHAR(30) DEFAULT 'manual',
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(technology, feed_type, parameter, sensitivity_type)
);

CREATE TABLE economic_params (
    id          SERIAL PRIMARY KEY,
    param_name  VARCHAR(50) NOT NULL UNIQUE,
    value       NUMERIC(12,4) NOT NULL,
    unit        VARCHAR(30),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE constraint_limits (
    id              SERIAL PRIMARY KEY,
    constraint_name VARCHAR(50) NOT NULL UNIQUE,
    limit_value     NUMERIC(10,4) NOT NULL,
    unit            VARCHAR(30),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE cross_feed_config (
    id              SERIAL PRIMARY KEY,
    source_type     VARCHAR(20) NOT NULL,
    ethane_frac     NUMERIC(5,3) NOT NULL,
    propane_frac    NUMERIC(5,3) NOT NULL,
    other_frac      NUMERIC(5,3) NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_type)
);

CREATE TABLE model_registry (
    id              SERIAL PRIMARY KEY,
    model_name      VARCHAR(100) NOT NULL,
    technology      VARCHAR(30) NOT NULL,
    feed_type       VARCHAR(20) NOT NULL,
    target          VARCHAR(50) NOT NULL,
    algorithm       VARCHAR(50) DEFAULT 'GradientBoostingRegressor',
    hyperparams     JSONB,
    metrics         JSONB,
    model_blob      BYTEA,
    active          BOOLEAN DEFAULT FALSE,
    trained_at      TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_model_active ON model_registry(technology, feed_type, target, active);

-- =============================================================================
-- OUTPUT TABLES (written by optimizer / models)
-- =============================================================================

CREATE TABLE optimizer_results (
    id              SERIAL PRIMARY KEY,
    snapshot_id     INTEGER REFERENCES upload_history(id),
    run_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delta_feed_eth  NUMERIC(8,2) DEFAULT 0,
    delta_feed_prop NUMERIC(8,2) DEFAULT 0,
    ethane_purity   NUMERIC(6,3),
    propane_purity  NUMERIC(6,3),
    per_furnace     JSONB NOT NULL,
    fleet_totals    JSONB NOT NULL,
    config_used     JSONB,
    notes           TEXT
);

CREATE INDEX idx_optresults_snapshot ON optimizer_results(snapshot_id);

CREATE TABLE soft_sensor_predictions (
    id              SERIAL PRIMARY KEY,
    model_id        INTEGER REFERENCES model_registry(id),
    upload_id       INTEGER REFERENCES upload_history(id),
    furnace_id      VARCHAR(10) NOT NULL,
    predicted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    target          VARCHAR(50) NOT NULL,
    predicted_value NUMERIC(10,4),
    actual_value    NUMERIC(10,4),
    residual        NUMERIC(10,4)
);

CREATE INDEX idx_softpred_upload ON soft_sensor_predictions(upload_id);

CREATE TABLE runlength_forecast (
    id              SERIAL PRIMARY KEY,
    furnace_id      VARCHAR(10) NOT NULL,
    forecast_date   DATE NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    day_number      INTEGER NOT NULL,
    projected_tmt   NUMERIC(6,1),
    projected_coke  NUMERIC(6,3),
    projected_yield NUMERIC(5,2),
    remaining_days  INTEGER,
    confidence      NUMERIC(4,2)
);

CREATE INDEX idx_runforecast_furnace ON runlength_forecast(furnace_id);

CREATE TABLE audit_log (
    id          SERIAL PRIMARY KEY,
    action      VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id   VARCHAR(50),
    user_name   VARCHAR(100) DEFAULT 'system',
    details     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_created ON audit_log(created_at);

-- =============================================================================
-- SEED DATA
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Furnace Config (8 furnaces)
-- ---------------------------------------------------------------------------
INSERT INTO furnace_config (furnace_id, technology, feed_type, num_passes, num_coils, design_capacity, max_cot, min_cot, max_feed_rate)
VALUES
    ('AF-01', 'Lummus',  'Ethane',  4, 8, 60.0, 860.0, 800.0, 65.0),
    ('AF-02', 'Lummus',  'Ethane',  4, 8, 60.0, 860.0, 800.0, 65.0),
    ('AF-03', 'Lummus',  'Propane', 4, 8, 85.0, 860.0, 800.0, 90.0),
    ('AF-04', 'Lummus',  'Propane', 4, 8, 85.0, 860.0, 800.0, 90.0),
    ('AF-05', 'Lummus',  'Propane', 4, 8, 85.0, 860.0, 800.0, 90.0),
    ('AF-06', 'Lummus',  'Propane', 4, 8, 85.0, 860.0, 800.0, 90.0),
    ('AF-07', 'Lummus',  'Propane', 4, 8, 85.0, 860.0, 800.0, 90.0),
    ('AF-08', 'Technip', 'Ethane',  2, 8, 35.0, 860.0, 800.0, 40.0);

-- ---------------------------------------------------------------------------
-- Sensitivity Config — per °C COT increase
-- ---------------------------------------------------------------------------
INSERT INTO sensitivity_config (technology, feed_type, parameter, sensitivity_type, value, unit, source)
VALUES
    -- Lummus Ethane
    ('Lummus', 'Ethane', 'ethylene_yield',  'per_cot_degC',  0.218, '%/°C',       'manual'),
    ('Lummus', 'Ethane', 'propylene',       'per_cot_degC', -0.017, '%/°C',       'manual'),
    ('Lummus', 'Ethane', 'conversion',      'per_cot_degC',  0.480, '%/°C',       'manual'),
    ('Lummus', 'Ethane', 'tmt',             'per_cot_degC',  1.660, '°C/°C',      'manual'),
    ('Lummus', 'Ethane', 'run_length',      'per_cot_degC', -3.000, 'd/°C',       'manual'),
    ('Lummus', 'Ethane', 'run_length_shc',  'per_shc_001',  10.000, 'd/0.01 SHC', 'manual'),
    ('Lummus', 'Ethane', 'coking_rate',     'per_cot_degC',  1.050, 'units/°C',   'manual'),

    -- Lummus Propane
    ('Lummus', 'Propane', 'ethylene_yield', 'per_cot_degC',  0.218, '%/°C',       'manual'),
    ('Lummus', 'Propane', 'propylene',      'per_cot_degC', -0.136, '%/°C',       'manual'),
    ('Lummus', 'Propane', 'conversion',     'per_cot_degC',  0.405, '%/°C',       'manual'),
    ('Lummus', 'Propane', 'tmt',            'per_cot_degC',  1.540, '°C/°C',      'manual'),
    ('Lummus', 'Propane', 'run_length',     'per_cot_degC', -2.500, 'd/°C',       'manual'),
    ('Lummus', 'Propane', 'run_length_shc', 'per_shc_001',   7.500, 'd/0.01 SHC', 'manual'),
    ('Lummus', 'Propane', 'coking_rate',    'per_cot_degC',  0.450, 'units/°C',   'manual'),

    -- Technip Ethane
    ('Technip', 'Ethane', 'ethylene_yield', 'per_cot_degC',  0.200, '%/°C',       'manual'),
    ('Technip', 'Ethane', 'propylene',      'per_cot_degC', -0.015, '%/°C',       'manual'),
    ('Technip', 'Ethane', 'conversion',     'per_cot_degC',  0.450, '%/°C',       'manual'),
    ('Technip', 'Ethane', 'tmt',            'per_cot_degC',  1.700, '°C/°C',      'manual'),
    ('Technip', 'Ethane', 'run_length',     'per_cot_degC', -4.500, 'd/°C',       'manual'),
    ('Technip', 'Ethane', 'run_length_shc', 'per_shc_001',  12.000, 'd/0.01 SHC', 'manual'),
    ('Technip', 'Ethane', 'coking_rate',    'per_cot_degC',  0.800, 'units/°C',   'manual');

-- ---------------------------------------------------------------------------
-- Composition Sensitivities (per 1% change in ethane fraction)
-- ---------------------------------------------------------------------------
INSERT INTO sensitivity_config (technology, feed_type, parameter, sensitivity_type, value, unit, source)
VALUES
    ('ALL', 'ALL', 'yield',       'per_ethane_pct',  0.220, '%yield/%ethane', 'manual'),
    ('ALL', 'ALL', 'propylene',   'per_ethane_pct', -0.160, '%prop/%ethane',  'manual'),
    ('ALL', 'ALL', 'conversion',  'per_ethane_pct', -0.050, '%conv/%ethane',  'manual'),
    ('ALL', 'ALL', 'sec',         'per_ethane_pct', -0.015, 'SEC/%ethane',    'manual'),
    ('ALL', 'ALL', 'coking_rate', 'per_ethane_pct',  0.080, 'rate/%ethane',   'manual');

-- ---------------------------------------------------------------------------
-- Coking Factors for Thickness Evolution (dimensionless multiplier)
-- effective_thickness = prev + coking_factor * predicted_coking_rate * (delta_hours / 720)
-- ---------------------------------------------------------------------------
INSERT INTO sensitivity_config (technology, feed_type, parameter, sensitivity_type, value, unit, source)
VALUES
    ('Lummus',  'Ethane',  'coking_factor', 'thickness_evolution', 0.3150, 'dimensionless', 'manual'),
    ('Lummus',  'Propane', 'coking_factor', 'thickness_evolution', 0.7100, 'dimensionless', 'manual'),
    ('Technip', 'Ethane',  'coking_factor', 'thickness_evolution', 0.9000, 'dimensionless', 'manual'),
    ('Technip', 'Propane', 'coking_factor', 'thickness_evolution', 0.9000, 'dimensionless', 'manual');

-- ---------------------------------------------------------------------------
-- Economic Parameters
-- ---------------------------------------------------------------------------
INSERT INTO economic_params (param_name, value, unit)
VALUES
    ('ethylene_price',   1050.0000, '$/ton'),
    ('propylene_price',   900.0000, '$/ton'),
    ('fuel_gas_cost',       8.5000, '$/GJ'),
    ('ethane_feed_cost',  350.0000, '$/ton'),
    ('propane_feed_cost', 320.0000, '$/ton'),
    ('decoke_cost',    150000.0000, '$/event'),
    ('decoke_downtime',     3.0000, 'days'),
    ('vhp_steam_cost',     25.0000, '$/ton');

-- ---------------------------------------------------------------------------
-- Constraint Limits
-- ---------------------------------------------------------------------------
INSERT INTO constraint_limits (constraint_name, limit_value, unit)
VALUES
    ('feed_valve_max',      85.0000, '%'),
    ('fgv_max',             85.0000, '%'),
    ('damper_max',          88.0000, '%'),
    ('tmt_alarm',         1075.0000, '°C'),
    ('tmt_warning',       1060.0000, '°C'),
    ('c2_splitter_max',     90.0000, '%'),
    ('cgc_suction_max',      0.4500, 'bar');

-- ---------------------------------------------------------------------------
-- Cross-Feed Config (unreacted stream fractions)
-- ---------------------------------------------------------------------------
INSERT INTO cross_feed_config (source_type, ethane_frac, propane_frac, other_frac)
VALUES
    ('Ethane',  0.950, 0.030, 0.020),
    ('Propane', 0.150, 0.780, 0.070);

-- ---------------------------------------------------------------------------
-- Seed Upload + Snapshot (initial fleet data from CLAUDE.md)
-- ---------------------------------------------------------------------------
INSERT INTO upload_history (filename, uploaded_by, uploaded_at, row_count, validation_ok, snapshot_ts)
VALUES ('seed_data.xlsx', 'system', NOW(), 8, TRUE, NOW());

-- Get the upload_id (will be 1 for fresh DB)
INSERT INTO furnace_snapshot (
    upload_id, snapshot_ts, furnace_id,
    feed_rate, cot, shc, cop, cit,
    tmt_max, yield, conversion, coking_rate, propylene,
    feed_valve_pct, fgv_pct, damper_pct, sec,
    run_days_elapsed, run_days_total, status,
    feed_ethane_pct, feed_propane_pct,
    coke_thickness_1, coke_thickness_2, coke_thickness_3, coke_thickness_4,
    coke_thickness_5, coke_thickness_6, coke_thickness_7, coke_thickness_8
)
VALUES
    -- AF-01: Lummus Ethane, online (protect) — runDays=45 < 60
    (1, NOW(), 'AF-01',
     54.00, 838.00, 0.330, 26.50, 140.00,
     1058.0, 49.20, 64.80, 1.200, 1.80,
     72.00, 72.00, 70.00, 3.200,
     45, 180, 'online (protect)',
     97.090, 2.910,
     2.10, 2.20, 2.15, 2.30, 2.25, 2.18, 2.22, 2.12),

    -- AF-02: Lummus Ethane, online (healthy)
    (1, NOW(), 'AF-02',
     56.00, 835.00, 0.320, 26.00, 138.00,
     1045.0, 48.80, 63.50, 1.100, 1.90,
     74.00, 68.00, 68.00, 3.150,
     62, 200, 'online (healthy)',
     97.090, 2.910,
     1.80, 1.90, 1.85, 1.95, 1.88, 1.82, 1.87, 1.79),

    -- AF-03: Lummus Propane, online (healthy)
    (1, NOW(), 'AF-03',
     76.00, 830.00, 0.350, 25.50, 135.00,
     1052.0, 29.10, 77.40, 0.800, 14.20,
     78.00, 65.00, 72.00, 3.500,
     89, 220, 'online (healthy)',
     7.830, 92.170,
     1.50, 1.60, 1.55, 1.65, 1.58, 1.52, 1.57, 1.48),

    -- AF-04: Lummus Propane, online (protect) — runDays=28 < 60
    (1, NOW(), 'AF-04',
     52.00, 842.00, 0.340, 27.00, 142.00,
     1068.0, 31.50, 82.00, 1.500, 13.50,
     65.00, 78.00, 75.00, 3.600,
     28, 150, 'online (protect)',
     7.700, 92.300,
     2.80, 2.90, 2.85, 3.00, 2.95, 2.82, 2.88, 2.78),

    -- AF-05: Lummus Propane, decoke
    (1, NOW(), 'AF-05',
     0.00, 0.00, 0.000, 0.00, 0.00,
     0.0, 0.00, 0.00, 0.000, 0.00,
     0.00, 0.00, 0.00, 0.000,
     0, 0, 'decoke',
     0.000, 0.000,
     0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00),

    -- AF-06: Lummus Propane, online (healthy)
    (1, NOW(), 'AF-06',
     68.00, 832.00, 0.350, 25.80, 136.00,
     1048.0, 29.80, 78.20, 0.750, 14.00,
     76.00, 66.00, 71.00, 3.450,
     95, 230, 'online (healthy)',
     7.830, 92.170,
     1.40, 1.50, 1.45, 1.55, 1.48, 1.42, 1.47, 1.38),

    -- AF-07: Lummus Propane, online (healthy)
    (1, NOW(), 'AF-07',
     72.00, 828.00, 0.360, 25.20, 134.00,
     1040.0, 28.50, 76.00, 0.700, 13.80,
     80.00, 60.00, 69.00, 3.400,
     110, 240, 'online (healthy)',
     2.040, 97.960,
     1.20, 1.30, 1.25, 1.35, 1.28, 1.22, 1.27, 1.18),

    -- AF-08: Technip Ethane, online (healthy)
    (1, NOW(), 'AF-08',
     30.00, 830.00, 0.320, 24.00, 130.00,
     1010.0, 34.20, 64.00, 0.600, 2.50,
     60.00, 58.00, 62.00, 3.100,
     120, 250, 'online (healthy)',
     98.570, 1.430,
     1.00, 1.10, 1.05, 1.15, 1.08, 1.02, 1.07, 0.98);

-- ---------------------------------------------------------------------------
-- Seed Coil Snapshots (per-coil X variables, 8 coils per furnace)
-- Per-coil COT/SHC/COP/CIT vary slightly across coils (radiant section position)
-- Thickness from existing seed data, delta_hours=24 (daily upload)
-- Feed = furnace_feed_rate / 8
-- ---------------------------------------------------------------------------
INSERT INTO coil_snapshot (upload_id, snapshot_ts, furnace_id, coil_number,
    feed, cot, shc, cop, cit, thickness, delta_hours)
VALUES
    -- AF-01: Lummus Ethane, feed=54 t/hr → 6.75/coil, COT=838 base
    (1, NOW(), 'AF-01', 1, 6.750, 839.2, 0.331, 26.60, 140.5, 2.10, 24.0),
    (1, NOW(), 'AF-01', 2, 6.750, 837.5, 0.329, 26.40, 139.8, 2.20, 24.0),
    (1, NOW(), 'AF-01', 3, 6.750, 838.8, 0.332, 26.55, 140.2, 2.15, 24.0),
    (1, NOW(), 'AF-01', 4, 6.750, 836.0, 0.328, 26.30, 139.0, 2.30, 24.0),
    (1, NOW(), 'AF-01', 5, 6.750, 838.0, 0.330, 26.50, 140.0, 2.25, 24.0),
    (1, NOW(), 'AF-01', 6, 6.750, 839.5, 0.333, 26.65, 140.8, 2.18, 24.0),
    (1, NOW(), 'AF-01', 7, 6.750, 837.0, 0.329, 26.35, 139.5, 2.22, 24.0),
    (1, NOW(), 'AF-01', 8, 6.750, 838.5, 0.331, 26.50, 140.3, 2.12, 24.0),

    -- AF-02: Lummus Ethane, feed=56 t/hr → 7.0/coil, COT=835 base
    (1, NOW(), 'AF-02', 1, 7.000, 836.2, 0.321, 26.10, 138.5, 1.80, 24.0),
    (1, NOW(), 'AF-02', 2, 7.000, 834.5, 0.319, 25.90, 137.8, 1.90, 24.0),
    (1, NOW(), 'AF-02', 3, 7.000, 835.8, 0.322, 26.05, 138.2, 1.85, 24.0),
    (1, NOW(), 'AF-02', 4, 7.000, 833.5, 0.318, 25.80, 137.0, 1.95, 24.0),
    (1, NOW(), 'AF-02', 5, 7.000, 835.0, 0.320, 26.00, 138.0, 1.88, 24.0),
    (1, NOW(), 'AF-02', 6, 7.000, 836.5, 0.323, 26.15, 138.8, 1.82, 24.0),
    (1, NOW(), 'AF-02', 7, 7.000, 834.0, 0.319, 25.85, 137.5, 1.87, 24.0),
    (1, NOW(), 'AF-02', 8, 7.000, 835.5, 0.321, 26.00, 138.3, 1.79, 24.0),

    -- AF-03: Lummus Propane, feed=76 t/hr → 9.5/coil, COT=830 base
    (1, NOW(), 'AF-03', 1, 9.500, 831.2, 0.351, 25.60, 135.5, 1.50, 24.0),
    (1, NOW(), 'AF-03', 2, 9.500, 829.5, 0.349, 25.40, 134.8, 1.60, 24.0),
    (1, NOW(), 'AF-03', 3, 9.500, 830.8, 0.352, 25.55, 135.2, 1.55, 24.0),
    (1, NOW(), 'AF-03', 4, 9.500, 828.5, 0.348, 25.30, 134.0, 1.65, 24.0),
    (1, NOW(), 'AF-03', 5, 9.500, 830.0, 0.350, 25.50, 135.0, 1.58, 24.0),
    (1, NOW(), 'AF-03', 6, 9.500, 831.5, 0.353, 25.65, 135.8, 1.52, 24.0),
    (1, NOW(), 'AF-03', 7, 9.500, 829.0, 0.349, 25.35, 134.5, 1.57, 24.0),
    (1, NOW(), 'AF-03', 8, 9.500, 830.5, 0.351, 25.50, 135.3, 1.48, 24.0),

    -- AF-04: Lummus Propane, feed=52 t/hr → 6.5/coil, COT=842 base
    (1, NOW(), 'AF-04', 1, 6.500, 843.2, 0.341, 27.10, 142.5, 2.80, 24.0),
    (1, NOW(), 'AF-04', 2, 6.500, 841.5, 0.339, 26.90, 141.8, 2.90, 24.0),
    (1, NOW(), 'AF-04', 3, 6.500, 842.8, 0.342, 27.05, 142.2, 2.85, 24.0),
    (1, NOW(), 'AF-04', 4, 6.500, 840.5, 0.338, 26.80, 141.0, 3.00, 24.0),
    (1, NOW(), 'AF-04', 5, 6.500, 842.0, 0.340, 27.00, 142.0, 2.95, 24.0),
    (1, NOW(), 'AF-04', 6, 6.500, 843.5, 0.343, 27.15, 142.8, 2.82, 24.0),
    (1, NOW(), 'AF-04', 7, 6.500, 841.0, 0.339, 26.85, 141.5, 2.88, 24.0),
    (1, NOW(), 'AF-04', 8, 6.500, 842.5, 0.341, 27.00, 142.3, 2.78, 24.0),

    -- AF-05: Lummus Propane, decoke (all zeros)
    (1, NOW(), 'AF-05', 1, 0.000, 0.00, 0.000, 0.00, 0.0, 0.00, 0.0),
    (1, NOW(), 'AF-05', 2, 0.000, 0.00, 0.000, 0.00, 0.0, 0.00, 0.0),
    (1, NOW(), 'AF-05', 3, 0.000, 0.00, 0.000, 0.00, 0.0, 0.00, 0.0),
    (1, NOW(), 'AF-05', 4, 0.000, 0.00, 0.000, 0.00, 0.0, 0.00, 0.0),
    (1, NOW(), 'AF-05', 5, 0.000, 0.00, 0.000, 0.00, 0.0, 0.00, 0.0),
    (1, NOW(), 'AF-05', 6, 0.000, 0.00, 0.000, 0.00, 0.0, 0.00, 0.0),
    (1, NOW(), 'AF-05', 7, 0.000, 0.00, 0.000, 0.00, 0.0, 0.00, 0.0),
    (1, NOW(), 'AF-05', 8, 0.000, 0.00, 0.000, 0.00, 0.0, 0.00, 0.0),

    -- AF-06: Lummus Propane, feed=68 t/hr → 8.5/coil, COT=832 base
    (1, NOW(), 'AF-06', 1, 8.500, 833.2, 0.351, 25.90, 136.5, 1.40, 24.0),
    (1, NOW(), 'AF-06', 2, 8.500, 831.5, 0.349, 25.70, 135.8, 1.50, 24.0),
    (1, NOW(), 'AF-06', 3, 8.500, 832.8, 0.352, 25.85, 136.2, 1.45, 24.0),
    (1, NOW(), 'AF-06', 4, 8.500, 830.5, 0.348, 25.60, 135.0, 1.55, 24.0),
    (1, NOW(), 'AF-06', 5, 8.500, 832.0, 0.350, 25.80, 136.0, 1.48, 24.0),
    (1, NOW(), 'AF-06', 6, 8.500, 833.5, 0.353, 25.95, 136.8, 1.42, 24.0),
    (1, NOW(), 'AF-06', 7, 8.500, 831.0, 0.349, 25.65, 135.5, 1.47, 24.0),
    (1, NOW(), 'AF-06', 8, 8.500, 832.5, 0.351, 25.80, 136.3, 1.38, 24.0),

    -- AF-07: Lummus Propane, feed=72 t/hr → 9.0/coil, COT=828 base
    (1, NOW(), 'AF-07', 1, 9.000, 829.2, 0.361, 25.30, 134.5, 1.20, 24.0),
    (1, NOW(), 'AF-07', 2, 9.000, 827.5, 0.359, 25.10, 133.8, 1.30, 24.0),
    (1, NOW(), 'AF-07', 3, 9.000, 828.8, 0.362, 25.25, 134.2, 1.25, 24.0),
    (1, NOW(), 'AF-07', 4, 9.000, 826.5, 0.358, 25.00, 133.0, 1.35, 24.0),
    (1, NOW(), 'AF-07', 5, 9.000, 828.0, 0.360, 25.20, 134.0, 1.28, 24.0),
    (1, NOW(), 'AF-07', 6, 9.000, 829.5, 0.363, 25.35, 134.8, 1.22, 24.0),
    (1, NOW(), 'AF-07', 7, 9.000, 827.0, 0.359, 25.05, 133.5, 1.27, 24.0),
    (1, NOW(), 'AF-07', 8, 9.000, 828.5, 0.361, 25.20, 134.3, 1.18, 24.0),

    -- AF-08: Technip Ethane, feed=30 t/hr → 3.75/coil, COT=830 base
    (1, NOW(), 'AF-08', 1, 3.750, 831.2, 0.321, 24.10, 130.5, 1.00, 24.0),
    (1, NOW(), 'AF-08', 2, 3.750, 829.5, 0.319, 23.90, 129.8, 1.10, 24.0),
    (1, NOW(), 'AF-08', 3, 3.750, 830.8, 0.322, 24.05, 130.2, 1.05, 24.0),
    (1, NOW(), 'AF-08', 4, 3.750, 828.5, 0.318, 23.80, 129.0, 1.15, 24.0),
    (1, NOW(), 'AF-08', 5, 3.750, 830.0, 0.320, 24.00, 130.0, 1.08, 24.0),
    (1, NOW(), 'AF-08', 6, 3.750, 831.5, 0.323, 24.15, 130.8, 1.02, 24.0),
    (1, NOW(), 'AF-08', 7, 3.750, 829.0, 0.319, 23.85, 129.5, 1.07, 24.0),
    (1, NOW(), 'AF-08', 8, 3.750, 830.5, 0.321, 24.00, 130.3, 0.98, 24.0);

-- ---------------------------------------------------------------------------
-- Seed Downstream Status
-- ---------------------------------------------------------------------------
INSERT INTO downstream_status (upload_id, snapshot_ts, c2_splitter_load_pct, cgc_suction_bar, cgc_power_mw, cgc_vhp_steam_tph)
VALUES (1, NOW(), 72.50, 0.380, 28.50, 42.300);

-- ---------------------------------------------------------------------------
-- Seed Audit Log
-- ---------------------------------------------------------------------------
INSERT INTO audit_log (action, entity_type, entity_id, user_name, details)
VALUES ('database_initialized', 'system', NULL, 'system', '{"message": "Database initialized with seed data"}');

-- =============================================================================
-- Done
-- =============================================================================
