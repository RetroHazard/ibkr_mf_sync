import configparser
import os
import logging
import json
from datetime import datetime, date
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import ibkr_flex_query_client as ibflex
import moneyforward_processing as mfproc
import utils
from contextlib import suppress
from playwright.sync_api import sync_playwright, Error as PlaywrightError
import pandas as pd

# Load environment variables from .env file
load_dotenv()

# ロギング設定 / Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_cache_path(cache_type):
    """
    Get the most recent cache file path for a specific report type.
    Looks for any existing cache file, not just today's.

    Args:
        cache_type: 'cash' or 'positions'

    Returns:
        str: Path to cache file (may not exist yet)
    """
    cache_dir = os.path.join(os.path.dirname(__file__), '.cache')
    os.makedirs(cache_dir, exist_ok=True)

    # 既存のキャッシュファイルを探す / Look for existing cache files
    import glob
    pattern = os.path.join(cache_dir, f'ibkr_{cache_type}_*.json')
    existing_caches = glob.glob(pattern)

    if existing_caches:
        # 最新のキャッシュファイルを返す / Return the most recent cache file
        return max(existing_caches, key=os.path.getmtime)

    # 既存のキャッシュがない場合は、今日の日付でパスを返す
    # If no existing cache, return path with today's date
    return os.path.join(cache_dir, f'ibkr_{cache_type}_{date.today().isoformat()}.json')


def load_cached_data(cache_type, max_age_hours=4):
    """
    Load cached IBKR data if it exists and is less than max_age_hours old.

    Args:
        cache_type: 'cash' or 'positions'
        max_age_hours: Maximum age of cache in hours (default: 4)

    Returns:
        pandas.DataFrame or None: Cached data if valid, None otherwise
    """
    cache_path = get_cache_path(cache_type)

    if not os.path.exists(cache_path):
        logger.info(f"No cache found for {cache_type}")
        return None

    try:
        with open(cache_path, 'r') as f:
            cache_data = json.load(f)

        # タイムスタンプを確認（4時間以内か？）
        # Check timestamp (is it less than 4 hours old?)
        cache_timestamp_str = cache_data.get('timestamp')
        if not cache_timestamp_str:
            logger.info(f"Cache for {cache_type} has no timestamp, treating as stale")
            return None

        cache_timestamp = datetime.fromisoformat(cache_timestamp_str)
        age = datetime.now() - cache_timestamp
        age_hours = age.total_seconds() / 3600

        if age_hours > max_age_hours:
            logger.info(f"Cache for {cache_type} is stale ({age_hours:.1f} hours old, max {max_age_hours} hours)")
            return None

        # DataFrameに変換 / Convert to DataFrame
        df = pd.DataFrame(cache_data['data'])
        logger.info(f"Using cached {cache_type} data from {cache_timestamp_str} ({age_hours:.1f} hours ago)")
        return df

    except Exception as e:
        logger.warning(f"Failed to load cache for {cache_type}: {e}")
        return None


def save_cached_data(cache_type, df):
    """
    Save IBKR data to cache.

    Args:
        cache_type: 'cash' or 'positions'
        df: pandas.DataFrame to cache
    """
    cache_path = get_cache_path(cache_type)

    try:
        cache_data = {
            'date': date.today().isoformat(),
            'timestamp': datetime.now().isoformat(),
            'data': df.to_dict('records')
        }

        with open(cache_path, 'w') as f:
            json.dump(cache_data, f, indent=2)

        logger.info(f"Cached {cache_type} data to {cache_path}")
    except Exception as e:
        logger.warning(f"Failed to save cache for {cache_type}: {e}")


def get_ibkr_data_with_cache(ib_flex_token, ib_flex_query_id, report_type, cache_type):
    """
    Get IBKR Flex Query data with caching.

    Args:
        ib_flex_token: IBKR Flex token
        ib_flex_query_id: IBKR Flex Query ID
        report_type: 'CashReport' or 'OpenPositions'
        cache_type: 'cash' or 'positions'

    Returns:
        pandas.DataFrame: IBKR report data
    """
    # キャッシュをチェック / Check cache
    cached_df = load_cached_data(cache_type)
    if cached_df is not None:
        return cached_df

    # キャッシュがない場合はAPIから取得 / Fetch from API if no cache
    logger.info(f"Fetching fresh {cache_type} data from IBKR API...")
    df = ibflex.get_ib_flex_report(ib_flex_token, ib_flex_query_id, report_type)

    # キャッシュに保存 / Save to cache
    save_cached_data(cache_type, df)

    return df


