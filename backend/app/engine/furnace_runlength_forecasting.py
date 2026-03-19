"""
================================================================================
ETHYLENE FURNACE RUNLENGTH FORECASTING ENGINE
================================================================================
Purpose:
    Build soft-sensor models for each furnace technology + feed combination
    to predict ALL dependent process variables from operating conditions.
    Use coking rate model to forecast coke thickness accumulation over time
    and predict remaining run length before TMT limit is reached.

Architecture:
    - 4 Model Sets: Lummus-Ethane, Lummus-Propane, Technip-Ethane, Technip-Propane
    - Independent Variables (X):
        Feed (per coil), SHC, COT, COP, CIT, Feed_Composition (Ethane/Propane%),
        Coke Thickness (current)
    - Target Variables (Y) — Soft Sensors:
        yield, Coking_rate, tmt, heat_absorbed, conversion,
        acetylene/c2h2, benzene, c4h4, styrene, propane, propylene, ethane,
        isoprene, butadiene, methane, hydrogen, residence_time
    - Runlength Forecasting:
        Uses coking rate model + TMT model to project day-by-day coke buildup
        until TMT hits the alarm limit (1075°C) or coil thickness limit.

Coil Configuration:
    Lummus:  4 passes × 2 coils/pass = 8 coils per furnace
    Technip: 6 passes × 1 coil/pass  = 6 coils per furnace
    Feed per coil = Total furnace feed / number of coils

Usage:
    python furnace_runlength_forecasting.py
================================================================================
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error, mean_absolute_percentage_error
from sklearn.preprocessing import StandardScaler
import warnings
import json
from datetime import datetime

warnings.filterwarnings('ignore')

# =============================================================================
# SECTION 1: DATA LOADING & HARMONIZATION
# =============================================================================

def load_and_harmonize_data(file_path, technology, feed_type):
    """Load simulation data and harmonize column names across all 4 datasets."""
    df = pd.read_excel(file_path)

    # Standardize column mapping per technology
    if technology == 'Lummus':
        col_map = {
            'FEED': 'feed', 'SHC': 'shc', 'CIT': 'cit', 'COT': 'cot',
            'COP_actual': 'cop', 'Feed_Ethane': 'feed_ethane_pct',
            'Feed_Propane': 'feed_propane_pct', 'thickness': 'thickness',
            'CIP_val': 'cip_val', 'yield': 'yield_c2h4', 'Coking_rate': 'coking_rate',
            'tmt': 'tmt', 'heat_absorbed': 'heat_absorbed', 'conversion': 'conversion',
            'acetylene': 'acetylene', 'benzene': 'benzene', 'c4h4': 'c4h4',
            'styrene': 'styrene', 'propane': 'propane_out', 'propylene': 'propylene',
            'ethane': 'ethane_out', 'isoprene': 'isoprene', 'butadiene': 'butadiene',
            'methane': 'methane', 'hydrogen': 'hydrogen',
            'residence_time': 'residence_time', 'runlength': 'runlength',
            'tmt_height': 'tmt_height'
        }
    else:  # Technip
        col_map = {
            'Feed': 'feed', 'SHC': 'shc', 'CIT': 'cit', 'Cot': 'cot',
            'COP': 'cop', 'Propane': 'feed_propane_pct',
            'thickness': 'thickness', 'CIP_val': 'cip_val',
            'yield': 'yield_c2h4', 'Coking_rate': 'coking_rate',
            'tmt': 'tmt', 'heat_absorbed': 'heat_absorbed', 'conversion': 'conversion',
            'c2h2': 'acetylene', 'benezene': 'benzene', 'c4h4': 'c4h4',
            'styrene': 'styrene', 'propane': 'propane_out', 'propylene': 'propylene',
            'ethane': 'ethane_out', 'isoprene': 'isoprene', 'butadiene': 'butadiene',
            'methane': 'methane', 'hydrogen': 'hydrogen',
            'Residence_time': 'residence_time', 'runlength': 'runlength'
        }
        if 'delta_p' in df.columns:
            col_map['delta_p'] = 'delta_p'

    # Apply mapping (only for columns that exist)
    rename_dict = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename_dict)

    # Derive feed_ethane_pct for Technip (100 - propane%)
    if 'feed_ethane_pct' not in df.columns and 'feed_propane_pct' in df.columns:
        df['feed_ethane_pct'] = 100.0 - df['feed_propane_pct']

    # Derive feed_propane_pct for Lummus ethane if missing
    if 'feed_propane_pct' not in df.columns and 'feed_ethane_pct' in df.columns:
        df['feed_propane_pct'] = 100.0 - df['feed_ethane_pct']

    df['technology'] = technology
    df['feed_type'] = feed_type

    return df


def load_all_datasets(file_paths):
    """Load all 4 datasets."""
    datasets = {}
    configs = [
        ('lummus_ethane', 'Lummus', 'Ethane'),
        ('lummus_propane', 'Lummus', 'Propane'),
        ('technip_ethane', 'Technip', 'Ethane'),
        ('technip_propane', 'Technip', 'Propane'),
    ]
    for (key, tech, feed), fpath in zip(configs, file_paths):
        datasets[key] = load_and_harmonize_data(fpath, tech, feed)
        print(f"  Loaded {key}: {datasets[key].shape[0]:,} rows, {datasets[key].shape[1]} columns")
    return datasets


# =============================================================================
# SECTION 2: FEATURE & TARGET DEFINITIONS
# =============================================================================

# Independent variables (X features) — same for all models
INDEPENDENT_VARS = ['feed', 'shc', 'cot', 'cop', 'cit', 'feed_ethane_pct', 'feed_propane_pct', 'thickness']

# Target variables (Y) — soft sensor outputs
TARGET_VARS = [
    'coking_rate', 'tmt', 'yield_c2h4', 'heat_absorbed', 'conversion',
    'acetylene', 'benzene', 'c4h4', 'styrene', 'propane_out', 'propylene',
    'ethane_out', 'isoprene', 'butadiene', 'methane', 'hydrogen'
]

# Critical targets for runlength forecasting
CRITICAL_TARGETS = ['coking_rate', 'tmt']


# =============================================================================
# SECTION 3: SOFT SENSOR MODEL BUILDER
# =============================================================================

class FurnaceSoftSensorModels:
    """Builds and stores GBR soft-sensor models for one technology-feed combination."""

    def __init__(self, name, n_estimators=200, max_depth=5, learning_rate=0.1):
        self.name = name
        self.models = {}
        self.scalers = {}
        self.metrics = {}
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.feature_names = None

    def build(self, df, features=INDEPENDENT_VARS, targets=TARGET_VARS, test_size=0.2):
        """Train a GBR model for each target variable."""
        available_targets = [t for t in targets if t in df.columns and df[t].notna().sum() > 100]
        available_features = [f for f in features if f in df.columns and df[f].notna().sum() > 100]
        self.feature_names = available_features

        X = df[available_features].dropna()
        valid_idx = X.index

        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        self.scalers['X'] = scaler

        print(f"\n{'='*70}")
        print(f"  MODEL SET: {self.name}")
        print(f"  Training samples: {len(X):,}  |  Features: {len(available_features)}")
        print(f"  Features: {available_features}")
        print(f"{'='*70}")
        print(f"  {'Target':<18} {'R² Train':>10} {'R² Test':>10} {'MAE':>12} {'MAPE(%)':>10}")
        print(f"  {'-'*62}")

        for target in available_targets:
            y = df.loc[valid_idx, target].copy()
            mask = y.notna()
            X_t = X_scaled[mask]
            y_t = y[mask].values

            if len(y_t) < 50:
                continue

            X_train, X_test, y_train, y_test = train_test_split(
                X_t, y_t, test_size=test_size, random_state=42
            )

            model = GradientBoostingRegressor(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                subsample=0.8,
                random_state=42
            )
            model.fit(X_train, y_train)

            y_pred_train = model.predict(X_train)
            y_pred_test = model.predict(X_test)

            r2_train = r2_score(y_train, y_pred_train)
            r2_test = r2_score(y_test, y_pred_test)
            mae = mean_absolute_error(y_test, y_pred_test)
            # Avoid division by zero in MAPE
            nonzero = np.abs(y_test) > 1e-6
            if nonzero.sum() > 0:
                mape = mean_absolute_percentage_error(y_test[nonzero], y_pred_test[nonzero]) * 100
            else:
                mape = np.nan

            self.models[target] = model
            self.metrics[target] = {
                'r2_train': round(r2_train, 5),
                'r2_test': round(r2_test, 5),
                'mae': round(mae, 5),
                'mape_pct': round(mape, 3) if not np.isnan(mape) else None,
                'n_train': len(y_train),
                'n_test': len(y_test)
            }

            print(f"  {target:<18} {r2_train:>10.5f} {r2_test:>10.5f} {mae:>12.5f} {mape:>10.3f}")

        return self

    def predict(self, X_input):
        """Predict all targets for given input features (dict or DataFrame row)."""
        if isinstance(X_input, dict):
            X_df = pd.DataFrame([X_input])
        else:
            X_df = X_input.copy()

        X_arr = X_df[self.feature_names].values
        X_scaled = self.scalers['X'].transform(X_arr)

        results = {}
        for target, model in self.models.items():
            results[target] = model.predict(X_scaled)[0]
        return results

    def get_accuracy_summary(self):
        """Return accuracy table as DataFrame."""
        rows = []
        for target, m in self.metrics.items():
            rows.append({
                'Model_Set': self.name,
                'Target_Variable': target,
                'R2_Train': m['r2_train'],
                'R2_Test': m['r2_test'],
                'MAE': m['mae'],
                'MAPE_%': m['mape_pct'],
                'N_Train': m['n_train'],
                'N_Test': m['n_test']
            })
        return pd.DataFrame(rows)


# =============================================================================
# SECTION 4: RUNLENGTH FORECASTING ENGINE
# =============================================================================

class RunlengthForecaster:
    """
    Forecasts remaining run length for a single coil by day-by-day
    coke thickness accumulation using soft-sensor predicted coking rate & TMT.

    Logic:
        1. Start with current coke thickness (from CIP model or sensor)
        2. For each future day:
           a. Predict coking_rate and tmt at current thickness + operating conditions
           b. Accumulate: thickness += coking_rate * delta_time_factor
           c. Check TMT against alarm limit (1075°C)
           d. Check thickness against max allowable
        3. The day TMT hits limit OR thickness exceeds max = end of run
    """

    TMT_ALARM_LIMIT = 1075.0       # °C — hard alarm
    TMT_WARNING_LIMIT = 1060.0     # °C — soft warning
    MAX_THICKNESS_LUMMUS = 12.0    # mm — max coke thickness before mandatory decoke
    MAX_THICKNESS_TECHNIP = 16.0   # mm
    DAYS_PER_STEP = 1              # forecast resolution in days
    # Coking rate from simulation is in arbitrary units per runlength step
    # thickness growth per day ≈ coking_rate * thickness_factor
    # This factor is calibrated from data: observe thickness range / runlength range
    THICKNESS_FACTOR_LUMMUS = 5.5   # ~(12mm / ~200 days) * rate normalization
    THICKNESS_FACTOR_TECHNIP = 0.30 # Technip thickness is in smaller units

    def __init__(self, model_set: FurnaceSoftSensorModels, technology: str):
        self.model_set = model_set
        self.technology = technology
        self.max_thickness = (self.MAX_THICKNESS_LUMMUS if technology == 'Lummus'
                              else self.MAX_THICKNESS_TECHNIP)
        self.thickness_factor = (self.THICKNESS_FACTOR_LUMMUS if technology == 'Lummus'
                                 else self.THICKNESS_FACTOR_TECHNIP)

    def forecast(self, operating_conditions: dict, current_thickness: float,
                 max_days: int = 365):
        """
        Forecast run length from current state.

        Parameters:
            operating_conditions: dict with keys matching INDEPENDENT_VARS
                                 (thickness will be overridden during simulation)
            current_thickness: current coke thickness (mm)
            max_days: maximum forecast horizon

        Returns:
            dict with forecast results including day-by-day trajectory
        """
        trajectory = []
        thickness = current_thickness
        end_reason = None
        days_remaining = 0

        for day in range(1, max_days + 1):
            # Update thickness in operating conditions
            conditions = operating_conditions.copy()
            conditions['thickness'] = thickness

            # Predict coking rate and TMT at current state
            predictions = self.model_set.predict(conditions)
            coking_rate = predictions.get('coking_rate', 0)
            tmt = predictions.get('tmt', 0)
            yield_val = predictions.get('yield_c2h4', 0)
            conversion = predictions.get('conversion', 0)

            trajectory.append({
                'day': day,
                'thickness_mm': round(thickness, 4),
                'coking_rate': round(coking_rate, 4),
                'tmt_predicted': round(tmt, 2),
                'yield_c2h4': round(yield_val, 3),
                'conversion': round(conversion, 3)
            })

            # Check termination conditions
            if tmt >= self.TMT_ALARM_LIMIT:
                end_reason = f'TMT alarm limit reached ({tmt:.1f} >= {self.TMT_ALARM_LIMIT}°C)'
                days_remaining = day
                break

            if thickness >= self.max_thickness:
                end_reason = f'Max coke thickness reached ({thickness:.2f} >= {self.max_thickness} mm)'
                days_remaining = day
                break

            # Accumulate coke thickness
            # thickness_increment = coking_rate * factor / normalization
            thickness += coking_rate * self.thickness_factor / 1000.0

        if end_reason is None:
            end_reason = f'Forecast horizon reached ({max_days} days) — no limit hit'
            days_remaining = max_days

        return {
            'technology': self.technology,
            'days_remaining': days_remaining,
            'end_reason': end_reason,
            'initial_thickness': current_thickness,
            'final_thickness': round(thickness, 4),
            'final_tmt': trajectory[-1]['tmt_predicted'] if trajectory else None,
            'tmt_warning_day': next(
                (t['day'] for t in trajectory if t['tmt_predicted'] >= self.TMT_WARNING_LIMIT),
                None
            ),
            'trajectory': trajectory
        }


# =============================================================================
# SECTION 5: MULTI-COIL FURNACE FORECASTER
# =============================================================================

class FurnaceRunlengthForecaster:
    """
    Forecast runlength for an entire furnace (all coils).
    The furnace runlength = minimum runlength across all coils.
    """

    def __init__(self, technology, model_set, num_passes, coils_per_pass):
        self.technology = technology
        self.model_set = model_set
        self.num_passes = num_passes
        self.coils_per_pass = coils_per_pass
        self.total_coils = num_passes * coils_per_pass
        self.forecaster = RunlengthForecaster(model_set, technology)

    def forecast_furnace(self, furnace_feed_total, shc, cot, cop, cit,
                         feed_ethane_pct, feed_propane_pct,
                         current_thicknesses: list, max_days=365):
        """
        Forecast for all coils in a furnace.

        Parameters:
            furnace_feed_total: total furnace feed rate (t/hr)
            current_thicknesses: list of current coke thickness per coil
            Other params: operating conditions (uniform across coils)

        Returns:
            dict with per-coil and furnace-level forecast
        """
        feed_per_coil = furnace_feed_total / self.total_coils

        if len(current_thicknesses) != self.total_coils:
            raise ValueError(
                f"Expected {self.total_coils} thickness values, got {len(current_thicknesses)}"
            )

        base_conditions = {
            'feed': feed_per_coil,
            'shc': shc,
            'cot': cot,
            'cop': cop,
            'cit': cit,
            'feed_ethane_pct': feed_ethane_pct,
            'feed_propane_pct': feed_propane_pct,
        }

        coil_results = []
        for coil_idx in range(self.total_coils):
            pass_num = coil_idx // self.coils_per_pass + 1
            coil_in_pass = coil_idx % self.coils_per_pass + 1

            result = self.forecaster.forecast(
                base_conditions,
                current_thickness=current_thicknesses[coil_idx],
                max_days=max_days
            )
            result['pass_number'] = pass_num
            result['coil_in_pass'] = coil_in_pass
            result['coil_index'] = coil_idx + 1
            result['feed_per_coil'] = round(feed_per_coil, 4)
            coil_results.append(result)

        # Furnace run length = min across coils (weakest coil limits the run)
        min_days = min(r['days_remaining'] for r in coil_results)
        limiting_coil = min(coil_results, key=lambda x: x['days_remaining'])

        return {
            'technology': self.technology,
            'total_coils': self.total_coils,
            'furnace_feed_total': furnace_feed_total,
            'feed_per_coil': round(feed_per_coil, 4),
            'furnace_runlength_days': min_days,
            'limiting_coil': limiting_coil['coil_index'],
            'limiting_reason': limiting_coil['end_reason'],
            'coil_forecasts': [
                {
                    'coil': r['coil_index'],
                    'pass': r['pass_number'],
                    'coil_in_pass': r['coil_in_pass'],
                    'days_remaining': r['days_remaining'],
                    'end_reason': r['end_reason'],
                    'initial_thickness': r['initial_thickness'],
                    'final_thickness': r['final_thickness'],
                    'final_tmt': r['final_tmt'],
                    'tmt_warning_day': r['tmt_warning_day']
                }
                for r in coil_results
            ]
        }


# =============================================================================
# SECTION 6: COUPLED FLEET ECONOMIC GAINS CALCULATOR
# =============================================================================

class EconomicGainsCalculator:
    """
    Calculates production gain, uptime gain, and profit gain potential
    using a COUPLED fleet strategy where:
      - High-rank furnaces are PUSHED (↑COT, ↓SHC → ↑yield, ↓run length)
      - Low-rank furnaces are PROTECTED (↓COT, ↑SHC → ↓yield, ↑run length)
      - Fleet gain = sum of individual gains (some positive, some negative)

    The key physics constraint: higher severity → higher yield BUT shorter run.
    The optimizer must show this trade-off honestly per furnace.

    Economic Assumptions (configurable):
        Ethylene price: $1,050/ton | Propylene: $900/ton | Fuel gas: $8.5/GJ
        Feed cost ethane: $350/ton | Feed cost propane: $320/ton
        Decoke cost: $150,000/event | Decoke downtime: 3 days
    """

    def __init__(self, ethylene_price=1050, propylene_price=900,
                 fuel_gas_cost=8.5, feed_cost_ethane=350, feed_cost_propane=320,
                 decoke_cost=150000, decoke_downtime_days=3):
        self.ethylene_price = ethylene_price
        self.propylene_price = propylene_price
        self.fuel_gas_cost = fuel_gas_cost
        self.feed_cost_ethane = feed_cost_ethane
        self.feed_cost_propane = feed_cost_propane
        self.decoke_cost = decoke_cost
        self.decoke_downtime_days = decoke_downtime_days

    def calc_furnace_economics(self, feed_rate, yield_pct, propylene_pct,
                               sec, run_days, feed_type='Ethane'):
        """Calculate annual economics for one furnace at given steady state."""
        feed_cost_per_ton = (self.feed_cost_ethane if feed_type == 'Ethane'
                             else self.feed_cost_propane)

        ethylene_rate = feed_rate * (yield_pct / 100.0)   # t/hr
        propylene_rate = feed_rate * (propylene_pct / 100.0)

        if run_days > 0:
            cycle_days = run_days + self.decoke_downtime_days
            cycles_per_year = 365.0 / cycle_days
            operating_days = cycles_per_year * run_days
            decokes_per_year = cycles_per_year
        else:
            operating_days = 0
            decokes_per_year = 0

        uptime_pct = (operating_days / 365.0) * 100.0
        operating_hours = operating_days * 24.0

        annual_ethylene = ethylene_rate * operating_hours
        annual_propylene = propylene_rate * operating_hours
        annual_feed = feed_rate * operating_hours

        revenue = (annual_ethylene * self.ethylene_price
                   + annual_propylene * self.propylene_price)
        cost_feed = annual_feed * feed_cost_per_ton
        cost_energy = annual_ethylene * sec * self.fuel_gas_cost
        cost_decoke = decokes_per_year * self.decoke_cost
        net_margin = revenue - cost_feed - cost_energy - cost_decoke

        return {
            'ethylene_tph': round(ethylene_rate, 3),
            'annual_ethylene_tons': round(annual_ethylene, 1),
            'annual_propylene_tons': round(annual_propylene, 1),
            'operating_days': round(operating_days, 1),
            'uptime_pct': round(uptime_pct, 2),
            'decokes_per_year': round(decokes_per_year, 2),
            'revenue_M': round(revenue / 1e6, 3),
            'feed_cost_M': round(cost_feed / 1e6, 3),
            'energy_cost_M': round(cost_energy / 1e6, 3),
            'decoke_cost_M': round(cost_decoke / 1e6, 3),
            'net_margin_M': round(net_margin / 1e6, 3),
            'run_days': run_days,
        }

    @staticmethod
    def multi_pass_yield(fresh_feed, yield_pct, conv_pct, n_passes=10):
        """
        Simulate multi-pass cracking with recycle loop.
        Per pass: feed → ethylene (yield%) + unconverted ethane (1-conv%)
        Unconverted ethane recycles back to furnace for next pass.
        Returns total ethylene produced after n_passes.
        """
        total_ethylene = 0
        remaining = fresh_feed
        for _ in range(n_passes):
            total_ethylene += remaining * (yield_pct / 100)
            converted = remaining * (conv_pct / 100)
            remaining = remaining - converted
            if remaining < 0.001:
                break
        return total_ethylene

    def compare(self, furnace_id, feed_type, feed_rate, baseline, optimized,
                strategy, cot_delta, shc_delta, use_multipass=False,
                base_conv=None, opt_conv=None):
        """Compare baseline vs optimized with strategy annotation.
        If use_multipass=True, uses multi-pass recycle loop model for ethylene calc."""
        base = self.calc_furnace_economics(
            feed_rate, baseline['yield_pct'], baseline['propylene_pct'],
            baseline['sec'], baseline['run_days'], feed_type)
        opt = self.calc_furnace_economics(
            feed_rate, optimized['yield_pct'], optimized['propylene_pct'],
            optimized['sec'], optimized['run_days'], feed_type)

        # Override ethylene with multi-pass model if requested
        if use_multipass and base_conv is not None and opt_conv is not None:
            base_eth_mp = self.multi_pass_yield(feed_rate, baseline['yield_pct'], base_conv)
            opt_eth_mp = self.multi_pass_yield(feed_rate, optimized['yield_pct'], opt_conv)
            # Scale to annual using operating hours from single-pass calc
            base_ophrs = base['operating_days'] * 24
            opt_ophrs = opt['operating_days'] * 24
            base['annual_ethylene_tons'] = round(base_eth_mp * base_ophrs, 1)
            opt['annual_ethylene_tons'] = round(opt_eth_mp * opt_ophrs, 1)
            # Recalculate margin with multi-pass ethylene
            base_rev = base['annual_ethylene_tons'] * self.ethylene_price + base['annual_propylene_tons'] * self.propylene_price
            base_fc = feed_rate * base_ophrs * (self.feed_cost_ethane if feed_type == 'Ethane' else self.feed_cost_propane)
            base_ec = base['annual_ethylene_tons'] * baseline['sec'] * self.fuel_gas_cost
            base_dc = base['decokes_per_year'] * self.decoke_cost
            base['net_margin_M'] = round((base_rev - base_fc - base_ec - base_dc) / 1e6, 3)

            opt_rev = opt['annual_ethylene_tons'] * self.ethylene_price + opt['annual_propylene_tons'] * self.propylene_price
            opt_fc = feed_rate * opt_ophrs * (self.feed_cost_ethane if feed_type == 'Ethane' else self.feed_cost_propane)
            opt_ec = opt['annual_ethylene_tons'] * optimized['sec'] * self.fuel_gas_cost
            opt_dc = opt['decokes_per_year'] * self.decoke_cost
            opt['net_margin_M'] = round((opt_rev - opt_fc - opt_ec - opt_dc) / 1e6, 3)

        prod_gain = opt['annual_ethylene_tons'] - base['annual_ethylene_tons']
        uptime_gain_pct = opt['uptime_pct'] - base['uptime_pct']
        uptime_gain_days = opt['operating_days'] - base['operating_days']
        profit_gain = opt['net_margin_M'] - base['net_margin_M']
        decoke_savings = ((base['decokes_per_year'] - opt['decokes_per_year'])
                          * self.decoke_cost / 1e6)

        return {
            'furnace': furnace_id,
            'feed_type': feed_type,
            'strategy': strategy,
            'cot_delta': cot_delta,
            'shc_delta': shc_delta,
            'baseline': base,
            'optimized': opt,
            'production_gain_tpy': round(prod_gain, 1),
            'production_gain_pct': round(
                prod_gain / max(base['annual_ethylene_tons'], 1) * 100, 2),
            'uptime_gain_pct': round(uptime_gain_pct, 2),
            'uptime_gain_days': round(uptime_gain_days, 1),
            'profit_gain_M': round(profit_gain, 3),
            'profit_gain_pct': round(
                profit_gain / max(abs(base['net_margin_M']), 0.001) * 100, 2),
            'decoke_savings_M': round(decoke_savings, 3),
        }


# =============================================================================
# SECTION 7: CONSTRAINT-DRIVEN FLEET OPTIMIZER WITH CROSS-FEED RECYCLE
# =============================================================================

class FleetOptimizer:
    """
    Constraint-driven optimizer with feed composition tracking.

    Key improvement: when recycle is routed to a furnace, the feed composition
    changes. Yield, conversion, coking rate, and other parameters all depend
    on feed composition. This class tracks composition through the recycle loop
    and adjusts predictions accordingly.

    Composition model:
    - Each furnace has current feed_ethane_pct and feed_propane_pct
    - Recycle streams have known purity (user input: ethane_recycle_purity,
      propane_recycle_purity)
    - When recycle is added, new composition = weighted average by mass flow
    - Sensitivities are interpolated between pure ethane and pure propane
      based on actual feed composition
    - If trained soft sensor models are provided, uses model.predict() for
      full composition-dependent prediction instead of linear sensitivities

    Cross-feed fractions (from cracked gas composition):
        Ethane furnace unreacted: 95% ethane, 3% propane, 2% other
        Propane furnace unreacted: 15% ethane, 78% propane, 7% other
    """

    # Base sensitivities for pure feeds (per °C COT increase)
    SENS_PURE = {
        'Ethane':  {'yld_cot': 0.218, 'prop_cot': -0.017, 'conv_cot': 0.480,
                    'tmt_cot': 1.66, 'run_cot': -3.0, 'run_shc': 10.0,
                    'coking_cot': 1.05},
        'Propane': {'yld_cot': 0.218, 'prop_cot': -0.136, 'conv_cot': 0.405,
                    'tmt_cot': 1.54, 'run_cot': -2.5, 'run_shc': 7.5,
                    'coking_cot': 0.45},
        'Technip': {'yld_cot': 0.200, 'prop_cot': -0.015, 'conv_cot': 0.450,
                    'tmt_cot': 1.70, 'run_cot': -4.5, 'run_shc': 12.0,
                    'coking_cot': 0.80},
    }

    # Composition sensitivity: how yield/conv change per 1% change in ethane fraction
    # Derived from comparing simulation data at different compositions
    SENS_COMPOSITION = {
        'yld_per_ethane_pct':  +0.22,    # %yield per %ethane (higher ethane → higher yield)
        'prop_per_ethane_pct': -0.16,    # %propylene per %ethane (higher ethane → less propylene)
        'conv_per_ethane_pct': -0.05,    # %conv per %ethane (ethane slightly harder to crack)
        'coking_per_ethane_pct': +0.08,  # coking rate per %ethane (ethane cokes slightly more)
        'sec_per_ethane_pct': -0.015,    # SEC per %ethane (ethane slightly lower SEC)
    }

    CROSS_FEED = {
        'Ethane':  {'ethane_frac': 0.95, 'propane_frac': 0.03},
        'Propane': {'ethane_frac': 0.15, 'propane_frac': 0.78},
    }

    LIMITS = {
        'feed_valve': 85, 'tmt_alarm': 1075, 'tmt_warn': 1060,
        'c2_splitter_max': 90, 'cgc_max': 0.45,
    }

    def __init__(self, econ=None, soft_sensor_models=None,
                 ethane_feed_purity=92.0, propane_feed_purity=85.0):
        """
        Constraint-driven fleet optimizer with feed composition awareness.

        Args:
            econ: EconomicGainsCalculator instance
            soft_sensor_models: dict of {model_key: FurnaceSoftSensorModels} or None
                Keys: 'lummus_ethane', 'lummus_propane', 'technip_ethane', 'technip_propane'
                If provided, uses GBR model.predict() with actual feed composition
                for yield, conversion, coking rate, propylene, TMT etc.
            ethane_feed_purity: % ethane in mixed feed going to ethane furnaces
                (fresh ethane + recycle ethane already mixed in plant piping)
                Example: 92% means 92% ethane + 8% propane entering the furnace
            propane_feed_purity: % propane in mixed feed going to propane furnaces
                (fresh propane + recycle propane already mixed)
                Example: 85% means 85% propane + 15% ethane entering the furnace

        These purities are what the plant manager reads from the analyzer
        at the furnace inlet — the actual composition after all mixing.
        """
        self.econ = econ or EconomicGainsCalculator()
        self.models = soft_sensor_models
        self.ethane_feed_purity = ethane_feed_purity      # % ethane in ethane furnace feed
        self.propane_feed_purity = propane_feed_purity    # % propane in propane furnace feed

    def get_sens(self, furnace, feed_ethane_pct=None):
        """
        Get sensitivities adjusted for actual feed composition.
        Uses ethane_feed_purity for ethane furnaces, propane_feed_purity for propane.
        """
        if furnace.get('tech') == 'Technip':
            return self.SENS_PURE['Technip']

        # Use user-input purity based on furnace feed type
        if feed_ethane_pct is not None:
            eth_pct = feed_ethane_pct
        elif furnace['feed'] == 'Ethane':
            eth_pct = self.ethane_feed_purity  # user input: actual ethane furnace feed purity
        else:
            eth_pct = 100.0 - self.propane_feed_purity  # user input: convert propane purity to ethane%

        # Interpolation weight: 0 = pure propane, 1 = pure ethane
        w = eth_pct / 100.0
        se = self.SENS_PURE['Ethane']
        sp = self.SENS_PURE['Propane']

        return {
            'yld_cot':  round(w * se['yld_cot']  + (1-w) * sp['yld_cot'], 4),
            'prop_cot': round(w * se['prop_cot'] + (1-w) * sp['prop_cot'], 4),
            'conv_cot': round(w * se['conv_cot'] + (1-w) * sp['conv_cot'], 4),
            'tmt_cot':  round(w * se['tmt_cot']  + (1-w) * sp['tmt_cot'], 3),
            'run_cot':  round(w * se['run_cot']  + (1-w) * sp['run_cot'], 2),
            'run_shc':  round(w * se['run_shc']  + (1-w) * sp['run_shc'], 2),
            'coking_cot': round(w * se['coking_cot'] + (1-w) * sp['coking_cot'], 3),
        }

    def get_cross(self, furnace):
        return self.CROSS_FEED.get(furnace['feed'], self.CROSS_FEED['Ethane'])

    def get_feed_composition(self, furnace):
        """
        Get actual feed composition for a furnace based on user-input purity.
        Returns (ethane_pct, propane_pct).
        """
        if furnace['feed'] == 'Ethane' or furnace.get('tech') == 'Technip':
            return self.ethane_feed_purity, 100.0 - self.ethane_feed_purity
        else:
            return 100.0 - self.propane_feed_purity, self.propane_feed_purity

    def predict_with_model(self, furnace, opt_feed, opt_cot, opt_shc, opt_thickness):
        """
        Use trained soft sensor model with actual feed composition from user input.
        The ethane_feed_purity / propane_feed_purity represent the real analyzer
        reading at furnace inlet (fresh + recycle already mixed).

        Returns: dict with yield_c2h4, propylene, conversion, coking_rate, tmt, etc.
                 or None if models not available.
        """
        if self.models is None:
            return None

        tech = furnace.get('tech', 'Lummus')
        feed = furnace.get('feed', 'Ethane')
        model_key = f"{'technip' if tech=='Technip' else 'lummus'}_{feed.lower()}"

        model = self.models.get(model_key)
        if model is None:
            return None

        # Get actual feed composition from user input
        eth_pct, prop_pct = self.get_feed_composition(furnace)

        # Number of coils for feed-per-coil calculation
        if tech == 'Technip':
            n_coils = 6  # 6 passes × 1 coil
        else:
            n_coils = 8  # 4 passes × 2 coils

        X_input = {
            'feed': opt_feed / n_coils,
            'shc': opt_shc,
            'cot': opt_cot,
            'cop': furnace.get('cop', 1.1),
            'cit': furnace.get('cit', 650),
            'feed_ethane_pct': eth_pct,
            'feed_propane_pct': prop_pct,
            'thickness': opt_thickness,
        }

        try:
            preds = model.predict(X_input)
            return preds
        except Exception:
            return None

    def composition_adjusted_yield(self, base_yield, base_eth_pct, new_eth_pct, dc, sens):
        """
        Adjust yield for both COT change AND composition change.
        yield_new = base + dc * sens['yld_cot'] + Δeth% * SENS_COMPOSITION['yld_per_ethane_pct']
        """
        comp_delta = (new_eth_pct - base_eth_pct) * self.SENS_COMPOSITION['yld_per_ethane_pct'] / 100.0
        cot_delta = dc * sens['yld_cot']
        return base_yield + cot_delta + comp_delta

    def composition_adjusted_propylene(self, base_prop, base_eth_pct, new_eth_pct, dc, sens):
        comp_delta = (new_eth_pct - base_eth_pct) * self.SENS_COMPOSITION['prop_per_ethane_pct'] / 100.0
        cot_delta = dc * sens['prop_cot']
        return base_prop + cot_delta + comp_delta

    def composition_adjusted_conv(self, base_conv, base_eth_pct, new_eth_pct, dc, sens):
        comp_delta = (new_eth_pct - base_eth_pct) * self.SENS_COMPOSITION['conv_per_ethane_pct'] / 100.0
        cot_delta = dc * sens['conv_cot']
        return base_conv + cot_delta + comp_delta

    def composition_adjusted_sec(self, base_sec, base_eth_pct, new_eth_pct, dc, ds):
        comp_delta = (new_eth_pct - base_eth_pct) * self.SENS_COMPOSITION['sec_per_ethane_pct'] / 100.0
        return base_sec + dc * 0.02 - ds * 5 + comp_delta

    def run_scenario(self, fleet, dc_protect, delta_fresh=None, c2_current=82.0):
        """
        Run one optimization scenario with full composition tracking.
        """
        delta_fresh = delta_fresh or {'Ethane': 0, 'Propane': 0}
        ds_map = {fid: 0.02 if fleet[fid].get('runDays', 999) < 40 else 0.01
                  for fid in dc_protect}

        protected_ids = set(dc_protect.keys())
        healthy_eth = sorted(
            [fid for fid, f in fleet.items()
             if f['feed'] != 'Propane' and fid not in protected_ids
             and f.get('status', 'online') == 'online'],
            key=lambda fid: -self._marginal_profit(fleet[fid]))
        healthy_prop = sorted(
            [fid for fid, f in fleet.items()
             if f['feed'] == 'Propane' and fid not in protected_ids
             and f.get('status', 'online') == 'online'],
            key=lambda fid: -self._marginal_profit(fleet[fid]))

        # Initialize actions — composition comes from user input, not tracked per-furnace
        acts = {}
        for fid, f in fleet.items():
            if f.get('status', 'online') != 'online':
                continue
            eth_pct, prop_pct = self.get_feed_composition(f)
            acts[fid] = {
                'dc': dc_protect.get(fid, 0),
                'ds': ds_map.get(fid, 0.0),
                'dFeed': 0.0,
                'optFeed': f['fr'],
                'feed_eth_pct': eth_pct,   # from user input (analyzer reading)
                'feed_prop_pct': prop_pct,
            }

        # Phase 1: Distribute fresh feed (composition = same as current for fresh)
        for ft_key, receivers in [('Ethane', healthy_eth), ('Propane', healthy_prop)]:
            remaining = delta_fresh.get(ft_key, 0)
            for fid in receivers:
                if remaining <= 0.01:
                    break
                f = fleet[fid]
                feed_hr = self.LIMITS['feed_valve'] - f.get('fgv', 70)
                max_extra = f['fr'] * feed_hr / 100
                give = min(remaining, max_extra)
                acts[fid]['dFeed'] = round(give, 3)
                acts[fid]['optFeed'] = round(f['fr'] + give, 3)
                # Fresh feed same purity as current — no composition change
                remaining -= give

        # Phase 2: Recycle from protection (with cross-feed)
        total_eth_rec = 0
        total_prop_rec = 0
        for fid in protected_ids:
            f = fleet[fid]
            s = self.get_sens(f)  # uses user-input purity
            cx = self.get_cross(f)
            dc = acts[fid]['dc']
            delta_conv = dc * s['conv_cot']
            extra_unr = f['fr'] * (-delta_conv) / 100
            total_eth_rec += extra_unr * cx['ethane_frac']
            total_prop_rec += extra_unr * cx['propane_frac']

        # Route recycle to healthy furnaces (composition already set by user input)
        def route_recycle(amount, receivers, fleet, acts):
            remaining = amount
            for fid in receivers:
                if remaining <= 0.05:
                    break
                f = fleet[fid]
                cur_feed = acts[fid]['optFeed']
                cur_valve = cur_feed / f['fr'] * f.get('fgv', 70) if f['fr'] > 0 else 100
                room = max(0, (self.LIMITS['feed_valve'] - cur_valve) / 100 * cur_feed)
                give = min(remaining, room)
                if give > 0.01:
                    acts[fid]['dFeed'] = round(acts[fid]['dFeed'] + give, 3)
                    acts[fid]['optFeed'] = round(f['fr'] + acts[fid]['dFeed'], 3)
                    remaining -= give
            return remaining

        route_recycle(total_eth_rec, healthy_eth, fleet, acts)
        route_recycle(total_prop_rec, healthy_prop, fleet, acts)

        # Phase 3: Secondary recycle → ↑COT to absorb
        for fid in healthy_eth + healthy_prop:
            if acts[fid]['dFeed'] <= 0.01:
                continue
            f = fleet[fid]
            s = self.get_sens(f)  # uses user-input purity
            cx = self.get_cross(f)
            sec_unr = acts[fid]['dFeed'] * (100 - f['conv']) / 100
            total_sec = sec_unr * (cx['ethane_frac'] + cx['propane_frac'])
            if total_sec > 0.01:
                dc_needed = total_sec * 100 / (acts[fid]['optFeed'] * s['conv_cot'])
                dc_up = round(max(0, dc_needed + 0.2))
                tmt_new = f.get('tmtMax', 1040) + dc_up * s['tmt_cot']
                if tmt_new > self.LIMITS['tmt_alarm']:
                    dc_up = max(0, int((self.LIMITS['tmt_alarm'] - f.get('tmtMax', 1040)) / s['tmt_cot']))
                acts[fid]['dc'] = dc_up

        # Phase 4: Economics — use user-input feed purity for predictions
        totals = {'ethGain': 0, 'propGain': 0, 'profitGain': 0, 'uptimeGain': 0}
        furnace_results = {}
        # [patched v2]

        for fid, a in acts.items():
            f = fleet[fid]
            eth_pct = a['feed_eth_pct']  # from user input

            # Try soft sensor model first (uses actual feed composition)
            model_pred = self.predict_with_model(
                f, a['optFeed'], f['cot'] + a['dc'], f['shc'] + a['ds'],
                f.get('thickness', 3.0))

            if model_pred and 'yield_c2h4' in model_pred:
                # Model prediction includes composition effects
                oY = model_pred['yield_c2h4']
                oP = model_pred.get('propylene', f.get('prop_yld', 0))
                # Also predict baseline at current conditions for delta calc
                base_pred = self.predict_with_model(
                    f, f['fr'], f['cot'], f['shc'], f.get('thickness', 3.0))
                if base_pred and 'yield_c2h4' in base_pred:
                    base_yield = base_pred['yield_c2h4']
                    base_prop = base_pred.get('propylene', f.get('prop_yld', 0))
                else:
                    base_yield = f['yield']
                    base_prop = f.get('prop_yld', 0)
            else:
                # Fallback: composition-adjusted sensitivities
                s = self.get_sens(f)  # uses user-input purity via interpolation
                base_eth = f.get('feed_ethane_pct', 97.0 if f['feed'] == 'Ethane' else 8.0)
                # Both baseline and optimized use same composition adjustment
                # so composition delta cancels out — only COT/SHC deltas produce gains
                base_yield = self.composition_adjusted_yield(f['yield'], base_eth, eth_pct, 0, s)
                base_prop = self.composition_adjusted_propylene(f.get('prop_yld', 0), base_eth, eth_pct, 0, s)
                oY = self.composition_adjusted_yield(f['yield'], base_eth, eth_pct, a['dc'], s)
                oP = self.composition_adjusted_propylene(f.get('prop_yld', 0), base_eth, eth_pct, a['dc'], s)

            base_eth = f.get('feed_ethane_pct', 97.0 if f['feed'] == 'Ethane' else 8.0)
            base_sec = self.composition_adjusted_sec(f.get('sec', 14), base_eth, eth_pct, 0, 0)
            oSec = self.composition_adjusted_sec(f.get('sec', 14), base_eth, eth_pct, a['dc'], a['ds'])
            s = self.get_sens(f)
            oR = max(30, round(f.get('runTotal', 120) + a['dc'] * s['run_cot']
                               + (a['ds'] * 100) * s['run_shc']))

            base = self.econ.calc_furnace_economics(
                f['fr'], base_yield, base_prop, base_sec,
                f.get('runTotal', 120), f['feed'])
            opt = self.econ.calc_furnace_economics(
                a['optFeed'], oY, oP, oSec, oR, f['feed'])

            dE = round(opt['annual_ethylene_tons'] - base['annual_ethylene_tons'])
            dP = round(opt['annual_propylene_tons'] - base['annual_propylene_tons'])
            dProf = round(opt['net_margin_M'] - base['net_margin_M'], 3)
            dUp = round(opt['operating_days'] - base['operating_days'], 1)
            dRun = oR - f.get('runTotal', 120)

            furnace_results[fid] = {
                'dc': a['dc'], 'ds': a['ds'], 'dFeed': round(a['dFeed'], 2),
                'optFeed': round(a['optFeed'], 2), 'ethGain': dE, 'propGain': dP,
                'profitGain': dProf, 'uptimeGain': dUp, 'runDelta': dRun,
                'feed_eth_pct': round(eth_pct, 1),
                'feed_prop_pct': round(a['feed_prop_pct'], 1),
            }
            totals['ethGain'] += dE
            totals['propGain'] += dP
            totals['profitGain'] += dProf
            totals['uptimeGain'] += dUp

        totals['profitGain'] = round(totals['profitGain'], 3)
        totals['uptimeGain'] = round(totals['uptimeGain'], 1)

        # Phase 5: Energy costs — CGC + C2 splitter
        # CGC: extra cracked gas from extra feed → more VHP steam
        # C2 splitter: extra ethane recycle → more condenser duty → more refrigeration
        cgc_spec_steam = 0.1279   # t/hr VHP per t/hr cracked gas (from plant data)
        vhp_cost = 25             # $/ton VHP steam
        c2s_vhp_per_eth = 0.203   # t/hr VHP per t/hr extra ethane to C2 splitter

        total_extra_cg = 0
        total_eth_to_c2s = 0
        for fid, a in acts.items():
            if a['dFeed'] <= 0.01:
                continue
            f = fleet[fid]
            gas_exp = 2.0 if f['feed'] == 'Propane' else 1.6
            shc_val = f.get('shc', 0.33)
            total_extra_cg += a['dFeed'] * (gas_exp + shc_val)
            # Ethane recycle going to C2 splitter (from conversion drop on protected)
            if f['feed'] != 'Propane' and f.get('tech') != 'Technip':
                total_eth_to_c2s += a['dFeed']

        # Add ethane from cross-feed (propane furnace protection generates ethane)
        for fid in dc_protect:
            f = fleet[fid]
            if f['feed'] == 'Propane':
                s = self.get_sens(f)
                dc = acts[fid]['dc']
                unr = f['fr'] * (-dc * s['conv_cot']) / 100
                total_eth_to_c2s += unr * self.CROSS_FEED['Propane']['ethane_frac']

        cgc_vhp_delta = total_extra_cg * cgc_spec_steam
        c2s_vhp_delta = total_eth_to_c2s * c2s_vhp_per_eth
        total_energy_vhp = cgc_vhp_delta + c2s_vhp_delta
        energy_cost_annual = round(total_energy_vhp * vhp_cost * 8400 / 1e6, 3)

        totals['cgc_vhp_delta_tph'] = round(cgc_vhp_delta, 3)
        totals['c2s_vhp_delta_tph'] = round(c2s_vhp_delta, 3)
        totals['energy_cost_M'] = energy_cost_annual
        totals['netProfit'] = round(totals['profitGain'] - energy_cost_annual, 3)

        return {'furnaces': furnace_results, 'totals': totals}

    def optimize(self, fleet, delta_fresh=None, c2_current=82.0,
                 max_dc=5.0, step=0.5):
        """
        Iterate COT reductions on all protected furnaces to find max profit.
        """
        protected = {fid: f for fid, f in fleet.items()
                     if f.get('status', 'online') == 'online'
                     and (f.get('runDays', 999) < 60 or f.get('tmtMax', 1000) > self.LIMITS['tmt_warn'])}

        if not protected:
            return self.run_scenario(fleet, {}, delta_fresh, c2_current)

        prot_ids = list(protected.keys())
        steps = [round(-i * step, 1) for i in range(1, int(max_dc / step) + 1)]

        best = None
        best_profit = -1e9

        if len(prot_ids) == 1:
            for dc1 in steps:
                result = self.run_scenario(fleet, {prot_ids[0]: dc1}, delta_fresh, c2_current)
                if result['totals']['profitGain'] > best_profit:
                    best_profit = result['totals']['profitGain']
                    best = result
        elif len(prot_ids) == 2:
            for dc1 in steps:
                for dc2 in steps:
                    dc_map = {prot_ids[0]: dc1, prot_ids[1]: dc2}
                    result = self.run_scenario(fleet, dc_map, delta_fresh, c2_current)
                    if result['totals']['profitGain'] > best_profit:
                        best_profit = result['totals']['profitGain']
                        best = result
        else:
            dc_map = {fid: -1.0 for fid in prot_ids}
            for fid in prot_ids:
                best_dc = -1.0
                for dc in steps:
                    dc_map[fid] = dc
                    result = self.run_scenario(fleet, dc_map, delta_fresh, c2_current)
                    if result['totals']['profitGain'] > best_profit:
                        best_profit = result['totals']['profitGain']
                        best_dc = dc
                        best = result
                dc_map[fid] = best_dc

        return best

    def _marginal_profit(self, f):
        """Marginal profit per ton of extra feed at current yield."""
        if f['feed'] == 'Propane':
            return (f['yield'] / 100 * 1050 + f.get('prop_yld', 16) / 100 * 900
                    - 320 - f['yield'] / 100 * f.get('sec', 15) * 8.5)
        return (f['yield'] / 100 * 1050 - 350
                - f['yield'] / 100 * f.get('sec', 14) * 8.5)


# =============================================================================
# SECTION 8: MAIN EXECUTION — BUILD MODELS, FORECAST, REPORT ACCURACY
# =============================================================================

def main():
    print("=" * 70)
    print("  ETHYLENE FURNACE RUNLENGTH FORECASTING ENGINE")
    print("  Soft Sensor Model Training + Runlength Prediction")
    print(f"  Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # --- File paths ---
    file_paths = [
        '/mnt/user-data/uploads/lummus_ethane_consolidated.xlsx',
        '/mnt/user-data/uploads/lummus_propane_consolidated.xlsx',
        '/mnt/user-data/uploads/technip_ethane_consolidated.xlsx',
        '/mnt/user-data/uploads/technip_propane_consolidated.xlsx',
    ]

    # --- Load data ---
    print("\n[1] LOADING DATA...")
    datasets = load_all_datasets(file_paths)

    # --- Build soft sensor models for each dataset ---
    print("\n[2] TRAINING SOFT SENSOR MODELS (Gradient Boosting Regressor)...")
    model_sets = {}
    for key, df in datasets.items():
        ms = FurnaceSoftSensorModels(name=key, n_estimators=200, max_depth=5, learning_rate=0.1)
        ms.build(df)
        model_sets[key] = ms

    # --- Compile accuracy report ---
    print("\n\n" + "=" * 70)
    print("  [3] CONSOLIDATED MODEL ACCURACY REPORT")
    print("=" * 70)
    all_metrics = pd.concat([ms.get_accuracy_summary() for ms in model_sets.values()], ignore_index=True)
    print(all_metrics.to_string(index=False))

    # Summary statistics
    print(f"\n  Overall Average R² (Test):  {all_metrics['R2_Test'].mean():.5f}")
    print(f"  Overall Average MAPE (%):  {all_metrics['MAPE_%'].mean():.3f}")
    print(f"  Total Models Trained:      {len(all_metrics)}")
    print(f"  Models with R² > 0.99:     {(all_metrics['R2_Test'] > 0.99).sum()}")
    print(f"  Models with R² > 0.95:     {(all_metrics['R2_Test'] > 0.95).sum()}")

    # =========================================================================
    # [4] SAMPLE RUNLENGTH FORECAST — LUMMUS ETHANE FURNACE (AF-01)
    # =========================================================================
    print("\n\n" + "=" * 70)
    print("  [4] SAMPLE FORECAST: LUMMUS ETHANE FURNACE (AF-01)")
    print("      Configuration: 4 passes × 2 coils = 8 coils")
    print("=" * 70)

    lummus_ethane_forecaster = FurnaceRunlengthForecaster(
        technology='Lummus',
        model_set=model_sets['lummus_ethane'],
        num_passes=4,
        coils_per_pass=2
    )

    # Sample input: furnace mid-run with non-uniform coking across coils
    sample_thicknesses_lummus = [3.2, 3.5, 2.8, 4.1, 3.0, 3.8, 2.5, 4.5]  # mm per coil

    result_lummus = lummus_ethane_forecaster.forecast_furnace(
        furnace_feed_total=54.0,    # t/hr total (6.75 per coil × 8)
        shc=0.33,
        cot=835,
        cop=1.1,
        cit=650,
        feed_ethane_pct=97.09,
        feed_propane_pct=1.43,
        current_thicknesses=sample_thicknesses_lummus,
        max_days=300
    )

    print(f"\n  Furnace Feed Total:    {result_lummus['furnace_feed_total']} t/hr")
    print(f"  Feed per Coil:         {result_lummus['feed_per_coil']} t/hr")
    print(f"  Operating: COT=835°C, SHC=0.33, COP=1.1 bar, CIT=650°C")
    print(f"  Feed Composition:      97.09% Ethane, 1.43% Propane")
    print(f"\n  {'Coil':<6} {'Pass':<6} {'Coil#':<7} {'Days':<8} {'Init.Thk':<10} {'Final.Thk':<11} {'Final TMT':<11} {'TMT Warn':<10} {'End Reason'}")
    print(f"  {'-'*90}")
    for c in result_lummus['coil_forecasts']:
        warn = c['tmt_warning_day'] if c['tmt_warning_day'] else '-'
        print(f"  {c['coil']:<6} {c['pass']:<6} {c['coil_in_pass']:<7} {c['days_remaining']:<8} "
              f"{c['initial_thickness']:<10.2f} {c['final_thickness']:<11.4f} "
              f"{c['final_tmt']:<11.1f} {str(warn):<10} {c['end_reason'][:50]}")

    print(f"\n  >>> FURNACE RUNLENGTH FORECAST: {result_lummus['furnace_runlength_days']} DAYS")
    print(f"  >>> Limiting Coil: #{result_lummus['limiting_coil']}")
    print(f"  >>> Reason: {result_lummus['limiting_reason']}")

    # =========================================================================
    # [5] SAMPLE FORECAST — TECHNIP ETHANE FURNACE (AF-08)
    # =========================================================================
    print("\n\n" + "=" * 70)
    print("  [5] SAMPLE FORECAST: TECHNIP ETHANE FURNACE (AF-08)")
    print("      Configuration: 6 passes × 1 coil = 6 coils")
    print("=" * 70)

    technip_ethane_forecaster = FurnaceRunlengthForecaster(
        technology='Technip',
        model_set=model_sets['technip_ethane'],
        num_passes=6,
        coils_per_pass=1
    )

    sample_thicknesses_technip = [5.0, 6.2, 4.8, 7.0, 5.5, 6.8]  # mm per coil

    result_technip = technip_ethane_forecaster.forecast_furnace(
        furnace_feed_total=30.0,    # t/hr total (5.0 per coil × 6)
        shc=0.32,
        cot=830,
        cop=1.15,
        cit=670,
        feed_ethane_pct=98.57,
        feed_propane_pct=1.43,
        current_thicknesses=sample_thicknesses_technip,
        max_days=300
    )

    print(f"\n  Furnace Feed Total:    {result_technip['furnace_feed_total']} t/hr")
    print(f"  Feed per Coil:         {result_technip['feed_per_coil']} t/hr")
    print(f"  Operating: COT=830°C, SHC=0.32, COP=1.15 bar, CIT=670°C")
    print(f"  Feed Composition:      98.57% Ethane, 1.43% Propane")
    print(f"\n  {'Coil':<6} {'Pass':<6} {'Days':<8} {'Init.Thk':<10} {'Final.Thk':<11} {'Final TMT':<11} {'TMT Warn':<10} {'End Reason'}")
    print(f"  {'-'*80}")
    for c in result_technip['coil_forecasts']:
        warn = c['tmt_warning_day'] if c['tmt_warning_day'] else '-'
        print(f"  {c['coil']:<6} {c['pass']:<6} {c['days_remaining']:<8} "
              f"{c['initial_thickness']:<10.2f} {c['final_thickness']:<11.4f} "
              f"{c['final_tmt']:<11.1f} {str(warn):<10} {c['end_reason'][:50]}")

    print(f"\n  >>> FURNACE RUNLENGTH FORECAST: {result_technip['furnace_runlength_days']} DAYS")
    print(f"  >>> Limiting Coil: #{result_technip['limiting_coil']}")
    print(f"  >>> Reason: {result_technip['limiting_reason']}")

    # =========================================================================
    # [6] SAMPLE FORECAST — LUMMUS PROPANE FURNACE
    # =========================================================================
    print("\n\n" + "=" * 70)
    print("  [6] SAMPLE FORECAST: LUMMUS PROPANE FURNACE (AF-03)")
    print("      Configuration: 4 passes × 2 coils = 8 coils")
    print("=" * 70)

    lummus_propane_forecaster = FurnaceRunlengthForecaster(
        technology='Lummus',
        model_set=model_sets['lummus_propane'],
        num_passes=4,
        coils_per_pass=2
    )

    sample_thicknesses_lp = [1.5, 2.0, 1.8, 2.5, 1.2, 2.8, 1.0, 3.0]

    result_lp = lummus_propane_forecaster.forecast_furnace(
        furnace_feed_total=76.0,    # t/hr total (9.5 per coil × 8)
        shc=0.35,
        cot=830,
        cop=1.1,
        cit=620,
        feed_ethane_pct=7.83,
        feed_propane_pct=84.36,
        current_thicknesses=sample_thicknesses_lp,
        max_days=300
    )

    print(f"\n  Furnace Feed Total:    {result_lp['furnace_feed_total']} t/hr")
    print(f"  Feed per Coil:         {result_lp['feed_per_coil']} t/hr")
    print(f"  Operating: COT=830°C, SHC=0.35, COP=1.1 bar, CIT=620°C")
    print(f"\n  {'Coil':<6} {'Pass':<6} {'Days':<8} {'Init.Thk':<10} {'Final.Thk':<11} {'Final TMT':<11} {'End Reason'}")
    print(f"  {'-'*70}")
    for c in result_lp['coil_forecasts']:
        print(f"  {c['coil']:<6} {c['pass']:<6} {c['days_remaining']:<8} "
              f"{c['initial_thickness']:<10.2f} {c['final_thickness']:<11.4f} "
              f"{c['final_tmt']:<11.1f} {c['end_reason'][:45]}")

    print(f"\n  >>> FURNACE RUNLENGTH FORECAST: {result_lp['furnace_runlength_days']} DAYS")
    print(f"  >>> Limiting Coil: #{result_lp['limiting_coil']}")

    # =========================================================================
    # [7] PRINT COIL-LEVEL TRAJECTORY SAMPLE (first 10 days, limiting coil)
    # =========================================================================
    print("\n\n" + "=" * 70)
    print("  [7] SAMPLE TRAJECTORY — AF-01 Limiting Coil Day-by-Day (first 20 days)")
    print("=" * 70)

    # Get full trajectory of the limiting coil from Lummus ethane
    limiting_idx = result_lummus['limiting_coil'] - 1
    full_result = lummus_ethane_forecaster.forecaster.forecast(
        operating_conditions={
            'feed': 6.75, 'shc': 0.33, 'cot': 835, 'cop': 1.1, 'cit': 650,
            'feed_ethane_pct': 97.09, 'feed_propane_pct': 1.43
        },
        current_thickness=sample_thicknesses_lummus[limiting_idx],
        max_days=300
    )

    traj = full_result['trajectory']
    print(f"\n  {'Day':<6} {'Thickness(mm)':<15} {'Coking Rate':<13} {'TMT(°C)':<10} {'Yield(%)':<10} {'Conv(%)':<10}")
    print(f"  {'-'*65}")
    for t in traj[:20]:
        print(f"  {t['day']:<6} {t['thickness_mm']:<15.4f} {t['coking_rate']:<13.4f} "
              f"{t['tmt_predicted']:<10.1f} {t['yield_c2h4']:<10.3f} {t['conversion']:<10.3f}")
    if len(traj) > 20:
        print(f"  ... ({len(traj) - 20} more days)")
        t = traj[-1]
        print(f"  {t['day']:<6} {t['thickness_mm']:<15.4f} {t['coking_rate']:<13.4f} "
              f"{t['tmt_predicted']:<10.1f} {t['yield_c2h4']:<10.3f} {t['conversion']:<10.3f}")

    # =========================================================================
    # [8] SAVE ACCURACY REPORT
    # =========================================================================
    print("\n\n" + "=" * 70)
    print("  [8] SAVING ACCURACY REPORT")
    print("=" * 70)
    all_metrics.to_csv('/mnt/user-data/outputs/soft_sensor_model_accuracy.csv', index=False)
    print("  Saved: soft_sensor_model_accuracy.csv")

    # =========================================================================
    # [9] THREE-STRATEGY FLEET ECONOMIC ANALYSIS (MULTI-PASS RECYCLE MODEL)
    # =========================================================================
    print("\n\n" + "=" * 70)
    print("  [9] THREE-STRATEGY FLEET ECONOMIC ANALYSIS")
    print("      Multi-pass recycle loop model for ethylene production")
    print("=" * 70)

    econ = EconomicGainsCalculator()

    # Conversion sensitivities
    conv_per_cot = {
        'Lummus_Ethane': 0.480, 'Lummus_Propane': 0.405, 'Technip_Ethane': 0.450
    }
    run_per_cot = {
        'Lummus_Ethane': -3.0, 'Lummus_Propane': -2.5, 'Technip_Ethane': -4.5
    }
    run_per_shc_001 = {
        'Lummus_Ethane': 10.0, 'Lummus_Propane': 7.5, 'Technip_Ethane': 12.0
    }
    yld_per_cot = {
        'Lummus_Ethane': 0.218, 'Lummus_Propane': 0.218, 'Technip_Ethane': 0.200
    }
    prop_per_cot = {
        'Lummus_Ethane': -0.017, 'Lummus_Propane': -0.136, 'Technip_Ethane': -0.015
    }

    base_furnaces = [
        {'id': 'AF-02', 'tech': 'Lummus_Ethane', 'ft': 'Ethane', 'fr': 56,
         'by': 48.8, 'bp': 1.11, 'bs': 13.8, 'br': 120, 'bc': 63.5, 'rank': 1},
        {'id': 'AF-06', 'tech': 'Lummus_Ethane', 'ft': 'Ethane', 'fr': 55,
         'by': 48.5, 'bp': 1.10, 'bs': 13.6, 'br': 140, 'bc': 63.0, 'rank': 2},
        {'id': 'AF-08', 'tech': 'Technip_Ethane', 'ft': 'Ethane', 'fr': 30,
         'by': 34.2, 'bp': 0.56, 'bs': 12.9, 'br': 280, 'bc': 64.0, 'rank': 3},
        {'id': 'AF-03', 'tech': 'Lummus_Propane', 'ft': 'Propane', 'fr': 76,
         'by': 29.1, 'bp': 16.88, 'bs': 15.1, 'br': 180, 'bc': 77.4, 'rank': 4},
        {'id': 'AF-01', 'tech': 'Lummus_Ethane', 'ft': 'Ethane', 'fr': 54,
         'by': 49.2, 'bp': 1.13, 'bs': 14.2, 'br': 120, 'bc': 64.8, 'rank': 5},
        {'id': 'AF-04', 'tech': 'Lummus_Ethane', 'ft': 'Ethane', 'fr': 52,
         'by': 50.1, 'bp': 1.15, 'bs': 14.8, 'br': 100, 'bc': 66.2, 'rank': 6},
    ]

    strategies = {
        'A': {
            'name': 'FEED LIMITED (multi-pass recycle)',
            'desc': 'Fresh feed at 85%. Lower COT → recycle loop recovers ethylene over multiple passes.',
            'feed_ratio': 0.85, 'use_multipass': True,
            'actions': {
                'AF-02': {'dc': -2, 'ds': +0.01, 'strat': 'RECYCLE GEN'},
                'AF-06': {'dc': -3, 'ds': +0.01, 'strat': 'RECYCLE GEN'},
                'AF-08': {'dc': -2, 'ds': +0.01, 'strat': 'RECYCLE GEN'},
                'AF-03': {'dc': -2, 'ds': +0.01, 'strat': 'RECYCLE GEN'},
                'AF-01': {'dc': -5, 'ds': +0.02, 'strat': 'MAX RECYCLE'},
                'AF-04': {'dc': -8, 'ds': +0.02, 'strat': 'MAX RECYCLE'},
            }
        },
        'B': {
            'name': 'FEED AVAILABLE (push/protect)',
            'desc': 'Fresh feed at 100%. Push high-rank, protect low-rank.',
            'feed_ratio': 1.0, 'use_multipass': False,
            'actions': {
                'AF-02': {'dc': +9, 'ds': -0.01, 'strat': 'MAX YIELD'},
                'AF-06': {'dc': +7, 'ds': -0.01, 'strat': 'MAX YIELD'},
                'AF-08': {'dc': +5, 'ds': 0.00, 'strat': 'BALANCED'},
                'AF-03': {'dc': +3, 'ds': 0.00, 'strat': 'BALANCED'},
                'AF-01': {'dc': -3, 'ds': +0.02, 'strat': 'PROTECT'},
                'AF-04': {'dc': -10, 'ds': +0.02, 'strat': 'PROTECT'},
            }
        },
        'C': {
            'name': 'C2 SPLITTER LIMITED (hold recycle)',
            'desc': 'Splitter at 90%. Net zero recycle change. Tight optimization.',
            'feed_ratio': 1.0, 'use_multipass': False,
            'actions': {
                'AF-02': {'dc': +3, 'ds': 0.00, 'strat': 'MILD PUSH'},
                'AF-06': {'dc': +2, 'ds': 0.00, 'strat': 'MILD PUSH'},
                'AF-08': {'dc': +1, 'ds': 0.00, 'strat': 'HOLD'},
                'AF-03': {'dc': +0, 'ds': 0.00, 'strat': 'HOLD'},
                'AF-01': {'dc': -2, 'ds': +0.01, 'strat': 'MILD PROTECT'},
                'AF-04': {'dc': -5, 'ds': +0.01, 'strat': 'MILD PROTECT'},
            }
        },
    }

    all_strategy_results = {}

    for skey, strat in strategies.items():
        print(f"\n  ┌{'─'*68}┐")
        print(f"  │  STRATEGY {skey}: {strat['name']:<57}│")
        print(f"  │  {strat['desc']:<67}│")
        print(f"  └{'─'*68}┘")

        fr_ratio = strat['feed_ratio']
        use_mp = strat['use_multipass']

        print(f"\n  {'ID':<7} {'Strat':<14} {'ΔCOT':>5} {'Feed':>6} {'ΔYld':>6} {'ΔRun':>5} "
              f"{'EthΔ t/yr':>11} {'PropΔ t/yr':>11} {'Profit $M':>10} {'RecycleΔ':>9}")
        print(f"  {'-'*90}")

        tot = {'eth': 0, 'prop': 0, 'profit': 0, 'recycle': 0, 'uptime': 0}
        strat_results = []

        for f in base_furnaces:
            a = strat['actions'][f['id']]
            tech = f['tech']
            feed = f['fr'] * fr_ratio

            # Optimized yields
            oy = f['by'] + a['dc'] * yld_per_cot[tech]
            op = f['bp'] + a['dc'] * prop_per_cot[tech]
            orun = max(30, round(f['br'] + a['dc'] * run_per_cot[tech]
                                 + (a['ds'] * 100) * run_per_shc_001[tech]))
            osec = f['bs'] + a['dc'] * 0.02 - a['ds'] * 5
            oconv = f['bc'] + a['dc'] * conv_per_cot[tech]

            baseline_d = {'yield_pct': f['by'], 'propylene_pct': f['bp'],
                          'sec': f['bs'], 'run_days': f['br']}
            optimized_d = {'yield_pct': oy, 'propylene_pct': op,
                           'sec': osec, 'run_days': orun}

            r = econ.compare(
                f['id'], f['ft'], feed, baseline_d, optimized_d,
                a['strat'], a['dc'], a['ds'],
                use_multipass=use_mp,
                base_conv=f['bc'], opt_conv=oconv
            )

            # Recycle change
            base_rec = feed * (100 - f['bc']) / 100
            opt_rec = feed * (100 - oconv) / 100
            d_rec = opt_rec - base_rec

            tot['eth'] += r['production_gain_tpy']
            tot['prop'] += (r['optimized']['annual_propylene_tons'] - r['baseline']['annual_propylene_tons'])
            tot['profit'] += r['profit_gain_M']
            tot['recycle'] += d_rec
            tot['uptime'] += r['uptime_gain_days']

            prop_gain = r['optimized']['annual_propylene_tons'] - r['baseline']['annual_propylene_tons']
            strat_results.append({**r, 'recycle_delta': round(d_rec, 2), 'prop_gain_tpy': round(prop_gain)})

            print(f"  {f['id']:<7} {a['strat']:<14} {a['dc']:>+5}°C {feed:>6.1f} "
                  f"{oy - f['by']:>+6.2f} {orun - f['br']:>+4}d "
                  f"{r['production_gain_tpy']:>+11,.0f} {prop_gain:>+11,.0f} "
                  f"{r['profit_gain_M']:>+10.3f} {d_rec:>+9.2f}")

        print(f"  {'-'*90}")
        print(f"  {'FLEET':<7} {'TOTAL':<14} {'':>5} {'':>6} {'':>6} {'':>5} "
              f"{tot['eth']:>+11,.0f} {tot['prop']:>+11,.0f} "
              f"{tot['profit']:>+10.3f} {tot['recycle']:>+9.2f}")

        all_strategy_results[skey] = {'results': strat_results, 'totals': tot}

    # Summary comparison
    print(f"\n\n  {'═'*70}")
    print(f"  THREE-STRATEGY COMPARISON SUMMARY")
    print(f"  {'═'*70}")
    print(f"\n  {'Strategy':<25} {'C2H4 Δ':>12} {'C3H6 Δ':>12} {'Recycle':>10} {'Uptime':>10} {'Profit':>12}")
    print(f"  {'':>25} {'(t/yr)':>12} {'(t/yr)':>12} {'(t/hr)':>10} {'(d/yr)':>10} {'($M/yr)':>12}")
    print(f"  {'-'*83}")
    for skey in ['A', 'B', 'C']:
        t = all_strategy_results[skey]['totals']
        name = strategies[skey]['name'][:24]
        print(f"  {name:<25} {t['eth']:>+12,.0f} {t['prop']:>+12,.0f} "
              f"{t['recycle']:>+10.2f} {t['uptime']:>+10.1f} {t['profit']:>+12.3f}")

    # Save CSV
    rows = []
    for skey in ['A', 'B', 'C']:
        for r in all_strategy_results[skey]['results']:
            rows.append({
                'Strategy': skey,
                'Strategy_Name': strategies[skey]['name'],
                'Furnace': r['furnace'],
                'Sub_Strategy': r['strategy'],
                'COT_Delta': r['cot_delta'],
                'SHC_Delta': r['shc_delta'],
                'Ethylene_Gain_tpy': r['production_gain_tpy'],
                'Propylene_Gain_tpy': r.get('prop_gain_tpy', 0),
                'Profit_Gain_M': r['profit_gain_M'],
                'Recycle_Delta_tph': r.get('recycle_delta', 0),
                'Uptime_Gain_days': r['uptime_gain_days'],
                'Run_Delta_days': r.get('optimized', {}).get('run_days', 0) - r.get('baseline', {}).get('run_days', 0),
            })
    econ_df = pd.DataFrame(rows)
    econ_df.to_csv('/mnt/user-data/outputs/economic_gains_report.csv', index=False)
    print("\n  Saved: economic_gains_report.csv")

    print("\n" + "=" * 70)
    print("  EXECUTION COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
