import pandas as pd
import yfinance as yf
import pandas_market_calendars as mcal
import requests
from datetime import datetime, timedelta
from get_index_tickers import get_index_tickers

# ------------ Settings ------------
INDEX_NAME = 'S&P500'  # Choose from 'S&P500', 'FTSE100', 'DAX'
INDEX_TICKERS = get_index_tickers(INDEX_NAME)
START_DATE = '2025-01-01'
END_DATE = datetime.today().strftime('%Y-%m-%d')
DROP_THRESHOLD = -0.03  # Drop >= 3%
LOOKAHEAD_DAYS = 14
NEWS_API_KEY = 'cb88fbbea0d04fda8c2ea37c63ee9a28'

# ------------ Functions ------------

def categorize_recovery(best_recovery_pct):
    if best_recovery_pct >= 0.90:
        return "Full Recovery (90%+)"
    elif 0.75 <= best_recovery_pct < 0.90:
        return "Good Recovery (75-90%)"
    elif 0.50 <= best_recovery_pct < 0.75:
        return "Partial Recovery (50-75%)"
    else:
        return "Poor Recovery (<50%)"

def check_stock_recovery(stock_data, drop_date, drop_open_price, drop_close_price):
    future_prices = stock_data[stock_data.index > drop_date].head(LOOKAHEAD_DAYS)

    recovery_date_50 = None
    recovery_date_75 = None
    recovery_date_90 = None
    best_recovery_pct = 0

    for date, row in future_prices.iterrows():
        future_close_price = row['Close']

        if isinstance(future_close_price, pd.Series):
            future_close_price = future_close_price.iloc[0]

        if (drop_open_price - drop_close_price) == 0:
            continue  # avoid division by zero

        recovery_pct = (future_close_price - drop_close_price) / (drop_open_price - drop_close_price)

        if recovery_pct > best_recovery_pct:
            best_recovery_pct = recovery_pct

        if recovery_date_50 is None and recovery_pct >= 0.50:
            recovery_date_50 = date
        if recovery_date_75 is None and recovery_pct >= 0.75:
            recovery_date_75 = date
        if recovery_date_90 is None and recovery_pct >= 0.90:
            recovery_date_90 = date

    recovery_quality = categorize_recovery(best_recovery_pct)
    return recovery_date_50, recovery_date_75, recovery_date_90, best_recovery_pct, recovery_quality

def get_news_for_ticker(ticker, drop_date):
    url = (
        f"https://newsapi.org/v2/everything?"
        f"q={ticker}&"
        f"from={drop_date}&"
        f"to={drop_date}&"
        f"sortBy=relevancy&"
        f"apiKey={NEWS_API_KEY}"
    )
    try:
        response = requests.get(url)
        data = response.json()

        if data.get("status") == "ok" and data.get("totalResults", 0) > 0:
            first_article = data["articles"][0]
            title = first_article.get("title", "unknown")
            link = first_article.get("url", "unknown")
            # Simplify title to tags by splitting words
            tags = ', '.join(title.lower().split()[:5])
            return tags, link
        else:
            return "unknown", "unknown"
    except Exception as e:
        print(f"News fetch error for {ticker}: {e}")
        return "unknown", "unknown"

def backfill_stock_drops():
    results = []

    nyse = mcal.get_calendar('NYSE')
    schedule = nyse.schedule(start_date=START_DATE, end_date=END_DATE)
    trading_days = schedule.index

    for ticker in INDEX_TICKERS:
        print(f"Processing {ticker}...")
        try:
            data = yf.download(ticker, start=START_DATE, end=END_DATE)
            if data.empty:
                continue

            # Resample to one row per day to avoid duplicate timestamps
            data = data.resample('1D').first()
            data.dropna(inplace=True)

            for current_day in trading_days:
                if current_day not in data.index:
                    continue  # No trading data for this day

                open_price = data.loc[current_day]['Open']
                close_price = data.loc[current_day]['Close']

                if isinstance(open_price, pd.Series):
                    open_price = open_price.iloc[0]
                if isinstance(close_price, pd.Series):
                    close_price = close_price.iloc[0]

                drop_pct = (close_price / open_price) - 1

                if drop_pct <= DROP_THRESHOLD:
                    print(f"Drop detected on {current_day.date()} for {ticker}: {round(drop_pct * 100, 2)}%")

                    future_data = data[data.index > current_day]
                    recovery_date_50, recovery_date_75, recovery_date_90, best_recovery_pct, recovery_quality = check_stock_recovery(
                        stock_data=future_data,
                        drop_date=current_day,
                        drop_open_price=open_price,
                        drop_close_price=close_price
                    )

                    # Fetch news headline tags and link
                    tags, link = get_news_for_ticker(ticker, current_day.strftime('%Y-%m-%d'))

                    row_result = {
                        "Date": current_day,
                        "Ticker": ticker,
                        "% Drop": round(drop_pct * 100, 2),
                        "Open": round(open_price, 2),
                        "Close": round(close_price, 2),
                        "Recovery Date 50%": recovery_date_50,
                        "Recovery Date 75%": recovery_date_75,
                        "Recovery Date 90%": recovery_date_90,
                        "Best Recovery % Achieved": round(best_recovery_pct, 2),
                        "Recovery Quality": recovery_quality,
                        "Headline Tags": tags,
                        "Headline Link": link
                    }
                    results.append(row_result)

        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    df = pd.DataFrame(results)
    df.sort_values(by=["Date", "Ticker"], inplace=True)
    df.to_csv('backfill_stock_drops.csv', index=False)
    print("Backfill complete: saved to backfill_stock_drops.csv")

if __name__ == "__main__":
    backfill_stock_drops()
