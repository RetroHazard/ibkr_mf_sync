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


def get_underlying_symbol(row):
    """
    IBKRデータからクリーンな原資産ティッカーを抽出します。
    Extract the clean underlying ticker symbol from IBKR data.

    株式 (STK) の場合、シンボルはすでに原資産ティッカー (例: "QSI")。
    For stocks (STK), the symbol is already the underlying ticker (e.g., "QSI").

    オプション (OPT) の場合、シンボルはOCCコード (例: "PNC   260213P00227500")
    で、最初の6文字がパディングされた原資産ティッカーです。
    For options (OPT), the symbol is an OCC code (e.g., "PNC   260213P00227500")
    where the first 6 chars are the padded underlying ticker.
    """
    symbol = str(row.get('symbol', 'UNKNOWN'))
    asset_category = str(row.get('assetCategory', 'STK'))

    if asset_category == 'OPT' and len(symbol) > 6:
        # OCC形式: 6文字パディング原資産 + 日付 + タイプ + 行使価格
        # OCC format: 6-char padded underlying + date + type + strike
        underlying = symbol[:6].strip()
        return underlying if underlying else symbol

    return symbol


def get_position_key(row):
    """
    ポジションのユニークなマージキーを生成します（ポジション数量に依存しない）。
    Generate a unique merge key for a position, independent of position count.

    キー形式 / Key formats:
        STK: "QSI"
        OPT: "PNC260213 P227.5" (原資産+YYMMDD+スペース+P/C+行使価格)
        FUT: "ES 250321"
        BND: "US10Y 2.5%"
        その他: 原資産シンボル / Others: underlying symbol
    """
    underlying = get_underlying_symbol(row)
    asset_category = str(row.get('assetCategory', 'STK'))

    if asset_category == 'OPT':
        strike = str(row.get('strike', ''))
        expiry = str(row.get('expiry', ''))
        put_call = str(row.get('putCall', ''))

        # 有効期限フォーマット: "20260213" -> "260213"
        # Format expiry: "20260213" -> "260213"
        if expiry and expiry != 'NONE' and len(expiry) == 8:
            expiry_formatted = expiry[2:]  # YYYYMMDD -> YYMMDD
        else:
            expiry_formatted = expiry if expiry != 'NONE' else ''

        # 行使価格フォーマット: "227.5" -> "227.5", "5.0" -> "5"
        # Format strike: "227.5" -> "227.5", "5.0" -> "5"
        strike_formatted = ''
        try:
            if strike and strike != 'NONE':
                strike_num = float(strike)
                if strike_num == int(strike_num):
                    strike_formatted = str(int(strike_num))
                else:
                    strike_formatted = f"{strike_num:g}"
            else:
                strike_formatted = ''
        except (ValueError, TypeError):
            strike_formatted = strike if strike != 'NONE' else ''

        pc_indicator = put_call[0].upper() if put_call and put_call != 'NONE' else ''

        # キー形式: "PNC260213 P227.5"
        # Key format: "PNC260213 P227.5"
        key = f"{underlying}{expiry_formatted} {pc_indicator}{strike_formatted}"
        return key[:20]

    elif asset_category == 'FUT':
        expiry = str(row.get('expiry', ''))
        if expiry and expiry != 'NONE' and len(expiry) == 8:
            expiry_formatted = expiry[2:]  # YYYYMMDD -> YYMMDD
        else:
            expiry_formatted = ''

        if expiry_formatted:
            key = f"{underlying} {expiry_formatted}"
        else:
            key = underlying
        return key[:20]

    elif asset_category == 'BND':
        import re
        description = str(row.get('description', ''))
        coupon_match = re.search(r'(\d+\.?\d*)\s*%', description)
        coupon = f" {coupon_match.group(1)}%" if coupon_match else ''
        key = f"{underlying}{coupon}"
        return key[:20]

    else:
        return underlying[:20]


