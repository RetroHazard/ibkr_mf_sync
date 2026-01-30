import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import logging
from asset_types import (
    ASSET_SUBCLASS_MAP,
    get_asset_type_for_currency,
    ASSET_TYPE_CASH_DEPOSIT
)

# ロギング設定 / Configure logging
logger = logging.getLogger(__name__)


class SecureCredential:
    """
    機密情報をラップして、ログやスタックトレースでの露出を防ぐクラス。
    Wrapper class to protect sensitive credentials from exposure in logs and stack traces.

    注意: これは完全なセキュリティソリューションではなく、偶発的な露出を防ぐためのものです。
    Note: This is not a complete security solution, but helps prevent accidental exposure.

    セキュリティのベストプラクティス:
    Security best practices:
    - 本番環境では環境変数を使用 / Use environment variables in production
    - 可能な限りシークレット管理システムを使用 / Use secret management systems when possible
    - 使用後は機密データをクリア / Clear sensitive data after use
    """
    def __init__(self, value):
        self._value = value

    def get(self):
        """機密値を取得 / Get the sensitive value"""
        return self._value

    def clear(self):
        """機密値をメモリからクリア / Clear the sensitive value from memory"""
        self._value = None

    def __repr__(self):
        """機密値を隠す / Hide sensitive value"""
        return "<SecureCredential: ***REDACTED***>"

    def __str__(self):
        """機密値を隠す / Hide sensitive value"""
        return "***REDACTED***"


def format_asset_name(row):
    """
    IBKRの資産データに基づいてMoneyForward表示用の資産名をフォーマットします。
    Format asset name for display in MoneyForward based on IBKR asset data.

    フォーマット例:
    Formatting examples:
        株式 (STK): "AAPL (100)"
        Stocks: "AAPL (100)"

        オプション (OPT): "AAPL Jan24 $150-C (10)" または "AAPL Jan24 $150-P (10)"
        Options: "AAPL Jan24 $150-C (10)" or "AAPL Jan24 $150-P (10)"

        先物 (FUT): "ES Mar24 (5)"
        Futures: "ES Mar24 (5)"

        CFD: "SPX500 (10)"

        ワラント (WAR): "TSLAW (1000)"
        Warrants: "TSLAW (1000)"

        外国為替 (SWP/CASH): "EUR.USD (100k)"
        Forex: "EUR.USD (100k)"

        投資信託 (FND): "VTSAX (50)"
        Mutual Funds: "VTSAX (50)"

        債券 (BND): "US10Y 2.5% (10)"
        Bonds: "US10Y 2.5% (10)"

    ハイフン区切り文字はCall (C) vs Put (P)契約を明確に区別します。
    The hyphen separator clearly distinguishes Call (C) vs Put (P) contracts.
    同じ行使価格/期日で両方が同時に保有される可能性があるため重要です。
    This is critical since both can be held simultaneously for the same strike/date.

    引数:
    Args:
        row: IBKRからの資産データを含むDataFrame行
             DataFrame row containing asset data from IBKR

    戻り値:
    Returns:
        人間が読みやすい形式の資産名（MoneyForward制約により最大20文字）
        Human-friendly formatted asset name (max 20 chars for MoneyForward)
    """
    symbol = str(row['symbol']) if 'symbol' in row and row['symbol'] != 'NONE' else 'UNKNOWN'
    position = str(row['position']) if 'position' in row and row['position'] != 'NONE' else '0'
    asset_category = str(row.get('assetCategory', 'STK'))

    # オプション (OPT)
    # Options
    if asset_category == 'OPT':
        # オプション形式: "AAPL Jan24 $150-C (10)"
        # Option format: "AAPL Jan24 $150-C (10)"
        strike = str(row.get('strike', ''))
        expiry = str(row.get('expiry', ''))
        put_call = str(row.get('putCall', ''))

        # 有効期限フォーマット: "20240119" -> "Jan24"
        # Format expiry date: "20240119" -> "Jan24"
        try:
            if expiry and expiry != 'NONE' and len(expiry) == 8:
                expiry_date = datetime.strptime(expiry, '%Y%m%d')
                month_abbr = expiry_date.strftime('%b')  # Jan, Feb, Mar, etc.
                year_short = expiry_date.strftime('%y')  # 24, 25, etc.
                expiry_formatted = f"{month_abbr}{year_short}"
            else:
                expiry_formatted = expiry[:6] if expiry != 'NONE' else ''
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to parse expiry date '{expiry}': {e}")
            expiry_formatted = expiry[:6] if expiry != 'NONE' else ''

        # 行使価格フォーマット: "150.0" -> "$150"
        # Format strike: "150.0" -> "$150"
        try:
            if strike and strike != 'NONE':
                strike_num = float(strike)
                if strike_num == int(strike_num):
                    strike_formatted = f"${int(strike_num)}"
                else:
                    strike_formatted = f"${strike_num:.1f}"
            else:
                strike_formatted = ''
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse strike price '{strike}': {e}")
            strike_formatted = f"${strike}" if strike != 'NONE' else ''

        # Put/Call インジケーター: C または P
        # Put/Call indicator: C or P
        pc_indicator = put_call[0].upper() if put_call and put_call != 'NONE' else ''

        # オプション名を構築: 明確さのためハイフン区切りで "AAPL Jan24 $150-C (10)"
        # Build option name: "AAPL Jan24 $150-C (10)" with hyphen separator for clarity
        option_name = f"{symbol} {expiry_formatted} {strike_formatted}-{pc_indicator} ({position})"

        # 20文字制限内に収める（MoneyForward制約）
        # Ensure within 20 char limit (MoneyForward constraint)
        if len(option_name) > 20:
            # 必要に応じてシンボルを切り詰める: "AAPL" -> "APL"
            # Truncate symbol if needed: "AAPL" -> "APL"
            symbol_short = symbol[:3] if len(symbol) > 4 else symbol
            option_name = f"{symbol_short} {expiry_formatted} {strike_formatted}-{pc_indicator} ({position})"

        return option_name[:20]  # 20文字でハードリミット / Hard limit at 20 chars

    # 先物 (FUT)
    # Futures
    elif asset_category == 'FUT':
        # 先物形式: "ES Mar24 (5)"
        # Futures format: "ES Mar24 (5)"
        expiry = str(row.get('expiry', ''))

        # 有効期限フォーマット: "20240315" -> "Mar24"
        # Format expiry date: "20240315" -> "Mar24"
        try:
            if expiry and expiry != 'NONE' and len(expiry) == 8:
                expiry_date = datetime.strptime(expiry, '%Y%m%d')
                month_abbr = expiry_date.strftime('%b')
                year_short = expiry_date.strftime('%y')
                expiry_formatted = f"{month_abbr}{year_short}"
            else:
                expiry_formatted = ''
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to parse futures expiry date '{expiry}': {e}")
            expiry_formatted = ''

        if expiry_formatted:
            future_name = f"{symbol} {expiry_formatted} ({position})"
        else:
            future_name = f"{symbol} ({position})"

        return future_name[:20]

    # CFD（差金決済取引）
    # CFD (Contract for Difference)
    elif asset_category == 'CFD':
        # CFD形式: "SPX500 (10)"
        # CFD format: "SPX500 (10)"
        cfd_name = f"{symbol} ({position})"
        return cfd_name[:20]

    # ワラント (WAR)
    # Warrants
    elif asset_category == 'WAR':
        # ワラント形式: "TSLAW (1000)"
        # Warrant format: "TSLAW (1000)"
        warrant_name = f"{symbol} ({position})"
        return warrant_name[:20]

    # 外国為替 (SWP/CASH)
    # Forex (Swaps/FX)
    elif asset_category == 'SWP' or asset_category == 'CASH':
        # 外国為替形式: "EUR.USD (100k)"
        # Forex format: "EUR.USD (100k)"
        # ポジションをk（千単位）でフォーマット
        # Format position in k (thousands)
        try:
            pos_num = float(position)
            if abs(pos_num) >= 1000:
                pos_formatted = f"{int(pos_num/1000)}k"
            else:
                pos_formatted = position
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse forex position '{position}': {e}")
            pos_formatted = position

        forex_name = f"{symbol} ({pos_formatted})"
        return forex_name[:20]

    # 投資信託 (FND)
    # Mutual Funds
    elif asset_category == 'FND':
        # 投資信託形式: "VTSAX (50)"
        # Fund format: "VTSAX (50)"
        fund_name = f"{symbol} ({position})"
        return fund_name[:20]

    # 債券 (BND)
    # Bonds
    elif asset_category == 'BND':
        # 債券形式: "US10Y 2.5% (10)"
        # Bond format: "US10Y 2.5% (10)"
        # 説明フィールドから利率を抽出しようと試みる
        # Try to extract coupon rate from description field
        description = str(row.get('description', ''))
        coupon = ''

        # 説明から利率パターンを検索（例: "2.5%"）
        # Search for coupon pattern in description (e.g., "2.5%")
        import re
        coupon_match = re.search(r'(\d+\.?\d*)\s*%', description)
        if coupon_match:
            coupon = f" {coupon_match.group(1)}%"

        bond_name = f"{symbol}{coupon} ({position})"
        return bond_name[:20]

    # 商品間スプレッド (ICS)
    # Inter-Commodity Spreads
    elif asset_category == 'ICS':
        # ICS形式: "GC-SI (2)"
        # ICS format: "GC-SI (2)"
        ics_name = f"{symbol} ({position})"
        return ics_name[:20]

    # 株式およびその他（デフォルト）
    # Stocks and other (default)
    else:
        # 株式形式: "AAPL (100)"
        # Stock format: "AAPL (100)"
        stock_name = f"{symbol} ({position})"
        return stock_name[:20]


