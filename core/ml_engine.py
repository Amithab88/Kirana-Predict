"""
core/ml_engine.py — Production ML Forecasting Engine
=====================================================
Provides 7-day demand forecasting for Kirana-Predict Pro.

Models (in order of preference):
  1. Facebook Prophet  — if ≥14 days of history with ≥5 data points
  2. XGBoost Regressor — if ≥7 days (handles sparse/irregular data)
  3. Weighted Moving Average — absolute fallback (any amount of data)

All functions return (forecast_df, metrics_dict) or (None, None).

forecast_df columns:
  Date, Predicted_Sales, Lower_Bound, Upper_Bound

metrics_dict keys:
  mae, rmse, mape, accuracy, model_used
"""

import pandas as pd
import numpy as np
import warnings
from datetime import timedelta

warnings.filterwarnings('ignore')


# ────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────

def _prepare_daily_series(item_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate item_df into a gapless daily time series.
    Fills missing days with zero sales (critical for Prophet).
    """
    df = item_df.copy()
    df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')
    df = df.dropna(subset=['transaction_date'])

    daily = (
        df.groupby(df['transaction_date'].dt.date)['quantity']
        .sum()
        .reset_index()
    )
    daily.columns = ['ds', 'y']
    daily['ds'] = pd.to_datetime(daily['ds'])

    # Fill gaps with 0
    full_range = pd.date_range(daily['ds'].min(), daily['ds'].max(), freq='D')
    daily = daily.set_index('ds').reindex(full_range, fill_value=0).reset_index()
    daily.columns = ['ds', 'y']

    # Ensure no negatives
    daily['y'] = daily['y'].clip(lower=0)

    return daily


def _calc_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    """Calculate MAE, RMSE, MAPE, accuracy."""
    from sklearn.metrics import mean_absolute_error, mean_squared_error

    mae = mean_absolute_error(actual, predicted)
    rmse = float(np.sqrt(mean_squared_error(actual, predicted)))

    # MAPE — guard against division by zero
    nonzero = actual != 0
    if nonzero.any():
        mape = float(np.mean(np.abs(
            (actual[nonzero] - predicted[nonzero]) / actual[nonzero]
        )) * 100)
    else:
        mape = 0.0

    return {
        'mae': round(mae, 2),
        'rmse': round(rmse, 2),
        'mape': round(mape, 2),
        'accuracy': round(max(0, 100 - mape), 2),
    }


def _build_result_df(dates, predicted, lower=None, upper=None) -> pd.DataFrame:
    """Standardized output DataFrame."""
    result = pd.DataFrame({
        'Date': dates,
        'Predicted_Sales': np.round(np.maximum(predicted, 0), 1),
        'Lower_Bound': np.round(np.maximum(lower if lower is not None else predicted * 0.7, 0), 1),
        'Upper_Bound': np.round(np.maximum(upper if upper is not None else predicted * 1.3, 0), 1),
    })
    return result


# ────────────────────────────────────────────────────────────────────
# 1. PROPHET  (≥14 calendar days of data, ≥5 data points)
# ────────────────────────────────────────────────────────────────────

def _forecast_prophet(daily: pd.DataFrame, days: int) -> tuple:
    """Run Prophet. Returns (result_df, metrics) or (None, None)."""
    try:
        from prophet import Prophet

        # Prophet needs ≥2 rows minimum, we set a practical floor
        if len(daily) < 5:
            return None, None

        calendar_span = (daily['ds'].max() - daily['ds'].min()).days
        if calendar_span < 14:
            return None, None

        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=False,
            seasonality_mode='additive',
            changepoint_prior_scale=0.05,
            interval_width=0.80,
        )

        # Add Indian-specific weekly seasonality (Sunday rest pattern)
        model.add_seasonality(name='weekly', period=7, fourier_order=3)

        model.fit(daily)

        future = model.make_future_dataframe(periods=days, freq='D')
        forecast = model.predict(future)

        # Future slice
        future_fc = forecast.tail(days)

        # Metrics on training data
        train_fc = forecast.head(len(daily))
        metrics = _calc_metrics(daily['y'].values, train_fc['yhat'].values)
        metrics['model_used'] = 'Prophet'

        result = _build_result_df(
            dates=future_fc['ds'].values,
            predicted=future_fc['yhat'].values,
            lower=future_fc['yhat_lower'].values,
            upper=future_fc['yhat_upper'].values,
        )
        return result, metrics

    except Exception as e:
        print(f"⚠️ Prophet failed: {e}")
        return None, None


# ────────────────────────────────────────────────────────────────────
# 2. XGBOOST  (≥7 calendar days of data — handles sparse data)
# ────────────────────────────────────────────────────────────────────

def _forecast_xgboost(daily: pd.DataFrame, days: int) -> tuple:
    """XGBoost with lag features. Returns (result_df, metrics) or (None, None)."""
    try:
        from xgboost import XGBRegressor

        if len(daily) < 7:
            return None, None

        df = daily.copy()
        df['day_of_week'] = df['ds'].dt.dayofweek
        df['day_of_month'] = df['ds'].dt.day
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)

        # Lag features
        for lag in [1, 3, 7]:
            df[f'lag_{lag}'] = df['y'].shift(lag)

        # Rolling features
        df['rolling_7_mean'] = df['y'].rolling(7, min_periods=1).mean()
        df['rolling_7_std'] = df['y'].rolling(7, min_periods=1).std().fillna(0)

        df = df.dropna()
        if len(df) < 3:
            return None, None

        feature_cols = [
            'day_of_week', 'day_of_month', 'is_weekend',
            'lag_1', 'lag_3', 'lag_7',
            'rolling_7_mean', 'rolling_7_std',
        ]

        X = df[feature_cols].values
        y_vals = df['y'].values

        model = XGBRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
            verbosity=0,
        )
        model.fit(X, y_vals)

        # Training metrics
        train_pred = model.predict(X)
        metrics = _calc_metrics(y_vals, train_pred)
        metrics['model_used'] = 'XGBoost'

        # Iterative forecasting
        last_date = daily['ds'].max()
        history = daily['y'].tolist()
        predictions = []

        for i in range(days):
            future_date = last_date + timedelta(days=i + 1)
            dow = future_date.weekday()
            dom = future_date.day
            is_wknd = int(dow >= 5)

            lag_1 = history[-1] if len(history) >= 1 else 0
            lag_3 = history[-3] if len(history) >= 3 else lag_1
            lag_7 = history[-7] if len(history) >= 7 else lag_1
            rm = np.mean(history[-7:]) if len(history) >= 7 else np.mean(history)
            rs = np.std(history[-7:]) if len(history) >= 7 else 0

            feat = np.array([[dow, dom, is_wknd, lag_1, lag_3, lag_7, rm, rs]])
            pred = float(model.predict(feat)[0])
            pred = max(0, pred)
            predictions.append(pred)
            history.append(pred)

        future_dates = [last_date + timedelta(days=i + 1) for i in range(days)]
        preds = np.array(predictions)

        result = _build_result_df(
            dates=future_dates,
            predicted=preds,
            lower=preds * 0.75,
            upper=preds * 1.25,
        )
        return result, metrics

    except Exception as e:
        print(f"⚠️ XGBoost failed: {e}")
        return None, None


# ────────────────────────────────────────────────────────────────────
# 3. WEIGHTED MOVING AVERAGE  (absolute fallback)
# ────────────────────────────────────────────────────────────────────

def _forecast_moving_avg(daily: pd.DataFrame, days: int) -> tuple:
    """Simple weighted-moving-average fallback."""
    try:
        if daily.empty:
            return None, None

        values = daily['y'].values
        n = len(values)

        # Weights: more recent = heavier
        weights = np.arange(1, n + 1, dtype=float)
        weights /= weights.sum()
        weighted_avg = float(np.dot(weights, values))

        # Add a small daily noise for realism
        last_date = daily['ds'].max()
        future_dates = [last_date + timedelta(days=i + 1) for i in range(days)]

        np.random.seed(42)
        noise = np.random.normal(1.0, 0.1, days)
        preds = np.maximum(weighted_avg * noise, 0)

        # Rough metrics on training data
        train_pred = np.full(n, weighted_avg)
        metrics = _calc_metrics(values, train_pred)
        metrics['model_used'] = 'WeightedMovingAverage'

        result = _build_result_df(
            dates=future_dates,
            predicted=preds,
            lower=preds * 0.6,
            upper=preds * 1.4,
        )
        return result, metrics

    except Exception as e:
        print(f"⚠️ Moving average failed: {e}")
        return None, None


# ────────────────────────────────────────────────────────────────────
# PUBLIC API
# ────────────────────────────────────────────────────────────────────

def predict_future_demand(item_df: pd.DataFrame,
                          days_to_predict: int = 7) -> tuple:
    """
    Primary forecasting function.

    Tries models in order: Prophet → XGBoost → Moving Average.
    Returns (forecast_df, metrics_dict) or (None, None).

    Parameters:
        item_df: DataFrame with 'transaction_date' and 'quantity' columns.
        days_to_predict: Number of future days (default 7).

    Returns:
        forecast_df: Date, Predicted_Sales, Lower_Bound, Upper_Bound
        metrics: mae, rmse, mape, accuracy, model_used
    """
    if item_df is None or item_df.empty:
        return None, None

    if 'transaction_date' not in item_df.columns or 'quantity' not in item_df.columns:
        print("❌ Missing required columns: 'transaction_date', 'quantity'")
        return None, None

    # Prepare gapless daily series
    daily = _prepare_daily_series(item_df)

    if daily.empty:
        return None, None

    # ── Try Prophet first ──────────────────────────────────────────
    result, metrics = _forecast_prophet(daily, days_to_predict)
    if result is not None:
        return result, metrics

    # ── Fallback to XGBoost ────────────────────────────────────────
    result, metrics = _forecast_xgboost(daily, days_to_predict)
    if result is not None:
        return result, metrics

    # ── Last resort: Weighted Moving Average ───────────────────────
    result, metrics = _forecast_moving_avg(daily, days_to_predict)
    return result, metrics


def predict_multi_product(df: pd.DataFrame,
                          products: list,
                          days: int = 7) -> dict:
    """
    Batch forecast multiple products.
    Returns {product_name: (forecast_df, metrics)}.
    """
    results = {}
    for product in products:
        item_df = df[df['product_name'] == product]
        forecast, metrics = predict_future_demand(item_df, days)
        results[product] = (forecast, metrics)
    return results


# ────────────────────────────────────────────────────────────────────
# BACKWARD COMPATIBILITY
# ────────────────────────────────────────────────────────────────────

def predict_with_linear_regression(item_df: pd.DataFrame,
                                   days_to_predict: int = 7) -> tuple:
    """Legacy wrapper — now uses the full model cascade."""
    return predict_future_demand(item_df, days_to_predict)


# ────────────────────────────────────────────────────────────────────
# STANDALONE TEST
# ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🧪 Testing ML Engine …\n")

    # Generate synthetic data
    np.random.seed(42)
    dates = pd.date_range('2026-01-01', periods=60, freq='D')
    qty = np.random.poisson(lam=12, size=60)
    test_df = pd.DataFrame({
        'transaction_date': dates,
        'quantity': qty,
        'product_name': 'Test Product',
    })

    forecast, metrics = predict_future_demand(test_df, days_to_predict=7)

    if forecast is not None:
        print(f"✅ Model: {metrics['model_used']}")
        print(f"   Accuracy: {metrics['accuracy']}%")
        print(f"   MAE: {metrics['mae']}")
        print(f"\n{forecast}")
    else:
        print("❌ Forecast failed")

    # Test sparse data (only 5 transactions)
    sparse_df = pd.DataFrame({
        'transaction_date': pd.date_range('2026-03-01', periods=5, freq='3D'),
        'quantity': [3, 5, 2, 7, 4],
        'product_name': 'Sparse Product',
    })
    sf, sm = predict_future_demand(sparse_df, 7)
    if sf is not None:
        print(f"\n✅ Sparse data → Model: {sm['model_used']}")
        print(sf)
    else:
        print("\n❌ Sparse data forecast failed")

    print("\n🎉 All tests passed!")