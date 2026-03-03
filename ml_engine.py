# ml_engine.py - Enhanced with Facebook Prophet

import pandas as pd
import numpy as np
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings('ignore')

def predict_future_demand(item_df, days_to_predict=7):
    """
    Facebook Prophet - Production-grade forecasting
    
    Features:
    - Automatic seasonality detection
    - Trend analysis
    - Confidence intervals
    - Handles missing data
    
    Returns: (forecast_df, metrics_dict) or (None, None)
    """
    
    # Data validation
    if len(item_df) < 7:
        return None, None
    
    # Prepare data
    daily_sales = item_df.groupby('transaction_date')['quantity'].sum().reset_index()
    
    if len(daily_sales) < 2:
        return None, None
    
    # Prophet requires specific column names
    prophet_data = daily_sales.rename(columns={
        'transaction_date': 'ds',
        'quantity': 'y'
    })
    
    try:
        # Initialize Prophet model
        model = Prophet(
            daily_seasonality=True,      # Detect daily patterns
            weekly_seasonality=True,     # Weekday vs weekend
            yearly_seasonality=False,    # Need 2+ years of data
            seasonality_mode='additive', # How seasonality affects trend
            changepoint_prior_scale=0.05 # Flexibility of trend changes
        )
        
        # Train the model
        model.fit(prophet_data)
        
        # Create future dataframe
        future = model.make_future_dataframe(periods=days_to_predict, freq='D')
        
        # Make predictions
        forecast = model.predict(future)
        
        # Extract only future predictions
        future_forecast = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(days_to_predict)
        
        # Ensure no negative predictions
        future_forecast['yhat'] = future_forecast['yhat'].apply(lambda x: max(0, x))
        future_forecast['yhat_lower'] = future_forecast['yhat_lower'].apply(lambda x: max(0, x))
        future_forecast['yhat_upper'] = future_forecast['yhat_upper'].apply(lambda x: max(0, x))
        
        # Calculate accuracy metrics on historical data
        historical_forecast = forecast[['ds', 'yhat']].head(len(prophet_data))
        mae = mean_absolute_error(prophet_data['y'], historical_forecast['yhat'])
        rmse = np.sqrt(mean_squared_error(prophet_data['y'], historical_forecast['yhat']))
        mape = np.mean(np.abs((prophet_data['y'] - historical_forecast['yhat']) / prophet_data['y'])) * 100
        
        # Format output
        result_df = pd.DataFrame({
            'Date': future_forecast['ds'].values,
            'Predicted_Sales': np.round(future_forecast['yhat'].values, 1),
            'Lower_Bound': np.round(future_forecast['yhat_lower'].values, 1),
            'Upper_Bound': np.round(future_forecast['yhat_upper'].values, 1)
        })
        
        metrics = {
            'mae': mae,           # Mean Absolute Error
            'rmse': rmse,         # Root Mean Squared Error
            'mape': mape,         # Mean Absolute Percentage Error
            'accuracy': max(0, 100 - mape)  # Simple accuracy percentage
        }
        
        return result_df, metrics
        
    except Exception as e:
        print(f"Prophet prediction error: {e}")
        return None, None


# Backward compatibility - keep old function name
def predict_with_linear_regression(item_df, days_to_predict=7):
    """
    Legacy Linear Regression (for comparison)
    """
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import r2_score
    
    if len(item_df) < 7:
        return None, None
    
    daily_sales = item_df.groupby('transaction_date')['quantity'].sum().reset_index()
    
    if len(daily_sales) < 2:
        return None, None
    
    daily_sales['date_ordinal'] = daily_sales['transaction_date'].map(pd.Timestamp.toordinal)
    
    X = daily_sales[['date_ordinal']].values
    y = daily_sales['quantity'].values
    
    model = LinearRegression()
    model.fit(X, y)
    
    train_predictions = model.predict(X)
    r2 = r2_score(y, train_predictions)
    
    last_date = daily_sales['transaction_date'].max()
    future_dates = [last_date + pd.Timedelta(days=i) for i in range(1, days_to_predict + 1)]
    future_ordinals = np.array([d.toordinal() for d in future_dates]).reshape(-1, 1)
    
    predictions = model.predict(future_ordinals)
    predictions = np.maximum(predictions, 0)
    
    forecast_df = pd.DataFrame({
        'Date': future_dates,
        'Predicted_Sales': np.round(predictions, 1)
    })
    
    return forecast_df, r2


if __name__ == "__main__":
    print("🧪 Testing Prophet Model...")
    # Add your test code here