import pandas as pd
from helpers import load_data
# 1. Load your data
# Use the correct column name 'transaction_date' 
# dayfirst=True ensures DD-MM-YYYY is parsed correctly
df = load_data()

# 2. Find top 5 items
top_items = df.groupby('product_name')['Quantity'].sum().sort_values(ascending=False).head(5)

# 3. Weekly Sales Sum
# Use 'transaction_date' here as well
weekly_sales = df.resample('W', on='transaction_date')['Quantity'].sum()

# Print results to verify
print("--- Top 5 Best Selling Items ---")
print(top_items)
print("\n--- Weekly Sales Preview ---")
print(weekly_sales.head())

