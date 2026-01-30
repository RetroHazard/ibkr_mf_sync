import yfinance as yf
import logging
from requests.exceptions import RequestException, Timeout
import time

# ロギング設定 / Configure logging
logger = logging.getLogger(__name__)


def get_latest_fx_rate(from_currency='USD', to_currency='JPY', timeout=10, max_retries=3):
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

    # リトライロジック付きでAPI呼び出し / API call with retry logic
    for attempt in range(max_retries):
        try:
            # 通貨ペアのデータを取得
            # Get currency pair data
            fx_ticker = yf.Ticker(currency_pair)
            # 履歴データを取得（タイムアウト設定付き）
            # Get historical data (with timeout)
            # Note: yfinance doesn't directly support timeout, but requests library does
            try:
                fx_rate_history = fx_ticker.history(period='1d', timeout=timeout)
            except (TypeError, AttributeError) as api_error:
                # Yahoo Finance APIがNoneを返した場合のハンドリング
                # Handle case where Yahoo Finance API returns None
                logger.warning(f"Yahoo Finance API returned invalid data for {currency_pair} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise ValueError(f"Yahoo Finance API failed to return data after {max_retries} attempts") from api_error

            # データが返されたか検証 / Validate that data was returned
            if fx_rate_history.empty:
                logger.error(f"No FX rate data returned for {currency_pair}")
                raise ValueError(f"No FX rate data available for {currency_pair}")

            # 'Close'列が存在するか確認 / Check if 'Close' column exists
            if 'Close' not in fx_rate_history.columns:
                logger.error(f"'Close' column not found in FX rate data for {currency_pair}")
                raise ValueError(f"Invalid FX rate data structure for {currency_pair}")

            # 最新の為替レートを取得
            # Get latest exchange rate
            latest_fx_rate = fx_rate_history['Close'].iloc[-1]

            # レートが有効な数値か検証 / Validate rate is a valid number
            if not isinstance(latest_fx_rate, (int, float)) or latest_fx_rate <= 0:
                logger.error(f"Invalid FX rate value: {latest_fx_rate} for {currency_pair}")
                raise ValueError(f"Invalid FX rate value: {latest_fx_rate}")

            logger.info(f"Successfully fetched FX rate for {currency_pair}: {latest_fx_rate}")
            return latest_fx_rate

        except (RequestException, Timeout) as e:
            logger.warning(f"Network error fetching FX rate for {currency_pair} (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                # 指数バックオフでリトライ / Retry with exponential backoff
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to fetch FX rate after {max_retries} attempts")
                raise RuntimeError(f"Failed to fetch FX rate for {currency_pair} after {max_retries} attempts") from e

        except (ValueError, IndexError, KeyError) as e:
            logger.error(f"Data error fetching FX rate for {currency_pair}: {e}")
            raise RuntimeError(f"Failed to parse FX rate data for {currency_pair}: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error fetching FX rate for {currency_pair}: {e}")
            raise RuntimeError(f"Unexpected error fetching FX rate for {currency_pair}: {e}") from e


def add_value_jpy(df, calculation_column_name, additional_column_name):
    if df.empty:
        # 空のDataFrameを変更せずに返す
        # Return the empty DataFrame without modifications
        return df
    if 'fx_rate_to_JPY' not in df.columns:
        # DataFrameに為替レートを追加
        # Add FX rate to the DataFrame
        # IBKRのfxRateToBaseを優先して使用、利用できない場合はyfinanceにフォールバック
        # Prefer IBKR's fxRateToBase, fallback to yfinance if not available
        def get_fx_rate(row):
            if row['currency'] == 'JPY':
                return 1.0
            # IBKRのfxRateToBaseが利用可能か確認
            # Check if IBKR's fxRateToBase is available
            if 'fxRateToBase' in row and row['fxRateToBase'] and str(row['fxRateToBase']).strip():
                logger.info(f"Using IBKR FX rate for {row['currency']}: {row['fxRateToBase']}")
                return float(row['fxRateToBase'])
            # yfinanceにフォールバック
            # Fallback to yfinance
            logger.info(f"IBKR FX rate not available for {row['currency']}, using yfinance")
            return float(get_latest_fx_rate(row['currency']))

        df['fx_rate_to_JPY'] = df.apply(get_fx_rate, axis=1)
    # JPY列を追加し、日本円に変換
    # Add JPY column and convert to JPY
    df[additional_column_name] = df.apply(lambda x: float(x[calculation_column_name]) * x['fx_rate_to_JPY'], axis=1)
    # JPY列を整数に変換
    # Convert JPY column to integer
    df[additional_column_name] = df[additional_column_name].astype(int)
    return df
