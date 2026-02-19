import pandas as pd

def load_data():
    return pd.read_csv('data/grocery_chain_data.csv', parse_dates=['transaction_date'], dayfirst=True)