def format_asset_name(row):
    """
    IBKRの資産データに基づいてMoneyForward表示用の資産名をフォーマットします。
    Format asset name for display in MoneyForward based on IBKR asset data.

    get_position_key()でアイデンティティ部分を生成し、20文字以内に収まる場合はポジション数を付加します。
    Uses get_position_key() for the identity part, appends position count if it fits within 20 chars.

    フォーマット例 / Formatting examples:
        オプション (OPT): "PNC260213 P227.5-1"  ({symbol}{YYMMDD} {PC}{strike}-{pos})
        株式 (STK): "QSI (500)"
        先物 (FUT): "ES 250321 (5)"
        外国為替 (SWP/CASH): "EUR.USD (100k)"

    引数 / Args:
        row: IBKRからの資産データを含むDataFrame行
             DataFrame row containing asset data from IBKR

    戻り値 / Returns:
        資産名（MoneyForward制約により最大20文字）
        Asset name (max 20 chars for MoneyForward)
    """
    position = str(row.get('position', '0')) if row.get('position', 'NONE') != 'NONE' else '0'
    asset_category = str(row.get('assetCategory', 'STK'))
    key = get_position_key(row)

    # オプション: ポジションキーをそのまま名称として使用（ポジション数なし）
    # Options: use position key directly as name (no position count suffix)
    # これにより名称とmerge_keyが同一になり、逆変換の必要がなくなる
    # This makes the name identical to merge_key, eliminating reverse-parsing
    if asset_category == 'OPT':
        return key

    # 外国為替: k（千単位）でポジション数をフォーマット
    # Forex: format position in k (thousands)
    if asset_category in ('SWP', 'CASH'):
        try:
            pos_num = float(position)
            if abs(pos_num) >= 1000:
                pos_formatted = f"{int(pos_num / 1000)}k"
            else:
                pos_formatted = position
        except (ValueError, TypeError):
            pos_formatted = position
        suffix = f" ({pos_formatted})"
    else:
        suffix = f" ({position})"

    # その他の資産タイプ: 括弧付きポジション数 "{key} ({pos})"
    # Other asset types: parenthesized position count "{key} ({pos})"
    full_name = f"{key}{suffix}"
    if len(full_name) <= 20:
        return full_name
    return key[:20]


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


def _read_mf_table_section(page, table_type):
    """
    Read one MF table section, extract merge_key and value_JPY, return DataFrame.
    Adds 'source_table' column so callers know which table each row came from.
    """
    df = get_data_from_mf_table(page, table_type)
    if df.empty:
        return df

    # 銘柄名からマージキーを抽出（ポジションサフィックスを除去）
    # Extract merge key from name (strip position suffix)
    if '銘柄名' in df.columns:
        logger.info(f"Raw 銘柄名 from MF {table_type}: {df['銘柄名'].tolist()}")
        df['merge_key'] = df['銘柄名'].str.split('|').str[0].str.replace(
            r'(?:\s*\(-?[\d.]+k?\)|-[\d.]+)\s*$', '', regex=True).str.strip()
        logger.info(f"Computed merge_keys from {table_type}: {df['merge_key'].tolist()}")
    else:
        df['merge_key'] = None

    # 評価額 or 現在の価値 を value_JPY にリネーム
    # Rename value column to value_JPY (try multiple possible column names)
    for col_name in ['評価額', '現在の価値']:
        if col_name in df.columns:
            df = df.rename(columns={col_name: 'value_JPY'})
            df['value_JPY'] = df['value_JPY'].str.replace(",", "").str.replace("円", "").astype(int)
            break
    else:
        df['value_JPY'] = None

    # どのテーブルから来たかを記録（modify/delete時に使用）
    # Track source table for use in modify/delete operations
    df['source_table'] = table_type

    # asset_idを取得
    # Get asset_id for each row
    df['asset_id'] = None
    for index, row in df.iterrows():
        df.loc[index, 'asset_id'] = get_asset_id_from_mf_table(page, table_type, row['row_no_in_mf_table'])

    return df


