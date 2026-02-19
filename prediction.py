from helpers import load_data

df = load_data()

# Identify Top 5 Items for the report
top_5_products = df.groupby('product_name')['Quantity'].sum().sort_values(ascending=False).head(5).index

print(f"{'Item Name':<18} | {'Avg Sales/Day':<15} | {'Days Left (Stock: 100)'}")
print("-" * 60)

for item in top_5_products:
    item_data = df[df['product_name'] == item]
    
    # Logic: Total Quantity / Number of days it was sold
    avg_sales = item_data['Quantity'].sum() / item_data['transaction_date'].nunique()
    days_left = 100 / avg_sales
    
    print(f"{item:<18} | {avg_sales:<15.2f} | {days_left:.1f} days")