def requires_2fa_verification(page):
    """
    Check if the page is showing an email OTP / 2FA verification prompt.

    Args:
        page: Playwright page object

    Returns:
        bool: True if verification is required, False otherwise
    """
    try:
        url = page.url
        # MoneyForwardの2FA/OTP確認ページのURLパターンをチェック
        # Check for MoneyForward 2FA/OTP verification page URL patterns
        if 'email_otp' in url or 'verification' in url.lower() or 'authenticate' in url.lower():
            logger.info(f"2FA verification page detected: {url}")
            return True

        # ページタイトルもチェック
        # Also check page title
        title = page.title()
        if '認証' in title or 'verification' in title.lower() or 'authenticate' in title.lower():
            logger.info(f"2FA verification page detected by title: {title}")
            return True

        return False
    except Exception as e:
        logger.warning(f"Error checking for 2FA requirement: {e}")
        return False


def login(page, mf_id, mf_pass):
    """
    MoneyForward MEにログイン / Login to MoneyForward ME

    Args:
        page: Playwright page object
        mf_id: メールアドレス（文字列またはSecureCredentialオブジェクト）
               Email address (string or SecureCredential object)
        mf_pass: パスワード（文字列またはSecureCredentialオブジェクト）
                 Password (string or SecureCredential object)

    セキュリティ注意事項:
    Security note:
        プレーンテキストのパスワードは、スタックトレースやログに表示される可能性があります。
        Plain text passwords may be visible in stack traces or logs.
        本番環境では、環境変数とSecureCredentialラッパーの使用を推奨します。
        For production use, recommend using environment variables and SecureCredential wrapper.

    Returns:
        tuple: (page, needs_2fa) - page object and boolean indicating if 2FA is required
    """
    # SecureCredentialオブジェクトから値を取得、または文字列をそのまま使用
    # Extract value from SecureCredential object, or use string as-is
    email = mf_id.get() if isinstance(mf_id, SecureCredential) else mf_id
    password = mf_pass.get() if isinstance(mf_pass, SecureCredential) else mf_pass

    try:
        # 既にログインしているかチェック（ログインフォームが存在しない場合はスキップ）
        # Check if already logged in (skip if login form doesn't exist)
        login_form = page.query_selector('#mfid_user\\[email\\]')
        if login_form is None:
            logger.info("Already logged in (using saved session)")
            return page, False

        # メールアドレスフィールドに入力
        # Fill in the email field
        page.fill('#mfid_user\\[email\\]', email)
        # 送信ボタンをクリック
        # Click the submit button
        page.click('#submitto')
        # ページ遷移を待機
        # Wait for navigation
        page.wait_for_timeout(2000)

        # パスワードフィールドに入力
        # Fill in the password field
        page.fill('#mfid_user\\[password\\]', password)
        # サインインボタンをクリック
        # Click the submit (sign in) button
        page.click('#submitto')

        # ログイン後のページ読み込みを待機（短いタイムアウト）
        # Wait for page load after login (short timeout)
        page.wait_for_load_state('networkidle', timeout=10000)

        # 2FA検証が必要かチェック
        # Check if 2FA verification is required
        needs_2fa = requires_2fa_verification(page)

        if needs_2fa:
            logger.warning("2FA/Email verification required - user interaction needed")
            return page, True

        logger.info("Login successful (no 2FA required)")
        return page, False

    except Exception as e:
        # 例外メッセージに機密情報が含まれないようにする
        # Ensure exception message doesn't contain sensitive information
        logger.error(f"Login error: {e}")
        # タイムアウトの場合は2FAが必要な可能性がある
        # If timeout, 2FA might be required
        if 'Timeout' in str(e):
            return page, True
        raise RuntimeError("Failed to login to MoneyForward ME") from e
    finally:
        # ローカル変数から機密情報をクリア（完全ではないが、最善の努力）
        # Clear sensitive data from local variables (not complete, but best effort)
        email = None
        password = None


