# AG Data Analyzer

A Streamlit-based data analysis workspace for Excel and CSV files.

## Features
- Excel and CSV upload
- Excel worksheet selection
- Dataset overview and preview
- Column profile and descriptive statistics
- Interactive histograms, box plots, and category bar charts
- Missing-value and duplicate checks
- Optional cleaning on a separate copy
- Cleaned CSV download

## Run locally (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

The uploaded original file is not modified. Cleaning operations are applied to a separate in-memory copy.