def get_mf_equity(page):
    """
    株式(table-eq)と先物OP(table-drv)の両テーブルからポジションを読み取り結合します。
    Read positions from both equity (table-eq) and derivatives (table-drv) tables and combine.
    """
    df_eq = _read_mf_table_section(page, 'table-eq')
    df_drv = _read_mf_table_section(page, 'table-drv')

    parts = [df for df in [df_eq, df_drv] if not df.empty]
    if not parts:
        empty = pd.DataFrame(columns=['row_no_in_mf_table', 'merge_key', 'value_JPY', 'asset_id', 'source_table'])
        return empty

    return pd.concat(parts, ignore_index=True)


def log_all_mf_tables(page):
    """Log all table types found on the MF page (diagnostic helper)."""
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table', class_=lambda c: c and 'table-bordered' in c)
    table_classes = [' '.join(t.get('class', [])) for t in tables]
    logger.info(f"All table-bordered tables on MF page: {table_classes}")


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
    df = df.drop([c for c in ['変更', '削除'] if c in df.columns], axis=1)
    return df


def get_asset_id_from_mf_table(page, table_type, row_no_in_mf_table):
    # XPath injection prevention: validate table_type
    # XPath インジェクション防止: table_type を検証
    if table_type not in ['table-depo', 'table-eq', 'table-drv']:
        raise ValueError(f"Invalid table type: {table_type}")

    # XPath injection prevention: validate row_no_in_mf_table is numeric
    # XPath インジェクション防止: row_no_in_mf_table が数値であることを検証
    try:
        row_num = int(row_no_in_mf_table)
        if row_num < 1:
            raise ValueError(f"Row number must be positive: {row_no_in_mf_table}")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid row number (must be numeric): {row_no_in_mf_table}") from e

    # モーダルリンクを行内で検索（列番号に依存しない汎用方式）
    # Search for modal link within the row (generic approach not dependent on column number)
    element_xpath = '//*[@class="table table-bordered {}"]/tbody/tr[{}]//a[contains(@href, "#modal_asset")]'.format(
        table_type, row_num)
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
        cost_amount: Purchase price/cost basis (optional, only updated if update_cost_basis=True)
        update_cost_basis: If True, update the purchase price/cost basis field.
                          If False (default), preserve existing purchase price to maintain history.

    Note: This function NEVER modifies the purchase date - that field is only set when creating
          new assets. The purchase date always remains the original date from the first creation.
          Cost basis SHOULD be updated (update_cost_basis=True) for equities when positions change
          through additional buys/sells, as IBKR provides the current average cost basis.
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
    deleted = False
    for delete_button in delete_buttons:
        href = delete_button.get_attribute('href')
        if asset_id in href:
            delete_button.click()
            page.wait_for_timeout(1000)
            page.wait_for_load_state('networkidle')
            deleted = True
            break
    if not deleted:
        logger.warning(f"DELETE FAILED: no delete button found for asset_id={asset_id} in {table_type}. "
                       f"Found {len(delete_buttons)} buttons with hrefs: "
                       f"{[b.get_attribute('href') for b in delete_buttons[:3]]}")
    return deleted


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

    削除ポリシー:
    DELETION POLICY:
        - MFにポジションがあるがIBKRレポートにない場合、自動的に削除します
          If a position exists in MF but not in IBKR report, automatically DELETE it
        - クローズポジション、期限切れオプション、売却済み保有株などに対応
          Handles closed positions, expired options, sold holdings, etc.
        - MoneyForwardのポートフォリオをIBKRの現在の状態と同期します
          Keeps MoneyForward portfolio in sync with current IBKR state
        - 履歴データが必要な場合は、MoneyForwardのアーカイブ機能を使用してください
          Use MoneyForward's archive features if historical data is needed
    """
    # ---pageから株式ポジションの表を取得---
    # ---Get equity positions table from page---
    mf_equity = get_mf_equity(page)

    # merge_key列の確認 / Verify merge_key columns exist
    if 'merge_key' not in mf_equity.columns:
        logger.warning("'merge_key' column not found in MoneyForward equity data.")
        mf_equity['merge_key'] = None

    # ---IBKRデータのmerge_keyを計算---
    # ---Compute merge_key for IBKR data---
    ib_open_position = ib_open_position.copy()
    ib_open_position['merge_key'] = ib_open_position.apply(get_position_key, axis=1)

    # ---IBKRのロットレベル重複をmerge_keyで集約---
    # ---Aggregate IBKR lot-level duplicates by merge_key---
    if ib_open_position['merge_key'].duplicated().any():
        logger.info(f"Aggregating lot-level IBKR positions: "
                    f"{ib_open_position[ib_open_position['merge_key'].duplicated(keep=False)]['merge_key'].tolist()}")
        sum_cols = ['position', 'positionValue', 'costBasisMoney', 'positionValue_JPY', 'costBasisMoney_JPY']
        agg_dict = {}
        for col in ib_open_position.columns:
            if col == 'merge_key':
                continue
            agg_dict[col] = 'sum' if col in sum_cols and col in ib_open_position.columns else 'first'
        ib_open_position = ib_open_position.groupby('merge_key', as_index=False).agg(agg_dict)

    # デバッグ: マージキーの内容を表示
    # Debug: Show merge key contents
    logger.info(f"MoneyForward equity merge_keys: {mf_equity['merge_key'].tolist() if not mf_equity.empty else 'None'}")
    logger.info(f"IBKR positions merge_keys: {ib_open_position['merge_key'].tolist() if not ib_open_position.empty else 'None'}")

    # 重複チェック: MoneyForwardに同じmerge_keyの複数のエントリがある場合は警告
    # Duplicate check: Warn if MoneyForward has multiple entries for the same merge_key
    if not mf_equity.empty and 'merge_key' in mf_equity.columns:
        duplicates = mf_equity[mf_equity.duplicated(subset=['merge_key'], keep=False)]
        if not duplicates.empty:
            logger.warning(f"WARNING: MoneyForward has duplicate entries: {duplicates['merge_key'].tolist()}")
            logger.warning("Only the first occurrence will be updated. Please manually remove duplicates.")
            mf_equity = mf_equity.drop_duplicates(subset=['merge_key'], keep='first')

    # merge_keyでマージ / Merge on merge_key
    merged_df = pd.merge(mf_equity, ib_open_position, on='merge_key', how='outer')

    # デバッグ: マージ結果を表示 / Debug: Show merge results
    display_cols = ['merge_key', 'row_no_in_mf_table']
    if 'value_JPY' in merged_df.columns:
        display_cols.append('value_JPY')
    if 'positionValue_JPY' in merged_df.columns:
        display_cols.append('positionValue_JPY')
    logger.info(f"Merged equity data:\n{merged_df[display_cols].to_string()}")

    # 非数値列のみ'NONE'で埋める / Fill only non-numeric columns with 'NONE'
    string_columns = ['merge_key', 'symbol', 'row_no_in_mf_table', 'asset_id', 'source_table', '銘柄名', 'currency',
                      'assetCategory', 'subCategory', 'description', 'strike', 'expiry', 'putCall']
    for col in string_columns:
        if col in merged_df.columns:
            merged_df[col] = merged_df[col].fillna('NONE')

    # 数値列は数値型を維持 / Keep numeric columns as numeric type
    if 'positionValue_JPY' not in merged_df.columns:
        import numpy as np
        merged_df['positionValue_JPY'] = np.nan

    numeric_columns = ['value_JPY', 'positionValue_JPY', 'costBasisMoney_JPY', 'position']
    for col in numeric_columns:
        if col in merged_df.columns:
            merged_df[col] = pd.to_numeric(merged_df[col], errors='coerce')

    # 'Action'列を追加 / Add 'Action' column
    merged_df['Action'] = 'NONE'
    if 'positionValue_JPY' in merged_df.columns:
        merged_df.loc[(merged_df['row_no_in_mf_table'] != 'NONE') & (
                merged_df['value_JPY'] != merged_df['positionValue_JPY']), 'Action'] = 'MODIFY'
    # MFにポジションがあるがIBKRにない場合、削除
    # If position exists in MF but not in IBKR, DELETE it
    merged_df.loc[
        (merged_df['row_no_in_mf_table'] != 'NONE') & (merged_df['positionValue_JPY'].isna()), 'Action'] = 'DELETE'
    merged_df.loc[
        (merged_df['row_no_in_mf_table'] == 'NONE') & (merged_df['positionValue_JPY'].notna()), 'Action'] = 'ADD'

    logger.info(f"Actions:\n{merged_df[['merge_key', 'row_no_in_mf_table', 'Action']].to_string()}")

    # ---更新を実施---
    # ---Execute updates---
    df_to_modify = merged_df[(merged_df['Action'] == 'MODIFY')]
    for index, row in df_to_modify.iterrows():
        asset_name_to_input = format_asset_name(row)
        table_type = str(row.get('source_table', 'table-eq'))
        if table_type == 'NONE':
            table_type = 'table-eq'
        modify_asset_in_mf(page, table_type, row['asset_id'], asset_name_to_input, int(row['positionValue_JPY']),
                           cost_amount=int(row['costBasisMoney_JPY']), update_cost_basis=True)

    # ---削除を実施 - IBKRに存在しないポジションを削除---
    # ---Execute deletions - Remove positions that don't exist in IBKR---
    df_to_delete = merged_df[(merged_df['Action'] == 'DELETE')]
    for index, row in df_to_delete.iterrows():
        original_name = str(row['銘柄名']) if '銘柄名' in row and row['銘柄名'] != 'NONE' else row['merge_key']
        table_type = str(row.get('source_table', 'table-eq'))
        if table_type == 'NONE':
            table_type = 'table-eq'
        logger.info(f"Deleting closed position: {original_name} from {table_type}")
        delete_asset_in_mf(page, table_type, row['asset_id'])

    # ---追加を実施---
    # ---Execute additions---
    df_to_add = merged_df[(merged_df['Action'] == 'ADD')]
    for index, row in df_to_add.iterrows():
        asset_name_to_input = format_asset_name(row)
        asset_category = str(row.get('assetCategory', 'STK'))
        subcategory = str(row.get('subCategory', None)) if 'subCategory' in row and row['subCategory'] != 'NONE' else None
        asset_type_to_input = get_asset_type_for_currency(row['currency'], asset_category, subcategory)

        # 購入日を取得してフォーマット (openDateTime: "2024-01-15;12:30:00" -> "2024-01-15")
        # Get and format purchase date (openDateTime: "2024-01-15;12:30:00" -> "2024-01-15")
        purchase_date = None
        if 'openDateTime' in row and row['openDateTime'] != 'NONE' and str(row['openDateTime']).strip():
            try:
                open_datetime_str = str(row['openDateTime'])
                purchase_date = open_datetime_str.split(';')[0]
                logger.info(f"Using IBKR openDateTime for {row['merge_key']}: {purchase_date}")
            except Exception as e:
                logger.warning(f"Failed to parse openDateTime '{row.get('openDateTime')}': {e}")

        if not purchase_date:
            from datetime import date
            purchase_date = date.today().isoformat()
            logger.info(f"openDateTime not available for {row['merge_key']}, using current date: {purchase_date}")

        create_asset_in_mf(page, asset_type_to_input, asset_name_to_input, int(row['positionValue_JPY']),
                           int(row['costBasisMoney_JPY']), purchase_date)
    return True