def delete_all_cash_deposit(page):
    # ダイアログ（ポップアップ）を処理 - 表示されるダイアログを自動的に承認（OKボタンを押す）
    # Handle dialog (popup) - Automatically accept displayed dialogs (click OK button)
    page.once("dialog", lambda dialog: dialog.accept())

    # すべての削除ボタンをクリック（削除ボタンがなくなるまで繰り返す）
    # Click all delete buttons (repeat until no more delete buttons remain)
    while True:
        # 指定されたテーブル内のすべての削除ボタンを検索
        # Find all delete buttons within the specified table
        delete_buttons = page.query_selector_all(
            '.table.table-bordered.table-depo .btn-asset-action[data-method="delete"]')

        # 削除ボタンがなくなったらループを抜ける
        # If no more delete buttons, break the loop
        if not delete_buttons:
            break

        # 最初の削除ボタンをクリック
        # Click the first delete button
        delete_buttons[0].click()
        page.wait_for_timeout(3000)

        # ページ遷移を待機（オプション、ページによって異なる）
        # Wait for navigation (optional, depending on the page)
        page.wait_for_load_state('networkidle')


def get_mf_cash_deposit(page):
    df = get_data_from_mf_table(page, 'table-depo')
    # '種類・名称'列を'currency'列にリネーム
    # Rename '種類・名称' column to 'currency'
    if '種類・名称' in df.columns:
        df = df.rename(columns={'種類・名称': 'currency'})
    else:
        df['currency'] = None
    # '残高'列を'value_JPY'列にリネーム
    # Rename '残高' column to 'value_JPY'
    if '残高' in df.columns:
        df = df.rename(columns={'残高': 'value_JPY'})
        # 'value_JPY'列について、カンマと「円」を取り除き、intに変換
        # For 'value_JPY' column, remove commas and '円', convert to int
        df['value_JPY'] = df['value_JPY'].str.replace(",", "").str.replace("円", "").astype(int)
    else:
        df['value_JPY'] = None
    # 'asset_id'列を作成
    # Create 'asset_id' column
    df['asset_id'] = None
    # 行ごとにループし、webの表からasset_idを取得し代入
    # Loop through each row and get asset_id from web table
    for index, row in df.iterrows():
        df.loc[index, 'asset_id'] = get_asset_id_from_mf_table(page, 'table-depo', row['row_no_in_mf_table'])
    return df


def get_mf_equity(page):
    df = get_data_from_mf_table(page, 'table-eq')
    # '銘柄コード'列を'symbol'列にリネーム
    # Rename '銘柄コード' column to 'symbol'
    if '銘柄コード' in df.columns:
        df = df.rename(columns={'銘柄コード': 'symbol'})
        # '銘柄名'から'|'の前の部分を取得し、ポジション数量 (xx.x) を削除
        # Extract part before '|' from stock name, and remove position quantity (xx.x)
        df['symbol'] = df['銘柄名'].str.split('|').str[0].str.replace(r'\s*\([\d.]+\)\s*$', '', regex=True).str.strip()
    else:
        # dfに"symbol"列を追加
        # Add "symbol" column to df
        df['symbol'] = None
    # '評価額'列を'value_JPY'列にリネーム
    # Rename '評価額' column to 'value_JPY'
    if '評価額' in df.columns:
        df = df.rename(columns={'評価額': 'value_JPY'})
        # 'value_JPY'列について、カンマと「円」を取り除き、intに変換
        # For 'value_JPY' column, remove commas and '円', convert to int
        df['value_JPY'] = df['value_JPY'].str.replace(",", "").str.replace("円", "").astype(int)
    else:
        # dfに"value_JPY"列を追加
        # Add "value_JPY" column to df
        df['value_JPY'] = None
    # 'asset_id'列を作成し、webの表からasset_idを取得して代入
    # Create 'asset_id' column and get asset_id from web table
    df['asset_id'] = None
    for index, row in df.iterrows():
        df.loc[index, 'asset_id'] = get_asset_id_from_mf_table(page, 'table-eq', row['row_no_in_mf_table'])
    return df


