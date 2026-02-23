import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

def predict_future_demand(item_df, days_to_predict=7):
    """
    Takes a dataframe for a single item and predicts future sales 
    using Linear Regression.
    
    Returns: (forecast_df, r2_score) or (None, None) if insufficient data
    """
    # Data validation
    if len(item_df) < 7:
        return None, None
    
    # 1. Prepare Data: Group by date
    daily_sales = item_df.groupby('transaction_date')['quantity'].sum().reset_index()
    
    if len(daily_sales) < 2:
        return None, None
    
    # 2. Convert dates to numeric 'ordinal' values for the ML model
    daily_sales['date_ordinal'] = daily_sales['transaction_date'].map(pd.Timestamp.toordinal)
    
    X = daily_sales[['date_ordinal']].values  # Feature: Date
    y = daily_sales['quantity'].values        # Target: Units Sold
    
    # 3. Train the Model
    model = LinearRegression()
    model.fit(X, y)
    
    # Calculate accuracy
    train_predictions = model.predict(X)
    r2 = r2_score(y, train_predictions)
    
    # 4. Create future dates for prediction
    last_date = daily_sales['transaction_date'].max()
    future_dates = [last_date + pd.Timedelta(days=i) for i in range(1, days_to_predict + 1)]
    future_ordinals = np.array([d.toordinal() for d in future_dates]).reshape(-1, 1)
    
    # 5. Predict
    predictions = model.predict(future_ordinals)
    predictions = np.maximum(predictions, 0)  # Remove any negative predictions
    
    # Return as a simple DataFrame
    forecast_df = pd.DataFrame({
        'Date': future_dates,
        'Predicted_Sales': np.round(predictions, 1)
    })
    
    return forecast_df, r2