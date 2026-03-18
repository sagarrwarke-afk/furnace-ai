"""
Multi-algorithm ML benchmark engine for furnace soft-sensor models.

Trains and compares Ridge, RF, GBR, XGBoost, LightGBM on simulation data.
Handles per-coil prediction: simulation data is per-coil, so furnace-level
predictions divide feed by num_coils, predict per-coil, then aggregate
(TMT=MAX, yield=MEAN, coking=MAX).
"""

from __future__ import annotations

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from typing import Any

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_percentage_error

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_FEATURES = [
    "feed", "shc", "cot", "cop", "cit",
    "thickness", "feed_ethane_pct", "feed_propane_pct",
]

ENGINEERED_FEATURE_NAMES = [
    "cot_x_shc", "cot_x_feed", "shc_x_feed",
    "cot_sq", "shc_sq", "thickness_sq",
    "log_cot", "log_feed", "log_thickness",
    "cot_cit_delta", "ethane_x_cot", "propane_x_cot",
    "feed_purity_ratio",
]

ALL_FEATURES = BASE_FEATURES + ENGINEERED_FEATURE_NAMES

TARGETS = ["yield_c2h4", "coking_rate", "tmt", "conversion", "propylene"]


def _make_algorithm(name: str):
    """Factory: return a fresh (unfitted) sklearn estimator by name."""
    if name == "Ridge":
        return Ridge(alpha=1.0)
    if name == "RandomForest":
        return RandomForestRegressor(
            n_estimators=200, max_depth=10, n_jobs=-1, random_state=42,
        )
    if name == "GradientBoosting":
        return GradientBoostingRegressor(
            n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42,
        )
    if name == "XGBoost":
        if not HAS_XGB:
            raise ImportError("xgboost is not installed")
        return xgb.XGBRegressor(
            n_estimators=300, max_depth=6, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=0,
        )
    if name == "LightGBM":
        if not HAS_LGB:
            raise ImportError("lightgbm is not installed")
        return lgb.LGBMRegressor(
            n_estimators=300, max_depth=6, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8, random_state=42, verbose=-1,
        )
    raise ValueError(f"Unknown algorithm: {name}")


AVAILABLE_ALGORITHMS = ["Ridge", "RandomForest", "GradientBoosting"]
if HAS_XGB:
    AVAILABLE_ALGORITHMS.append("XGBoost")