def get_data_from_mf_table(page, table_type):
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    # テーブルのclass IDを設定
    # Set table class ID
    class_id = f'table table-bordered {table_type}'
    table = soup.find('table', class_=class_id)
    if table is None:
        # テーブルが存在しない場合は空のdfを返す
        # If table doesn't exist, return empty df
        df = pd.DataFrame()
        df['row_no_in_mf_table'] = None
        return df
    rows = table.find_all('tr')
    headers = [th.text.strip() for th in rows[0].find_all('th')]
    # テーブルの全データを取得
    # Get all data from table
    depo_data = []  # list
    for row in rows[1:]:
        values = [td.text.strip() for td in row.find_all('td')]
        depo_data.append(values)
    # Pandasのデータフレームに変換
    # Convert to Pandas DataFrame
    df = pd.DataFrame(depo_data, columns=headers)
    # 'row_no_in_mf_table'列を作成（index + 1）
    # Create 'row_no_in_mf_table' column (index + 1)
    df['row_no_in_mf_table'] = df.index + 1
    # 'row_no_in_mf_table'列を先頭に移動
    # Move 'row_no_in_mf_table' column to the front
    df = df.reindex(columns=['row_no_in_mf_table'] + list(df.columns[:-1]))
    df = df.drop(['変更', '削除'], axis=1)
    return df


def get_asset_id_from_mf_table(page, table_type, row_no_in_mf_table):
    # XPath injection prevention: validate table_type
    # XPath インジェクション防止: table_type を検証
    if table_type not in ['table-depo', 'table-eq']:
        raise ValueError(f"Invalid table type: {table_type}")

    # XPath injection prevention: validate row_no_in_mf_table is numeric
    # XPath インジェクション防止: row_no_in_mf_table が数値であることを検証
    try:
        row_num = int(row_no_in_mf_table)
        if row_num < 1:
            raise ValueError(f"Row number must be positive: {row_no_in_mf_table}")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid row number (must be numeric): {row_no_in_mf_table}") from e

    if table_type == 'table-depo':
        change_btn_column_no = 3
    elif table_type == 'table-eq':
        change_btn_column_no = 11

    element_xpath = '//*[@class="table table-bordered {}"]/tbody/tr[{}]/td[{}]/a'.format(table_type, row_num,
                                                                                         change_btn_column_no)
    element = page.query_selector(element_xpath)
    if element is None:
        raise RuntimeError(f"Element not found at row {row_no_in_mf_table} in {table_type}. Page structure may have changed.")
    # href属性から目的の文字列を取得し、これをasset_idとする
    # Get target string from href attribute and use it as asset_id
    href_attribute = element.get_attribute('href')
    if href_attribute is None:
        raise RuntimeError(f"Element at row {row_no_in_mf_table} in {table_type} has no href attribute.")
    asset_id = href_attribute.replace('#modal_asset', '')
    return asset_id


def modify_asset_in_mf(page, table_type, asset_id, asset_name, market_value, cost_amount=None, update_cost_basis=False):
    """
    Update an existing asset in MoneyForward.

    Args:
        page: Playwright page object
        table_type: Type of table ('table-depo' for cash, 'table-eq' for equity)
        asset_id: MoneyForward asset ID
        asset_name: Asset name to display
        market_value: Current market value (always updated)
        cost_amount: Purchase price/cost basis (optional)
        update_cost_basis: If True, update the purchase price field.
                          If False (default), preserve existing purchase price to maintain history.

    Note: To preserve historical data and allow MoneyForward to track gains/losses over time,
          we only update the purchase price when explicitly requested (e.g., first time or
          when user wants to update cost basis). Otherwise, we only update the current value.
    """
    # XPath injection prevention: validate asset_id
    # XPath インジェクション防止: asset_id を検証
    if not asset_id or not isinstance(asset_id, str):
        raise ValueError(f"Invalid asset_id: {asset_id}")
    # Validate asset_id contains only alphanumeric characters and underscores
    # asset_id が英数字とアンダースコアのみを含むことを検証
    if not asset_id.replace('_', '').replace('-', '').isalnum():
        raise ValueError(f"Invalid asset_id format (contains special characters): {asset_id}")

    # 指定されたテーブル内のすべての変更ボタンを検索
    # Find all modify buttons within the specified table
    modify_buttons = page.query_selector_all(
        f'.table.table-bordered.{table_type} .btn-asset-action[data-toggle="modal"]')
    # 変更ボタンの中からasset_idを含むボタンを探してクリック
    # Find the button containing asset_id among modify buttons and click it
    for modify_button in modify_buttons:
        href = modify_button.get_attribute('href')
        if asset_id in href:
            # クリックするとモーダルが表示される
            # Clicking displays the modal
            modify_button.click()
            break
    # 以下、モーダル内での操作
    # Following operations are within the modal
    modal_id = f'modal_asset{asset_id}'
    # ---資産の名称を変更---
    # ---Change asset name---
    asset_det_name_textbox_xpath = f'//div[@id="{modal_id}"]//input[@id="user_asset_det_name"]'
    asset_det_name_textbox = page.query_selector(asset_det_name_textbox_xpath)
    if asset_det_name_textbox is None:
        raise RuntimeError(f"Asset name input not found for asset_id {asset_id}. Modal may not have loaded properly.")
    # 20文字までしか入力できないため、最初の20文字を入力
    # Input first 20 characters (maximum allowed is 20 characters)
    asset_det_name_textbox.fill(str(asset_name)[:20])
    # ---現在の価値を変更---
    # ---Change current value---
    asset_det_value_textbox_xpath = f'//div[@id="{modal_id}"]//input[@id="user_asset_det_value"]'
    asset_det_value_textbox = page.query_selector(asset_det_value_textbox_xpath)
    if asset_det_value_textbox is None:
        raise RuntimeError(f"Asset value input not found for asset_id {asset_id}. Modal may not have loaded properly.")
    asset_det_value_textbox.fill(str(market_value)[:12])
    # ---購入価格を変更（履歴データ保持のため明示的にリクエストされた場合のみ）---
    # ---Change purchase price (only if explicitly requested to preserve historical data)---
    if update_cost_basis and cost_amount is not None:
        asset_det_entried_price_textbox_xpath = f'//div[@id="{modal_id}"]//input[@id="user_asset_det_entried_price"]'
        asset_det_entried_price_textbox = page.query_selector(asset_det_entried_price_textbox_xpath)
        if asset_det_entried_price_textbox is None:
            raise RuntimeError(f"Purchase price input not found for asset_id {asset_id}. Modal may not have loaded properly.")
        asset_det_entried_price_textbox.fill(str(cost_amount)[:12])
    # ---「この内容で登録」ボタンを押す---
    # ---Click the "Register with this content" button---
    commit_btn_xpath = f'//div[@id="{modal_id}"]//input[@name="commit"]'
    commit_btn = page.query_selector(commit_btn_xpath)
    if commit_btn is None:
        raise RuntimeError(f"Commit button not found for asset_id {asset_id}. Modal may not have loaded properly.")
    commit_btn.click()
    # ---モーダルが消えるまで待機---
    # ---Wait until the modal disappears---
    page.wait_for_timeout(3000)
    page.wait_for_load_state('networkidle')
    return True


