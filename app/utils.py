"""
app/utils.py – Shared export helpers used across all pages.
"""
import io
import pandas as pd
from datetime import datetime


def export_to_csv(dataframe: pd.DataFrame, filename_prefix: str):
    """Convert DataFrame to CSV bytes for Streamlit download button."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv = dataframe.to_csv(index=False)
    return csv, f"{filename_prefix}_{timestamp}.csv"


def export_to_excel(dataframe: pd.DataFrame, filename_prefix: str):
    """Convert DataFrame to Excel bytes for Streamlit download button."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        dataframe.to_excel(writer, index=False, sheet_name='Data')
    output.seek(0)
    return output.getvalue(), f"{filename_prefix}_{timestamp}.xlsx"