if HAS_LGB:
    AVAILABLE_ALGORITHMS.append("LightGBM")


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add domain-specific interaction and polynomial features."""
    d = df.copy()
    d["cot_x_shc"]        = d["cot"] * d["shc"]
    d["cot_x_feed"]       = d["cot"] * d["feed"]
    d["shc_x_feed"]       = d["shc"] * d["feed"]
    d["cot_sq"]           = d["cot"] ** 2
    d["shc_sq"]           = d["shc"] ** 2
    d["thickness_sq"]     = d["thickness"] ** 2
    d["log_cot"]          = np.log(d["cot"].clip(lower=1))
    d["log_feed"]         = np.log(d["feed"].clip(lower=0.01))
    d["log_thickness"]    = np.log(d["thickness"].clip(lower=0.001) + 1)
    d["cot_cit_delta"]    = d["cot"] - d["cit"]
    d["ethane_x_cot"]     = d["feed_ethane_pct"] * d["cot"]
    d["propane_x_cot"]    = d["feed_propane_pct"] * d["cot"]
    d["feed_purity_ratio"] = d["feed_ethane_pct"] / (d["feed_propane_pct"] + 1)
    return d


def _engineer_single(raw: dict) -> dict:
    """Apply feature engineering to a single raw data point (dict)."""
    d = dict(raw)
    d["cot_x_shc"]        = d["cot"] * d["shc"]
    d["cot_x_feed"]       = d["cot"] * d["feed"]
    d["shc_x_feed"]       = d["shc"] * d["feed"]
    d["cot_sq"]           = d["cot"] ** 2
    d["shc_sq"]           = d["shc"] ** 2
    d["thickness_sq"]     = d["thickness"] ** 2
    d["log_cot"]          = np.log(max(d["cot"], 1))
    d["log_feed"]         = np.log(max(d["feed"], 0.01))
    d["log_thickness"]    = np.log(max(d["thickness"], 0.001) + 1)
    d["cot_cit_delta"]    = d["cot"] - d["cit"]
    d["ethane_x_cot"]     = d["feed_ethane_pct"] * d["cot"]
    d["propane_x_cot"]    = d["feed_propane_pct"] * d["cot"]
    d["feed_purity_ratio"] = d["feed_ethane_pct"] / (d["feed_propane_pct"] + 1)
    return d


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def _evaluate(y_true, y_pred):
    r2   = r2_score(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mape = float(mean_absolute_percentage_error(y_true, y_pred) * 100)
    return {"r2": round(r2, 6), "rmse": round(rmse, 4), "mape_pct": round(mape, 4)}


# ---------------------------------------------------------------------------
# ModelBenchmark class
# ---------------------------------------------------------------------------

class ModelBenchmark:
    """
    Trains multiple ML algorithms on furnace simulation data,
    benchmarks accuracy + interpolation, recommends best model.
    """

    # ---- public API -------------------------------------------------------

    @staticmethod
    def analyze_grid(df: pd.DataFrame) -> dict[str, int]:
        """Return {feature: n_unique_values} to show data sparsity."""
        result = {}
        for col in BASE_FEATURES:
            if col in df.columns:
                result[col] = int(df[col].nunique())
        return result

    @staticmethod
    def run_benchmark(
        df: pd.DataFrame,
        selected_algorithms: list[str],
    ) -> dict[str, dict[str, dict]]:
        """
        Train selected algorithms on 80/20 split.

        Returns:
            {algorithm: {target: {r2, rmse, mape_pct, r2_train, n_train, n_test}}}
        """
        # Ensure required columns
        for col in BASE_FEATURES:
            if col not in df.columns:
                df[col] = 0.0

        avail_targets = [t for t in TARGETS if t in df.columns]
        df_eng = engineer_features(df[BASE_FEATURES + avail_targets].dropna())

        X = df_eng[ALL_FEATURES].values
        scaler = StandardScaler()

        results: dict[str, dict] = {}

        for algo_name in selected_algorithms:
            results[algo_name] = {}
            for target in avail_targets:
                y = df_eng[target].values
                X_tr, X_te, y_tr, y_te = train_test_split(
                    X, y, test_size=0.2, random_state=42,
                )
                X_tr_s = scaler.fit_transform(X_tr)
                X_te_s = scaler.transform(X_te)

                model = _make_algorithm(algo_name)
                model.fit(X_tr_s, y_tr)

                pred_te = model.predict(X_te_s)
                pred_tr = model.predict(X_tr_s)

                metrics = _evaluate(y_te, pred_te)
                metrics["r2_train"] = round(r2_score(y_tr, pred_tr), 6)
                metrics["n_train"] = len(y_tr)
                metrics["n_test"] = len(y_te)
                results[algo_name][target] = metrics

        return results

    @staticmethod
    def run_interpolation_test(
        df: pd.DataFrame,
        selected_algorithms: list[str],
    ) -> dict[str, dict]:
        """
        Hold-out one grid level per variable, measure interpolation accuracy.

        Returns:
            {algorithm: {mean_r2, mean_mape, worst_r2, detail: [...]}}
        """
        for col in BASE_FEATURES:
            if col not in df.columns:
                df[col] = 0.0

        avail_targets = [t for t in TARGETS if t in df.columns]
        df_clean = df[BASE_FEATURES + avail_targets].dropna()

        # Find variables with 4+ unique values
        testable = []
        for col in BASE_FEATURES:
            uvals = sorted(df_clean[col].unique())
            if len(uvals) >= 4:
                holdout_val = uvals[len(uvals) // 2]
                testable.append((col, holdout_val))

        if not testable:
            # Not enough grid variation for interpolation test
            return {a: {"mean_r2": None, "mean_mape": None, "worst_r2": None} for a in selected_algorithms}

        interp_results: dict[str, list] = {a: [] for a in selected_algorithms}

        for var_name, holdout_val in testable[:4]:  # limit to 4 variables for speed
            train_mask = df_clean[var_name] != holdout_val
            test_mask = df_clean[var_name] == holdout_val
            if test_mask.sum() < 10:
                continue

            df_tr = engineer_features(df_clean[train_mask])
            df_te = engineer_features(df_clean[test_mask])

            X_tr = df_tr[ALL_FEATURES].values
            X_te = df_te[ALL_FEATURES].values

            scaler = StandardScaler()
            X_tr_s = scaler.fit_transform(X_tr)
            X_te_s = scaler.transform(X_te)

            for algo_name in selected_algorithms:
                for target in avail_targets:
                    y_tr = df_tr[target].values
                    y_te = df_te[target].values

                    model = _make_algorithm(algo_name)
                    model.fit(X_tr_s, y_tr)
                    pred = model.predict(X_te_s)

                    r2 = r2_score(y_te, pred)
                    mape = mean_absolute_percentage_error(y_te, pred) * 100
                    interp_results[algo_name].append({
                        "var": var_name, "target": target,
                        "r2": r2, "mape": mape,
                    })

        # Aggregate per algorithm
        summary = {}
        for algo_name in selected_algorithms:
            entries = interp_results[algo_name]
            if not entries:
                summary[algo_name] = {"mean_r2": None, "mean_mape": None, "worst_r2": None}
            else:
                r2s = [e["r2"] for e in entries]
                mapes = [e["mape"] for e in entries]
                summary[algo_name] = {
                    "mean_r2": round(float(np.mean(r2s)), 4),
                    "mean_mape": round(float(np.mean(mapes)), 2),
                    "worst_r2": round(float(np.min(r2s)), 4),
                }
        return summary

    @staticmethod
    def recommend(
        benchmark: dict[str, dict[str, dict]],
        interpolation: dict[str, dict],
    ) -> tuple[str, str]:
        """
        Score algorithms and recommend the best.

        Score = 0.4 * mean_test_R2 + 0.4 * mean_interpolation_R2 + 0.2 * smoothness_bonus
        Linear models get a smoothness bonus of 0.05.

        Returns (recommended_algorithm, reason_string)
        """
        LINEAR_MODELS = {"Ridge"}
        scores = {}

        for algo_name, target_metrics in benchmark.items():
            # Mean test R2 across all targets
            r2_values = [m["r2"] for m in target_metrics.values()]
            mean_test_r2 = np.mean(r2_values) if r2_values else 0

            # Interpolation R2
            interp = interpolation.get(algo_name, {})
            interp_r2 = interp.get("mean_r2")
            if interp_r2 is None:
                interp_r2 = mean_test_r2  # fallback if no interpolation test

            # Smoothness bonus
            smoothness = 0.05 if algo_name in LINEAR_MODELS else 0.0

            score = 0.4 * mean_test_r2 + 0.4 * interp_r2 + 0.2 * (1.0 + smoothness)
            scores[algo_name] = round(score, 4)

        best = max(scores, key=scores.get)

        # Build reason
        interp_data = interpolation.get(best, {})
        interp_r2 = interp_data.get("mean_r2", "N/A")

        if best in LINEAR_MODELS:
            reason = (
                f"{best} recommended: smooth interpolation (no staircase artifacts) "
                f"on sparse grid data. Interpolation R2={interp_r2}. "
                f"Tree models scored lower on held-out grid levels."
            )
        else:
            reason = (
                f"{best} recommended: highest combined accuracy and interpolation score. "
                f"Interpolation R2={interp_r2}."
            )

        return best, reason, scores

    @staticmethod
    def train_production_model(
        df: pd.DataFrame,
        algorithm_name: str,
    ) -> dict[str, Any]:
        """
        Train the selected algorithm on the FULL dataset with engineered features.

        Returns picklable dict:
        {
            "models": {target: fitted_model},
            "scaler": StandardScaler (fitted),
            "feature_names": list[str],   # ALL_FEATURES
            "base_features": list[str],   # BASE_FEATURES
            "algorithm": str,
            "metrics": {target: {r2_train, r2_test, mae, mape_pct, n_train, n_test}},
        }
        """
        for col in BASE_FEATURES:
            if col not in df.columns:
                df[col] = 0.0

        avail_targets = [t for t in TARGETS if t in df.columns]
        df_eng = engineer_features(df[BASE_FEATURES + avail_targets].dropna())

        X = df_eng[ALL_FEATURES].values
        scaler = StandardScaler()
        scaler.fit(X)

        models = {}
        metrics = {}

        for target in avail_targets:
            y = df_eng[target].values
            X_tr, X_te, y_tr, y_te = train_test_split(
                X, y, test_size=0.2, random_state=42,
            )
            X_tr_s = scaler.transform(X_tr)
            X_te_s = scaler.transform(X_te)

            model = _make_algorithm(algorithm_name)
            model.fit(X_tr_s, y_tr)

            pred_te = model.predict(X_te_s)
            pred_tr = model.predict(X_tr_s)

            r2_test = r2_score(y_te, pred_te)
            r2_train = r2_score(y_tr, pred_tr)
            mae = float(np.mean(np.abs(y_te - pred_te)))
            mape = float(mean_absolute_percentage_error(y_te, pred_te) * 100)

            # Now re-train on FULL dataset for production
            X_full_s = scaler.transform(X)
            model_prod = _make_algorithm(algorithm_name)
            model_prod.fit(X_full_s, y)

            models[target] = model_prod
            metrics[target] = {
                "r2_train": round(r2_train, 6),
                "r2_test": round(r2_test, 6),
                "mae": round(mae, 4),
                "mape_pct": round(mape, 2),
                "n_train": len(y_tr),
                "n_test": len(y_te),
            }

        return {
            "models": models,
            "scaler": scaler,
            "feature_names": ALL_FEATURES,
            "base_features": BASE_FEATURES,
            "algorithm": algorithm_name,
            "metrics": metrics,
        }

    # ---- prediction (static, works on pickled model_dict) -----------------

    @staticmethod
    def predict(model_dict: dict, X_raw: dict) -> dict[str, float]:
        """
        Predict all targets from raw feature values (8 base features).
        Applies feature engineering + scaling internally.

        Args:
            model_dict: unpickled production model dict
            X_raw: dict with keys from BASE_FEATURES, e.g. {"feed": 6.75, "cot": 838, ...}

        Returns:
            {target: predicted_value} e.g. {"yield_c2h4": 49.2, "tmt": 1058, ...}
        """
        # Ensure all base features present
        for f in BASE_FEATURES:
            if f not in X_raw:
                X_raw[f] = 0.0

        # Engineer features
        eng = _engineer_single(X_raw)

        # Build feature array in correct order
        feature_names = model_dict.get("feature_names", ALL_FEATURES)
        X_arr = np.array([[eng.get(f, 0.0) for f in feature_names]])

        # Scale
        scaler = model_dict["scaler"]
        X_scaled = scaler.transform(X_arr)

        # Predict each target
        result = {}
        for target, model in model_dict["models"].items():
            pred = float(model.predict(X_scaled)[0])
            result[target] = round(pred, 4)

        return result

    @staticmethod
    def predict_furnace(
        model_dict: dict,
        furnace_feed_rate: float,
        cot: float,
        shc: float,
        cop: float,
        cit: float,
        feed_ethane_pct: float,
        feed_propane_pct: float,
        coil_thicknesses: list[float],
        num_coils: int,
    ) -> dict[str, Any]:
        """
        Per-coil furnace prediction.

        Simulation data is per-coil, so:
        1. feed_per_coil = furnace_feed_rate / num_coils
        2. For each coil: predict with that coil's thickness
        3. Aggregate: tmt=MAX, yield=MEAN, conversion=MEAN,
                      propylene=MEAN, coking_rate=MAX

        Returns:
            {
                "yield_c2h4": float,   # furnace average
                "tmt": float,          # furnace MAX
                "coking_rate": float,  # furnace MAX
                "conversion": float,   # furnace average
                "propylene": float,    # furnace average
                "per_coil": [          # per-coil detail
                    {"coil": 1, "thickness": 0.67, "tmt": 1055, ...},
                    ...
                ]
            }
        """
        if num_coils < 1:
            num_coils = 1

        feed_per_coil = furnace_feed_rate / num_coils

        # Pad or truncate thicknesses to match num_coils
        thicknesses = list(coil_thicknesses)
        while len(thicknesses) < num_coils:
            thicknesses.append(thicknesses[-1] if thicknesses else 0.5)
        thicknesses = thicknesses[:num_coils]

        coil_preds = []
        for i, thick in enumerate(thicknesses):
            # Skip coils with zero thickness (use a small default)
            effective_thick = thick if thick > 0.001 else 0.5

            raw = {
                "feed": feed_per_coil,
                "cot": cot,
                "shc": shc,
                "cop": cop,
                "cit": cit,
                "thickness": effective_thick,
                "feed_ethane_pct": feed_ethane_pct,
                "feed_propane_pct": feed_propane_pct,
            }
            pred = ModelBenchmark.predict(model_dict, raw)
            pred["coil"] = i + 1
            pred["thickness"] = effective_thick
            coil_preds.append(pred)

        # Aggregate across coils
        result = {"per_coil": coil_preds}

        if not coil_preds:
            return result

        for target in TARGETS:
            vals = [cp.get(target) for cp in coil_preds if cp.get(target) is not None]
            if not vals:
                continue
            if target in ("tmt", "coking_rate"):
                result[target] = round(max(vals), 4)
            else:
                result[target] = round(float(np.mean(vals)), 4)

        return result