def create_asset_in_mf(page, asset_type, asset_name, market_value, cost_amount, purchase_date=None):
    """
    Create a new asset in MoneyForward.

    Args:
        page: Playwright page object
        asset_type: MoneyForward asset type ID
        asset_name: Asset name
        market_value: Current market value
        cost_amount: Purchase price/cost basis
        purchase_date: Optional purchase date in 'YYYY-MM-DD' format (from IBKR openDateTime)
    """
    try:
        # デバッグ: 現在のURLとページタイトルをログ出力
        # Debug: Log current URL and page title
        logger.info(f"Current URL: {page.url}")
        logger.info(f"Page title: {page.title()}")

        add_button = page.get_by_role("button", name="手入力で資産を追加")
        if add_button is None:
            raise RuntimeError("Add asset button not found. Page structure may have changed.")
        add_button.click()

        asset_type_combo = page.get_by_role("combobox", name="資産の種類")
        if asset_type_combo is None:
            raise RuntimeError("Asset type combobox not found. Page structure may have changed.")
        asset_type_combo.select_option(str(asset_type))

        name_field = page.get_by_label("資産の名称")
        if name_field is None:
            raise RuntimeError("Asset name field not found. Page structure may have changed.")
        name_field.fill(str(asset_name)[:20])

        value_field = page.get_by_label("現在の価値")
        if value_field is None:
            raise RuntimeError("Current value field not found. Page structure may have changed.")
        value_field.fill(str(market_value)[:12])

        cost_field = page.get_by_label("購入価格")
        if cost_field is None:
            raise RuntimeError("Purchase price field not found. Page structure may have changed.")
        cost_field.fill(str(cost_amount)[:12])

        # 購入日フィールドが存在する場合は設定
        # Set purchase date field if it exists and date is provided
        if purchase_date:
            try:
                from datetime import date
                # MoneyForwardの購入日フィールドにアクセス (ID: user_asset_det_entried_at)
                # Access MoneyForward purchase date field (ID: user_asset_det_entried_at)
                date_field = page.query_selector('#user_asset_det_entried_at')
                if date_field:
                    # YYYY/MM/DD形式に変換 (MoneyForwardは通常この形式を期待)
                    # Convert to YYYY/MM/DD format (MoneyForward typically expects this format)
                    formatted_date = purchase_date.replace('-', '/')
                    today = date.today().isoformat().replace('-', '/')

                    # JavaScriptで値を直接設定し、必要なイベントをトリガー
                    # Set value directly with JavaScript and trigger necessary events
                    logger.info(f"Setting purchase date: {formatted_date}")
                    page.evaluate(f'''() => {{
                        const field = document.querySelector('#user_asset_det_entried_at');
                        if (field) {{
                            field.value = '{formatted_date}';
                            // 各種イベントをトリガーしてフォームに値の変更を通知
                            // Trigger events to notify form of value change
                            field.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            field.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            field.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                        }}
                    }}''')

                    # 日付値をコミットするため、Tabキーでフォーカスを移動
                    # Press Tab to move focus and commit the date value
                    # カレンダーウィジェットは明示的なフォーカス変更が必要
                    # Calendar widgets require explicit focus change to commit
                    date_field.press('Tab')
                    page.wait_for_timeout(500)  # 値のコミットを待つ / Wait for value to commit

                    # 値が正しく設定されたか確認
                    # Verify the value was set correctly
                    committed_value = date_field.input_value()
                    logger.info(f"Purchase date set to: {formatted_date}, committed value in field: '{committed_value}'")
                else:
                    logger.warning("Purchase date field (#user_asset_det_entried_at) not found in form")
            except Exception as e:
                # 購入日フィールドが存在しない場合はスキップ
                # Skip if purchase date field doesn't exist
                logger.warning(f"Error setting purchase date: {e}")

        submit_button = page.get_by_role("button", name="この内容で登録する")
        if submit_button is None:
            raise RuntimeError("Submit button not found. Page structure may have changed.")
        logger.info("Clicking submit button to create asset...")

        # JavaScriptクリックを使用してハングを回避
        # Use JavaScript click to avoid hanging
        try:
            submit_button.evaluate('el => el.click()')
            logger.info("Submit button clicked via JavaScript")
        except:
            # フォールバック: 通常のクリック
            # Fallback to normal click
            submit_button.click()
            logger.info("Submit button clicked via Playwright")

        page.wait_for_timeout(2000)
        try:
            page.wait_for_load_state('networkidle', timeout=10000)  # 10秒タイムアウト / 10 second timeout
            logger.info("Asset created successfully")
        except Exception as e:
            logger.warning(f"Page didn't reach networkidle state after submit, but continuing: {e}")
            # フォーム送信後にページが完全に落ち着かない場合でも続行
            # Continue even if page doesn't fully settle after form submission
        return True
    except Exception as e:
        raise RuntimeError(f"Failed to create asset in MoneyForward: {e}") from e


