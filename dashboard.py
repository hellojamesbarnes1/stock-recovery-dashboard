import streamlit as st
import pandas as pd

st.set_page_config(page_title="Stock Drop & Recovery Dashboard", layout="wide")
st.title("\U0001F4C8 Stock Drop & Recovery Dashboard")

# Load backfill data
df = pd.read_csv("backfill_stock_drops.csv")

# --- Clean ticker symbols upfront ---
df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()

# --- Mapping for known non-US stocks (base ticker) ---
ticker_to_exchange = {
    'BP': 'LSE',        # British Petroleum - London
    'BHP': 'ASX',       # BHP Group - Australia
    'SHOP': 'TSX',      # Shopify - Toronto
    '0700': 'HKEX',     # Tencent - Hong Kong
    # Add more mappings if needed
}

# --- Add Exchange column using mapping + smart guessing ---
if 'Exchange' not in df.columns:
    def infer_exchange(ticker):
        ticker = ticker.strip().upper()
        base_ticker = ticker.split('.')[0]  # Get base ticker (before any dot)
        if base_ticker in ticker_to_exchange:
            return ticker_to_exchange[base_ticker]
        elif '.' in ticker:
            suffix = ticker.split('.')[-1]
            if suffix == 'L':
                return 'LSE'
            elif suffix == 'TO':
                return 'TSX'
            elif suffix == 'AX':
                return 'ASX'
            elif suffix == 'HK':
                return 'HKEX'
            else:
                return suffix.upper()
        else:
            if ticker.isalpha() and len(ticker) <= 4:
                return 'NASDAQ'
            else:
                return 'NYSE'

    df['Exchange'] = df['Ticker'].apply(infer_exchange)

# Sort by Drop Date, newest first
df = df.sort_values(by="Date", ascending=False)

# Sidebar filters
st.sidebar.header("\U0001F50D Filter Options")

# Filter by Ticker
tickers = df['Ticker'].unique()
selected_tickers = st.sidebar.multiselect("Select Tickers:", tickers, default=tickers)

# Filter by Recovery Quality
recovery_quality_options = ['Full Recovery (90%+)', 'Good Recovery (75-90%)', 'Partial Recovery (50-75%)', 'Poor Recovery (<50%)']
selected_recovery = st.sidebar.multiselect("Select Recovery Quality:", recovery_quality_options, default=recovery_quality_options)

# Filter by Date Range
min_date = pd.to_datetime(df['Date']).min()
max_date = pd.to_datetime(df['Date']).max()
start_date, end_date = st.sidebar.date_input("Select Date Range:", [min_date, max_date], min_value=min_date, max_value=max_date)

# Apply filters
filtered_df = df[
    (df['Ticker'].isin(selected_tickers)) &
    (df['Recovery Quality'].isin(selected_recovery)) &
    (pd.to_datetime(df['Date']) >= pd.to_datetime(start_date)) &
    (pd.to_datetime(df['Date']) <= pd.to_datetime(end_date))
]

# Reorder columns for nicer view
columns_order = [
    'Date', 'Ticker', 'Exchange', '% Drop', 'Open', 'Close',
    'Recovery Date 50%', 'Recovery Date 75%', 'Recovery Date 90%',
    'Best Recovery % Achieved', 'Recovery Quality',
    'Headline Tags', 'Headline Link'
]
filtered_df = filtered_df[columns_order]

# --- Format Dates: Remove Year ---
for col in ['Date', 'Recovery Date 50%', 'Recovery Date 75%', 'Recovery Date 90%']:
    if col in filtered_df.columns:
        filtered_df[col] = pd.to_datetime(filtered_df[col], errors='coerce').dt.strftime('%d %b')

# --- Format Best Recovery % Achieved as Percent ---
if 'Best Recovery % Achieved' in filtered_df.columns:
    filtered_df['Best Recovery % Achieved'] = (filtered_df['Best Recovery % Achieved'] * 100).round(1).astype(str) + '%'

# --- Format numeric columns (% Drop, Open, Close) to 2 decimal places ---
for col in ['% Drop', 'Open', 'Close']:
    if col in filtered_df.columns:
        filtered_df[col] = filtered_df[col].map(lambda x: f"{x:.2f}")

# --- Styling functions ---
def highlight_recovery_date(val):
    if pd.isna(val) or val == "None" or val == "":
        return 'background-color: red'
    else:
        return 'background-color: green'

def highlight_recovery_quality(val):
    if val == "Poor Recovery (<50%)":
        return 'background-color: red'
    elif val == "Partial Recovery (50-75%)":
        return 'background-color: orange'
    elif val in ["Good Recovery (75-90%)", "Full Recovery (90%+)"]:
        return 'background-color: green'
    else:
        return ''

def darken_unrecovered_rows(row):
    if pd.isna(row['Recovery Date 90%']) or row['Recovery Date 90%'] in ["None", ""]:
        return ['background-color: #333333'] * len(row)
    else:
        return [''] * len(row)

# --- Apply styles ---
styled_df = filtered_df.style \
    .applymap(highlight_recovery_date, subset=['Recovery Date 50%', 'Recovery Date 75%', 'Recovery Date 90%']) \
    .applymap(highlight_recovery_quality, subset=['Recovery Quality']) \
    .apply(darken_unrecovered_rows, axis=1) \
    .set_table_styles([
        {'selector': 'tbody tr:hover',
         'props': [('background-color', '#444444')]}
    ])

# --- Display styled dataframe ---
st.dataframe(styled_df, use_container_width=True)

st.caption("\U0001F4C9 Data: Stock drops >= 3% with 14-day recovery tracking and news headlines.")