def get_config_value(env_var, config, section, key, required=True):
    """
    環境変数から設定値を取得し、見つからない場合はconfig.iniにフォールバック。
    Get configuration value from environment variable first, fallback to config.ini.

    引数:
    Args:
        env_var: チェックする環境変数名
                 Environment variable name to check
        config: ConfigParserオブジェクト
                ConfigParser object
        section: 設定ファイルのセクション名
                 Config file section name
        key: 設定ファイルのキー名
             Config file key name
        required: Trueの場合、両方のソースで値が見つからない場合はエラーを発生
                  If True, raise error if value not found in either source

    戻り値:
    Returns:
        環境変数または設定ファイルからの設定値
        Configuration value from environment or config file
    """
    # 最初に環境変数を試す
    # Try environment variable first
    value = os.environ.get(env_var)
    if value is not None:
        return value

    # config.iniにフォールバック
    # Fallback to config.ini
    try:
        return config.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        if required:
            raise ValueError(
                f"Configuration '{env_var}' not found in environment variables or "
                f"config.ini [{section}][{key}]. Please set environment variable or update config.ini"
            )
        return None


def main():
    # ConfigParserオブジェクトを作成してconfig.iniファイルを読み込む
    # Create ConfigParser object and read config.ini file
    config = configparser.ConfigParser()
    config.read('config.ini')

    # 環境変数を優先、config.iniをフォールバックとして設定を取得
    # Environment variables take precedence, config.ini as fallback
    MF_EMAIL = get_config_value('MF_EMAIL', config, 'moneyforward', 'email')
    MF_PASS = get_config_value('MF_PASSWORD', config, 'moneyforward', 'password')
    MF_IB_INSTITUTION_URL = get_config_value('MF_IB_INSTITUTION_URL', config, 'moneyforward', 'ib_institution_url')
    IB_FLEX_TOKEN = get_config_value('IBKR_FLEX_TOKEN', config, 'ibkr_flex_query', 'token')
    # TODO: トークン有効期限追跡を追加（TODO.md参照）
    # TODO: Add token expiration tracking (see TODO.md)
    # IBKR Flexトークンは1年後に期限切れ - 期限切れ前にユーザーに警告する必要あり
    # IBKR Flex tokens expire after 1 year - need to warn users before expiration
    IB_FLEX_QUERY_FOR_MF_ID = get_config_value('IBKR_FLEX_QUERY_ID', config, 'ibkr_flex_query', 'query_id')
    # ---IB FLEXレポートを取得（キャッシュ使用）---
    # ---GET IB FLEX REPORT (with caching)---
    ib_cash_report = get_ibkr_data_with_cache(IB_FLEX_TOKEN, IB_FLEX_QUERY_FOR_MF_ID, 'CashReport', 'cash')
    # 現金残高を日本円に変換
    # Convert cash balance to JPY
    ib_cash_report = utils.add_value_jpy(ib_cash_report, 'endingCash', 'endingCash_JPY')
    ib_open_position = get_ibkr_data_with_cache(IB_FLEX_TOKEN, IB_FLEX_QUERY_FOR_MF_ID, 'OpenPositions', 'positions')
    if not ib_open_position.empty:
        # デバッグ: 利用可能な列を表示
        # Debug: Show available columns
        logger.info(f"Available IBKR OpenPositions columns: {ib_open_position.columns.tolist()}")
        # 取得金額を日本円に変換
        # Convert acquisition cost to JPY
        ib_open_position = utils.add_value_jpy(ib_open_position, 'costBasisMoney', 'costBasisMoney_JPY')
        # 現在価値を日本円に変換
        # Convert current value to JPY
        ib_open_position = utils.add_value_jpy(ib_open_position, 'positionValue', 'positionValue_JPY')
    else:
        print("No open positions found.")
    # ブラウザセッションの保存先（永続化用）
    # Browser session storage location (for persistence)
    storage_state_path = os.path.join(os.path.dirname(__file__), '.browser_session.json')

    # ヘッドレスモードで実行を試みる（2FAが必要な場合は表示モードで再試行）
    # Try running in headless mode first (retry in headed mode if 2FA is required)
    headless_mode = True
    needs_2fa = False

    with sync_playwright() as playwright:
        # 新しいブラウザコンテキストを開く
        # Open a new browser context
        logger.info(f"Launching browser in {'headless' if headless_mode else 'headed'} mode")
        browser = playwright.chromium.launch(headless=headless_mode)

        # 保存されたセッションがあれば使用
        # Use saved session if it exists
        context_options = {
            # ユーザーエージェントを変更 - MoneyForwardのログイン画面を表示するために必要
            # Change user agent - Required to display MoneyForward login screen
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }

        # 既存のセッションファイルがあれば読み込む
        # Load existing session file if available
        if os.path.exists(storage_state_path):
            context_options["storage_state"] = storage_state_path
            logger.info("Loading saved browser session")

        context = browser.new_context(**context_options)
        page = context.new_page()

        # タイムアウトを5分に設定（メール認証の時間を確保）
        # Set timeout to 5 minutes (allow time for email verification)
        page.set_default_timeout(300000)  # 5 minutes in milliseconds

        # 後で削除できるダイアログハンドラを設定
        # Set up a dialog handler that can be removed later
        def dialog_handler(dialog):
            dialog.accept()

        try:
            # ダイアログハンドラを追加
            # Add the dialog handler
            page.on("dialog", dialog_handler)
            try:
                page.goto(MF_IB_INSTITUTION_URL)
                # ---MoneyForward Meログイン---
                # ---MoneyForward Me Login---
                page, needs_2fa = mfproc.login(page, MF_EMAIL, MF_PASS)

                # 2FA が必要な場合、ヘッドレスモードでは処理できないため終了
                # If 2FA is required, we need to restart in headed mode
                if needs_2fa and headless_mode:
                    logger.warning("2FA verification required - restarting in headed mode for user interaction")
                    logger.warning("Please complete the email verification in the browser window that will open")
                    context.close()
                    browser.close()

                    # 表示モードで再起動
                    # Restart in headed mode
                    browser = playwright.chromium.launch(headless=False)
                    context = browser.new_context(**context_options)
                    page = context.new_page()
                    page.set_default_timeout(300000)
                    page.on("dialog", dialog_handler)

                    page.goto(MF_IB_INSTITUTION_URL)
                    page, needs_2fa = mfproc.login(page, MF_EMAIL, MF_PASS)

                    if needs_2fa:
                        # ユーザーが2FAを完了するまで待機
                        # Wait for user to complete 2FA
                        logger.info("Waiting for you to complete email verification (up to 5 minutes)...")
                        page.wait_for_load_state('networkidle', timeout=300000)
                        logger.info("2FA verification completed")

                page.wait_for_load_state('networkidle')
            except PlaywrightError as e:
                if "Cannot accept dialog which is already handled!" in str(e):
                    print("Dialog was already handled, continuing execution...")
                else:
                    # 期待しているエラーでない場合は再度発生させる
                    # Re-raise the exception if it's not the one we're expecting
                    raise
            finally:
                # 複数のハンドラを防ぐためにダイアログハンドラを削除
                # Remove the dialog handler to prevent multiple handlers
                page.remove_listener("dialog", dialog_handler)

            # ---ログイン後、IBKRの口座ページに遷移---
            # ---After login, navigate to IBKR institution page---
            page.goto(MF_IB_INSTITUTION_URL)
            page.wait_for_load_state('networkidle')

            # ---取得したIB FLEXレポートをMoneyForward MEに反映---
            # ---Reflect retrieved IB FLEX report to MoneyForward ME---
            mfproc.reflect_to_mf_cash_deposit(page, ib_cash_report)
            mfproc.reflect_to_mf_equity(page, ib_open_position)

            # セッション状態を保存（次回から2FA不要）
            # Save session state (skip 2FA on next run)
            context.storage_state(path=storage_state_path)
            logger.info(f"Browser session saved to {storage_state_path}")
        finally:
            # ブラウザコンテキストを閉じる（例外が発生しても常に実行）
            # Close browser context (always executed even if exception occurs)
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