def delete_asset_in_mf(page, table_type, asset_id):
    # ダイアログ（ポップアップ）を処理 - 表示されるダイアログを自動的に承認（OKボタンを押す）
    # Handle dialog (popup) - Automatically accept displayed dialogs (click OK button)
    page.once("dialog", lambda dialog: dialog.accept())
    # 指定されたテーブル内のすべての削除ボタンを検索
    # Find all delete buttons within the specified table
    delete_buttons = page.query_selector_all(
        f'.table.table-bordered.{table_type} .btn-asset-action[data-method="delete"]')
    # 削除ボタンの中からasset_idを含むボタンを検索
    # Find the button containing asset_id among delete buttons
    for delete_button in delete_buttons:
        href = delete_button.get_attribute('href')
        if asset_id in href:
            delete_button.click()
            # 1秒待機
            # Wait for 1 sec
            page.wait_for_timeout(1000)
            # ページ遷移を待機（オプション、ページによって異なる）
            # Wait for navigation (optional, depending on the page)
            page.wait_for_load_state('networkidle')
            break
    return True


def reflect_to_mf_cash_deposit(page, ib_cash_report):
    """
    Sync cash deposits from IBKR to MoneyForward.

    CONSERVATIVE DELETION POLICY:
    - Assets are NEVER automatically deleted
    - If an asset exists in MF but not in IBKR report, we UPDATE it to 0 value
    - This preserves historical data while reflecting current state
    - Manual deletion via delete_all_cash_deposit() still available if needed
    """
    # ---pageから「預金・現金・暗号資産」の表を取得---
    # ---Get "Deposits, Cash, Cryptocurrency" table from page---
    mf_cash_deposit = get_mf_cash_deposit(page)

    # デバッグ: MoneyForwardにある通貨を表示
    # Debug: Show currencies in MoneyForward
    logger.info(f"MoneyForward cash deposits: {mf_cash_deposit['currency'].tolist() if not mf_cash_deposit.empty else 'None'}")
    logger.info(f"IBKR cash report: {ib_cash_report['currency'].tolist() if not ib_cash_report.empty else 'None'}")

    # 重複チェック: MoneyForwardに同じ通貨の複数のエントリがある場合は警告
    # Duplicate check: Warn if MoneyForward has multiple entries for the same currency
    if not mf_cash_deposit.empty:
        duplicates = mf_cash_deposit[mf_cash_deposit.duplicated(subset=['currency'], keep=False)]
        if not duplicates.empty:
            logger.warning(f"WARNING: MoneyForward has duplicate currency entries: {duplicates['currency'].tolist()}")
            logger.warning("Only the first occurrence will be updated. Please manually remove duplicates.")
            # 最初の出現のみを保持（重複を削除）
            # Keep only first occurrence (remove duplicates)
            mf_cash_deposit = mf_cash_deposit.drop_duplicates(subset=['currency'], keep='first')
            logger.info(f"After deduplication: {mf_cash_deposit['currency'].tolist()}")

    # ib_cash_reportとmf_cash_depositをマージ（キー: currency）
    # Merge ib_cash_report and mf_cash_deposit (key: currency)
    merged_df = pd.merge(mf_cash_deposit, ib_cash_report, on='currency', how='outer')

    # デバッグ: マージ結果を表示
    # Debug: Show merge results
    logger.info(f"Merged data:\n{merged_df[['currency', 'row_no_in_mf_table', 'value_JPY', 'endingCash_JPY']].to_string()}")
    # 非数値列のみ'NONE'で埋める / Fill only non-numeric columns with 'NONE'
    # 数値列は数値のままにする / Keep numeric columns as numeric
    string_columns = ['currency', 'row_no_in_mf_table', 'asset_id']
    for col in string_columns:
        if col in merged_df.columns:
            merged_df[col] = merged_df[col].fillna('NONE')
    # 数値列は0で埋める（後でNoneチェックで検出可能） / Fill numeric columns with NaN (detectable via None check)
    numeric_columns = ['value_JPY', 'endingCash_JPY']
    for col in numeric_columns:
        if col in merged_df.columns:
            merged_df[col] = pd.to_numeric(merged_df[col], errors='coerce')
    # 'Action'列を追加（初期値: 'NONE'）
    # Add 'Action' column (initial value: 'NONE')
    merged_df['Action'] = 'NONE'
    # 条件に基づいて'Action'列を更新
    # Update 'Action' column based on conditions
    merged_df.loc[(merged_df['row_no_in_mf_table'] != 'NONE') & (
            merged_df['value_JPY'] != merged_df['endingCash_JPY']), 'Action'] = 'MODIFY'
    # 保守的アプローチ: MFに資産があるがIBKRにない場合、削除せず0に更新
    # CONSERVATIVE: If asset in MF but not in IBKR, UPDATE to 0 instead of DELETE
    # 履歴データを保持しつつ現在の状態（残高なし）を反映
    # This preserves historical data while showing current state (no balance)
    merged_df.loc[
        (merged_df['row_no_in_mf_table'] != 'NONE') & (merged_df['endingCash_JPY'].isna()), 'Action'] = 'MODIFY_TO_ZERO'
    merged_df.loc[
        (merged_df['row_no_in_mf_table'] == 'NONE') & (merged_df['endingCash_JPY'].notna()), 'Action'] = 'ADD'
    # print(merged_df)
    # ---更新を実施---
    # ---Execute updates---
    df_to_modify = merged_df[(merged_df['Action'] == 'MODIFY')]
    for index, row in df_to_modify.iterrows():
        # 現在の価値のみ更新し、購入価格は履歴データ保持のため保存
        # Only update current value, preserve purchase price to maintain historical data
        modify_asset_in_mf(page, 'table-depo', row['asset_id'], row['currency'], int(row['endingCash_JPY']), update_cost_basis=False)
    # ---ゼロに更新（削除の代わり）- 履歴データを保持---
    # ---Update to zero (instead of delete) - Preserves historical data---
    df_to_zero = merged_df[(merged_df['Action'] == 'MODIFY_TO_ZERO')]
    for index, row in df_to_zero.iterrows():
        print(f"Setting {row['currency']} balance to 0 (not deleting to preserve history)")
        modify_asset_in_mf(page, 'table-depo', row['asset_id'], row['currency'], 0, update_cost_basis=False)
    # ---追加を実施---
    # ---Execute additions---
    df_to_add = merged_df[(merged_df['Action'] == 'ADD')]
    for index, row in df_to_add.iterrows():
        create_asset_in_mf(page, ASSET_TYPE_CASH_DEPOSIT, row['currency'], int(row['endingCash_JPY']), '')
    return True


