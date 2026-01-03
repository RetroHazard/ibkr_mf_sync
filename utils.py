import yfinance as yf


def get_latest_fx_rate(from_currency='USD', to_currency='JPY'):
    # TODO: 為替レートの精度を向上させ、エラーハンドリングを追加（TODO.md参照）
    # TODO: Improve FX rate accuracy and add error handling (see TODO.md)
    # - Yahoo Financeのレートは概算値
    # - Yahoo Finance rates are approximate
    # - API呼び出しを減らすためにキャッシュを追加
    # - Add caching to reduce API calls
    # - API障害を適切に処理
    # - Handle API failures gracefully
    # - 代替FXデータソースを検討
    # - Consider alternative FX data sources
    currency_pair = f'{from_currency}{to_currency}=X'
    # 通貨ペアのデータを取得
    # Get currency pair data
    fx_ticker = yf.Ticker(currency_pair)
    # 履歴データを取得
    # Get historical data
    fx_rate_history = fx_ticker.history(period='1d')
    # 最新の為替レートを取得
    # Get latest exchange rate
    latest_fx_rate = fx_rate_history['Close'].iloc[-1]
    return latest_fx_rate


def add_value_jpy(df, calculation_column_name, additional_column_name):
    if df.empty:
        # 空のDataFrameを変更せずに返す
        # Return the empty DataFrame without modifications
        return df
    if 'fx_rate_to_JPY' not in df.columns:
        # DataFrameに為替レートを追加
        # Add FX rate to the DataFrame
        df['fx_rate_to_JPY'] = df.apply(
            lambda x: float(1) if x['currency'] == 'JPY' else float(get_latest_fx_rate(x['currency'])), axis=1)
    # JPY列を追加し、日本円に変換
    # Add JPY column and convert to JPY
    df[additional_column_name] = df.apply(lambda x: float(x[calculation_column_name]) * x['fx_rate_to_JPY'], axis=1)
    # JPY列を整数に変換
    # Convert JPY column to integer
    df[additional_column_name] = df[additional_column_name].astype(int)
    return df