def reflect_to_mf_equity(page, ib_open_position):
    """
    IBKRからMoneyForwardにポジション（株式、オプション、先物、CFD、ワラント、外国為替、投資信託、債券など）を同期します。
    Sync positions (stocks, options, futures, CFDs, warrants, forex, funds, bonds, etc.) from IBKR to MoneyForward.

    資産タイプマッピング:
    ASSET TYPE MAPPING:
        - 株式 (STK): 通貨別の適切な株式カテゴリにマッピング (14/15/16/55/17)
          Stocks: Mapped by currency to appropriate stock category (14/15/16/55/17)
        - オプション (OPT): "指数OP" (Index Options, ID: 23)にマッピング
          Options: Mapped to "指数OP" (Index Options, ID: 23)
        - 先物 (FUT): "指数先物" (22) または "商品先物" (26)にマッピング
          Futures: Mapped to "指数先物" (22) or "商品先物" (26)
        - CFD: "CFD" (24)にマッピング
          CFD: Mapped to "CFD" (24)
        - ワラント (WAR): 通貨ベースの株式分類にマッピング (14/15/16/55)
          Warrants: Mapped to currency-based stock classification (14/15/16/55)
        - 外国為替 (SWP/CASH): "店頭FX" (18)にマッピング
          Forex: Mapped to "店頭FX" (18)
        - 投資信託 (FND): "投資信託" (12) または "外国投資信託" (52)にマッピング
          Mutual Funds: Mapped to "投資信託" (12) or "外国投資信託" (52)
        - 債券 (BND): "国債" (7) / "社債" (8) / "外債" (9) / "その他債券" (11)にマッピング
          Bonds: Mapped to "国債" (7) / "社債" (8) / "外債" (9) / "その他債券" (11)
        - 商品間スプレッド (ICS): "商品先物" (26)にマッピング
          Inter-Commodity Spreads: Mapped to "商品先物" (26)
        - 完全なマッピングについてはASSET_SUBCLASS_MAPを参照
          See ASSET_SUBCLASS_MAP for complete mapping of all MoneyForward asset types

    保守的な削除ポリシー:
    CONSERVATIVE DELETION POLICY:
        - 資産は自動的に削除されることはありません
          Assets are NEVER automatically deleted
        - MFにポジションがあるがIBKRレポートにない場合、0に更新します
          If a position exists in MF but not in IBKR report, we UPDATE it to 0 value
        - クローズポジション、期限切れオプションなどの履歴データを保持します
          This preserves historical data for closed positions, expired options, etc.
        - MoneyForwardがポジション終了後も履歴パフォーマンスを表示できるようにします
          Allows MoneyForward to show historical performance even after position closure
        - 必要に応じて削除機能で手動削除が可能です
          Manual deletion via delete functions still available if needed
    """
    # ---pageから株式ポジションの表を取得---
    # ---Get equity positions table from page---
    mf_equity = get_mf_equity(page)
    # 両方のDataFrameに'symbol'列が存在するか確認
    # Check if 'symbol' column exists in both DataFrames
    if 'symbol' not in mf_equity.columns:
        print("Warning: 'symbol' column not found in MoneyForward equity data.")
        mf_equity['symbol'] = None
    if 'symbol' not in ib_open_position.columns:
        print("Warning: 'symbol' column not found in IB open positions data.")
        ib_open_position['symbol'] = None

    # デバッグ: シンボルの内容を表示
    # Debug: Show symbol contents
    logger.info(f"MoneyForward equity symbols: {mf_equity['symbol'].tolist() if not mf_equity.empty else 'None'}")
    logger.info(f"IBKR positions symbols: {ib_open_position['symbol'].tolist() if not ib_open_position.empty else 'None'}")

    # 重複チェック: MoneyForwardに同じシンボルの複数のエントリがある場合は警告
    # Duplicate check: Warn if MoneyForward has multiple entries for the same symbol
    if not mf_equity.empty and 'symbol' in mf_equity.columns:
        duplicates = mf_equity[mf_equity.duplicated(subset=['symbol'], keep=False)]
        if not duplicates.empty:
            logger.warning(f"WARNING: MoneyForward has duplicate symbol entries: {duplicates['symbol'].tolist()}")
            logger.warning("Only the first occurrence will be updated. Please manually remove duplicates.")
            # 最初の出現のみを保持（重複を削除）
            # Keep only first occurrence (remove duplicates)
            mf_equity = mf_equity.drop_duplicates(subset=['symbol'], keep='first')

    # ib_open_positionとmf_equityをマージ（キー: symbol）
    # Merge ib_open_position and mf_equity (key: symbol)
    merged_df = pd.merge(mf_equity, ib_open_position, on='symbol', how='outer')

    # デバッグ: マージ結果を表示
    # Debug: Show merge results
    # 存在する列のみ表示 / Only show columns that exist
    display_cols = ['symbol', 'row_no_in_mf_table']
    if 'value_JPY' in merged_df.columns:
        display_cols.append('value_JPY')
    if 'positionValue_JPY' in merged_df.columns:
        display_cols.append('positionValue_JPY')
    logger.info(f"Merged equity data:\n{merged_df[display_cols].to_string()}")
    # 非数値列のみ'NONE'で埋める / Fill only non-numeric columns with 'NONE'
    # 数値列は数値のままにする / Keep numeric columns as numeric
    string_columns = ['symbol', 'row_no_in_mf_table', 'asset_id', '銘柄名', 'currency', 'assetCategory',
                      'subCategory', 'description', 'strike', 'expiry', 'putCall']
    for col in string_columns:
        if col in merged_df.columns:
            merged_df[col] = merged_df[col].fillna('NONE')
    # 数値列は数値型を維持 / Keep numeric columns as numeric type
    # IBKRポジションがない場合、positionValue_JPY列を追加（NaN値）
    # Add positionValue_JPY column with NaN if no IBKR positions
    if 'positionValue_JPY' not in merged_df.columns:
        import numpy as np
        merged_df['positionValue_JPY'] = np.nan

    numeric_columns = ['value_JPY', 'positionValue_JPY', 'costBasisMoney_JPY', 'position']
    for col in numeric_columns:
        if col in merged_df.columns:
            merged_df[col] = pd.to_numeric(merged_df[col], errors='coerce')
    # 'Action'列を追加（初期値: 'NONE'）
    # Add 'Action' column (initial value: 'NONE')
    merged_df['Action'] = 'NONE'
    # 条件に基づいて'Action'列を更新
    # Update 'Action' column based on conditions
    if 'positionValue_JPY' in merged_df.columns:
        merged_df.loc[(merged_df['row_no_in_mf_table'] != 'NONE') & (
                merged_df['value_JPY'] != merged_df['positionValue_JPY']), 'Action'] = 'MODIFY'
    # MFにポジションがあるがIBKRにない場合、削除
    # If position exists in MF but not in IBKR, DELETE it
    # クローズポジション、期限切れオプション、売却済み保有株に対応
    # Handles closed positions, expired options, sold holdings
    merged_df.loc[
        (merged_df['row_no_in_mf_table'] != 'NONE') & (merged_df['positionValue_JPY'].isna()), 'Action'] = 'DELETE'
    merged_df.loc[
        (merged_df['row_no_in_mf_table'] == 'NONE') & (merged_df['positionValue_JPY'].notna()), 'Action'] = 'ADD'
    # print(merged_df)
    # ---更新を実施---
    # ---Execute updates---
    df_to_modify = merged_df[(merged_df['Action'] == 'MODIFY')]
    for index, row in df_to_modify.iterrows():
        # 改善されたフォーマットを使用: 株式 "AAPL (100)", オプション "AAPL Jan24 $150-C (10)"
        # Use improved formatting: stocks "AAPL (100)", options "AAPL Jan24 $150-C (10)"
        asset_name_to_input = format_asset_name(row)
        # 現在の価値(positionValue_JPY)のみ更新、コストベースは履歴データ保持のため保存
        # Only update current value (positionValue_JPY), preserve cost basis to maintain historical data
        # MoneyForwardが損益を正確に追跡できるようにする
        # This allows MoneyForward to track gains/losses over time correctly
        modify_asset_in_mf(page, 'table-eq', row['asset_id'], asset_name_to_input, int(row['positionValue_JPY']),
                           update_cost_basis=False)
    # ---削除を実施 - IBKRに存在しないポジションを削除---
    # ---Execute deletions - Remove positions that don't exist in IBKR---
    df_to_delete = merged_df[(merged_df['Action'] == 'DELETE')]
    for index, row in df_to_delete.iterrows():
        # MoneyForwardから元の資産名を取得
        # Get original asset name from MoneyForward
        original_name = str(row['銘柄名']) if '銘柄名' in row and row['銘柄名'] != 'NONE' else row['symbol']
        logger.info(f"Deleting closed position: {original_name}")
        delete_asset_in_mf(page, 'table-eq', row['asset_id'])
    # ---追加を実施---
    # ---Execute additions---
    df_to_add = merged_df[(merged_df['Action'] == 'ADD')]
    for index, row in df_to_add.iterrows():
        # 改善されたフォーマットを使用: 株式 "AAPL (100)", オプション "AAPL Jan24 $150-C (10)", 先物 "ES Mar24 (5)"など
        # Use improved formatting: stocks "AAPL (100)", options "AAPL Jan24 $150-C (10)", futures "ES Mar24 (5)", etc.
        asset_name_to_input = format_asset_name(row)
        # 通貨、資産カテゴリ（STK、OPT、FUT、CFD、WAR、SWP、FND、BND、ICSなど）、サブカテゴリに基づいて資産タイプを決定
        # Determine asset type based on currency, asset category (STK, OPT, FUT, CFD, WAR, SWP, FND, BND, ICS, etc.), and subcategory
        asset_category = str(row.get('assetCategory', 'STK'))
        subcategory = str(row.get('subCategory', None)) if 'subCategory' in row and row['subCategory'] != 'NONE' else None
        asset_type_to_input = get_asset_type_for_currency(row['currency'], asset_category, subcategory)

        # 購入日を取得してフォーマット (openDateTime: "2024-01-15;12:30:00" -> "2024-01-15")
        # Get and format purchase date (openDateTime: "2024-01-15;12:30:00" -> "2024-01-15")
        purchase_date = None
        if 'openDateTime' in row and row['openDateTime'] != 'NONE' and str(row['openDateTime']).strip():
            try:
                # IBKRのopenDateTimeは "YYYY-MM-DD;HH:MM:SS" 形式
                # IBKR openDateTime is in "YYYY-MM-DD;HH:MM:SS" format
                open_datetime_str = str(row['openDateTime'])
                purchase_date = open_datetime_str.split(';')[0]  # 日付部分のみ取得 / Get date part only
                logger.info(f"Using IBKR openDateTime for {row['symbol']}: {purchase_date}")
            except Exception as e:
                logger.warning(f"Failed to parse openDateTime '{row.get('openDateTime')}': {e}")

        # openDateTimeが利用できない場合は、現在の日付にフォールバック
        # Fallback to current date if openDateTime is not available
        if not purchase_date:
            from datetime import date
            purchase_date = date.today().isoformat()  # YYYY-MM-DD形式 / YYYY-MM-DD format
            logger.info(f"openDateTime not available for {row['symbol']}, using current date: {purchase_date}")

        create_asset_in_mf(page, asset_type_to_input, asset_name_to_input, int(row['positionValue_JPY']),
                           int(row['costBasisMoney_JPY']), purchase_date)
    return True
