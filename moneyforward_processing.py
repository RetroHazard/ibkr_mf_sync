import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from asset_types import (
    ASSET_SUBCLASS_MAP,
    get_asset_type_for_currency,
    ASSET_TYPE_CASH_DEPOSIT
)


def format_asset_name(row):
    """
    Format asset name for display in MoneyForward.

    For stocks: "SYMBOL (qty)"
    For options: "SYMBOL Jan24 $150C (qty)" or "SYMBOL Jan24 $150P (qty)"

    Args:
        row: DataFrame row containing asset data from IBKR

    Returns:
        Human-friendly formatted asset name (max 20 chars for MoneyForward)
    """
    symbol = str(row['symbol']) if 'symbol' in row and row['symbol'] != 'NONE' else 'UNKNOWN'
    position = str(row['position']) if 'position' in row and row['position'] != 'NONE' else '0'
    asset_category = str(row.get('assetCategory', 'STK'))

    if asset_category == 'OPT':
        # Option format: "AAPL Jan24 $150C (10)"
        strike = str(row.get('strike', ''))
        expiry = str(row.get('expiry', ''))
        put_call = str(row.get('putCall', ''))

        # Format expiry date: "20240119" -> "Jan24"
        try:
            if expiry and expiry != 'NONE' and len(expiry) == 8:
                expiry_date = datetime.strptime(expiry, '%Y%m%d')
                month_abbr = expiry_date.strftime('%b')  # Jan, Feb, Mar, etc.
                year_short = expiry_date.strftime('%y')  # 24, 25, etc.
                expiry_formatted = f"{month_abbr}{year_short}"
            else:
                expiry_formatted = expiry[:6] if expiry != 'NONE' else ''
        except:
            expiry_formatted = expiry[:6] if expiry != 'NONE' else ''

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
        except:
            strike_formatted = f"${strike}" if strike != 'NONE' else ''

        # Put/Call indicator: C or P
        pc_indicator = put_call[0].upper() if put_call and put_call != 'NONE' else ''

        # Build option name: "AAPL Jan24 $150C (10)"
        option_name = f"{symbol} {expiry_formatted} {strike_formatted}{pc_indicator} ({position})"

        # Ensure within 20 char limit (MoneyForward constraint)
        if len(option_name) > 20:
            # Truncate symbol if needed: "AAPL" -> "APL"
            symbol_short = symbol[:3] if len(symbol) > 4 else symbol
            option_name = f"{symbol_short} {expiry_formatted} {strike_formatted}{pc_indicator} ({position})"

        return option_name[:20]  # Hard limit at 20 chars
    else:
        # Stock format: "AAPL (100)"
        stock_name = f"{symbol} ({position})"
        return stock_name[:20]


def login(page, mf_id, mf_pass):
    # Fill in the email field
    page.fill('#mfid_user\\[email\\]', mf_id)
    # Click the submit button
    page.click('#submitto')
    # Wait for navigation (optional, depending on the page)
    # page.wait_for_load_state('networkidle')
    # Fill in the password field
    page.fill('#mfid_user\\[password\\]', mf_pass)
    # Click the submit (sign in) button
    page.click('#submitto')
    # retuen the page instance
    return page


def delete_all_cash_deposit(page):
    # Handle dialog (popup)　表示されるダイアログを自動的に承認（OKボタンを押す）する。
    page.once("dialog", lambda dialog: dialog.accept())

    # Click all delete buttons(削除ボタンがなくなるまで削除ボタンをクリックし続ける)
    while True:
        # Find all delete buttons within the specified table
        delete_buttons = page.query_selector_all(
            '.table.table-bordered.table-depo .btn-asset-action[data-method="delete"]')

        # If no more delete buttons, break the loop
        if not delete_buttons:
            break

        # Click the first delete button
        delete_buttons[0].click()
        page.wait_for_timeout(3000)

        # Wait for navigation (optional, depending on the page)
        page.wait_for_load_state('networkidle')


def get_mf_cash_deposit(page):
    df = get_data_from_mf_table(page, 'table-depo')
    # '種類・名称'列を'currency'列にリネーム
    if '種類・名称' in df.columns:
        df = df.rename(columns={'種類・名称': 'currency'})
    else:
        df['currency'] = None
    # '残高'列を'value'列にリネーム
    if '残高' in df.columns:
        df = df.rename(columns={'残高': 'value_JPY'})
        # 'value'列について、カンマと「円」を取り除き、intにする。
        df['value_JPY'] = df['value_JPY'].str.replace(",", "").str.replace("円", "").astype(int)
    else:
        df['value_JPY'] = None
    # 'asset_id'列を作成
    df['asset_id'] = None
    # 行ごとにループし、webの表からasset_idを取得し代入する
    for index, row in df.iterrows():
        df.loc[index, 'asset_id'] = get_asset_id_from_mf_table(page, 'table-depo', row['row_no_in_mf_table'])
    return df


def get_mf_equity(page):
    df = get_data_from_mf_table(page, 'table-eq')
    # '銘柄コード'列を'symbol'列にリネーム
    if '銘柄コード' in df.columns:
        df = df.rename(columns={'銘柄コード': 'symbol'})
        df['symbol'] = df['銘柄名'].str.split('|').str[0]
    else:
        # dfに"symbol"列を追加する
        df['symbol'] = None
    # '評価額'列を'value'列にリネーム
    if '評価額' in df.columns:
        df = df.rename(columns={'評価額': 'value_JPY'})
        # 'value'列について、カンマと「円」を取り除き、intにする。
        df['value_JPY'] = df['value_JPY'].str.replace(",", "").str.replace("円", "").astype(int)
    else:
        # dfに"value_JPY"列を追加する
        df['value_JPY'] = None
    # 'asset_id'列を作成, webの表からasset_idを取得し代入する
    df['asset_id'] = None
    for index, row in df.iterrows():
        df.loc[index, 'asset_id'] = get_asset_id_from_mf_table(page, 'table-eq', row['row_no_in_mf_table'])
    return df


def get_data_from_mf_table(page, table_type):
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    # tableのclass IDを設定
    class_id = f'table table-bordered {table_type}'
    table = soup.find('table', class_=class_id)
    if table is None:
        # テーブルが存在しない場合は空のdfを返す
        df = pd.DataFrame()
        df['row_no_in_mf_table'] = None
        return df
    rows = table.find_all('tr')
    headers = [th.text.strip() for th in rows[0].find_all('th')]
    # テーブルの全データを取得
    depo_data = []  # list
    for row in rows[1:]:
        values = [td.text.strip() for td in row.find_all('td')]
        depo_data.append(values)
    # Pandasのデータフレームに変換
    df = pd.DataFrame(depo_data, columns=headers)
    # 'row_no_in_mf_table'列を作成(index + 1)
    df['row_no_in_mf_table'] = df.index + 1
    # 'row_no_in_mf_table'列を先頭に移動
    df = df.reindex(columns=['row_no_in_mf_table'] + list(df.columns[:-1]))
    df = df.drop(['変更', '削除'], axis=1)
    return df


def get_asset_id_from_mf_table(page, table_type, row_no_in_mf_table):
    if table_type == 'table-depo':
        change_btn_column_no = 3
    elif table_type == 'table-eq':
        change_btn_column_no = 11
    else:
        return False
    element_xpath = '//*[@class="table table-bordered {}"]/tbody/tr[{}]/td[{}]/a'.format(table_type, row_no_in_mf_table,
                                                                                         change_btn_column_no)
    element = page.query_selector(element_xpath)
    # href属性から目的の文字列を取得し、これをasset_idとする
    href_attribute = element.get_attribute('href')
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
    # Find all delete buttons within the specified table
    modify_buttons = page.query_selector_all(
        f'.table.table-bordered.{table_type} .btn-asset-action[data-toggle="modal"]')
    # 変更ボタンの中からasset_idを含むボタンを探しクリックする
    for modify_button in modify_buttons:
        href = modify_button.get_attribute('href')
        if asset_id in href:
            modify_button.click()  # クリックするとモーダルが現れる
            break
    # 以下モーダルにおける操作
    modal_id = f'modal_asset{asset_id}'
    # ---資産の名称を変更---
    asset_det_name_textbox_xpath = f'//div[@id="{modal_id}"]//input[@id="user_asset_det_name"]'
    asset_det_name_textbox = page.query_selector(asset_det_name_textbox_xpath)
    asset_det_name_textbox.fill(str(asset_name)[:20])  # 20文字までしか入力できないので、最初の20文字を入力する
    # ---現在の価値を変更---
    asset_det_value_textbox_xpath = f'//div[@id="{modal_id}"]//input[@id="user_asset_det_value"]'
    asset_det_value_textbox = page.query_selector(asset_det_value_textbox_xpath)
    asset_det_value_textbox.fill(str(market_value)[:12])
    # ---購入価格を変更 (only if explicitly requested to preserve historical data)---
    if update_cost_basis and cost_amount is not None:
        asset_det_entried_price_textbox_xpath = f'//div[@id="{modal_id}"]//input[@id="user_asset_det_entried_price"]'
        asset_det_entried_price_textbox = page.query_selector(asset_det_entried_price_textbox_xpath)
        asset_det_entried_price_textbox.fill(str(cost_amount)[:12])
    # ---「この内容で登録」ボタンを押す---
    commit_btn_xpath = f'//div[@id="{modal_id}"]//input[@name="commit"]'
    commit_btn = page.query_selector(commit_btn_xpath)
    commit_btn.click()
    # ---モーダルが消えるまで待つ---
    page.wait_for_timeout(3000)
    page.wait_for_load_state('networkidle')
    return True


def create_asset_in_mf(page, asset_type, asset_name, market_value, cost_amount):
    page.get_by_role("button", name="手入力で資産を追加").click()
    page.get_by_role("combobox", name="資産の種類").select_option(str(asset_type))
    page.get_by_label("資産の名称").fill(str(asset_name)[:20])
    page.get_by_label("現在の価値").fill(str(market_value)[:12])
    page.get_by_label("購入価格").fill(str(cost_amount)[:12])
    page.get_by_role("button", name="この内容で登録する").click()
    page.wait_for_timeout(2000)
    page.wait_for_load_state('networkidle')
    return True


def delete_asset_in_mf(page, table_type, asset_id):
    # Handle dialog (popup)　表示されるダイアログを自動的に承認（OKボタンを押す）する。
    page.once("dialog", lambda dialog: dialog.accept())
    # Find all delete buttons within the specified table
    delete_buttons = page.query_selector_all(
        f'.table.table-bordered.{table_type} .btn-asset-action[data-method="delete"]')
    # 削除ボタンの中からasset_idを含むボタンを探す
    for delete_button in delete_buttons:
        href = delete_button.get_attribute('href')
        if asset_id in href:
            delete_button.click()
            # Wait for 1 sec
            page.wait_for_timeout(1000)
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
    # ---pageから「預金・現金・暗号資産」の表を取得する。
    mf_cash_deposit = get_mf_cash_deposit(page)
    # merge(ib_cash_reportとmf_cash_depositを突き合わる、キーはcurrency)
    merged_df = pd.merge(mf_cash_deposit, ib_cash_report, on='currency', how='outer').fillna('NONE')
    # 'Action' 列を追加
    merged_df['Action'] = 'NONE'  # 初期値を設定
    # 条件に基づいて 'Action' 列を更新
    merged_df.loc[(merged_df['row_no_in_mf_table'] != 'NONE') & (
            merged_df['value_JPY'] != merged_df['endingCash_JPY']), 'Action'] = 'MODIFY'
    # CONSERVATIVE: If asset in MF but not in IBKR, UPDATE to 0 instead of DELETE
    # This preserves historical data while showing current state (no balance)
    merged_df.loc[
        (merged_df['row_no_in_mf_table'] != 'NONE') & (merged_df['endingCash_JPY'] == 'NONE'), 'Action'] = 'MODIFY_TO_ZERO'
    merged_df.loc[
        (merged_df['row_no_in_mf_table'] == 'NONE') & (merged_df['endingCash_JPY'] != 'NONE'), 'Action'] = 'ADD'
    # print(merged_df)
    # ---更新を実施---
    df_to_modify = merged_df[(merged_df['Action'] == 'MODIFY')]
    for index, row in df_to_modify.iterrows():
        # Only update current value, preserve purchase price to maintain historical data
        modify_asset_in_mf(page, 'table-depo', row['asset_id'], row['currency'], int(row['endingCash_JPY']), update_cost_basis=False)
    # ---ゼロに更新 (削除の代わり) - Preserves historical data---
    df_to_zero = merged_df[(merged_df['Action'] == 'MODIFY_TO_ZERO')]
    for index, row in df_to_zero.iterrows():
        print(f"Setting {row['currency']} balance to 0 (not deleting to preserve history)")
        modify_asset_in_mf(page, 'table-depo', row['asset_id'], row['currency'], 0, update_cost_basis=False)
    # ---追加を実施---
    df_to_add = merged_df[(merged_df['Action'] == 'ADD')]
    for index, row in df_to_add.iterrows():
        create_asset_in_mf(page, ASSET_TYPE_CASH_DEPOSIT, row['currency'], int(row['endingCash_JPY']), '')
    return True


def reflect_to_mf_equity(page, ib_open_position):
    """
    Sync equity positions (stocks, options) from IBKR to MoneyForward.

    ASSET TYPE MAPPING:
    - Stocks (STK): Mapped by currency to appropriate stock category (14/15/16/55/17)
    - Options (OPT): Mapped to "指数OP" (Index Options, ID: 23)
    - See ASSET_SUBCLASS_MAP for complete mapping of all MoneyForward asset types

    CONSERVATIVE DELETION POLICY:
    - Assets are NEVER automatically deleted
    - If a position exists in MF but not in IBKR report, we UPDATE it to 0 value
    - This preserves historical data for closed positions, expired options, etc.
    - Allows MoneyForward to show historical performance even after position closure
    - Manual deletion via delete functions still available if needed
    """
    # ---pageから「預金・現金・暗号資産」の表を取得する。
    mf_equity = get_mf_equity(page)
    # Check if 'symbol' column exists in both DataFrames
    if 'symbol' not in mf_equity.columns:
        print("Warning: 'symbol' column not found in MoneyForward equity data.")
        mf_equity['symbol'] = None
    if 'symbol' not in ib_open_position.columns:
        print("Warning: 'symbol' column not found in IB open positions data.")
        ib_open_position['symbol'] = None
    # merge(ib_cash_reportとmf_cash_depositを突き合わる、キーはsymbol)
    merged_df = pd.merge(mf_equity, ib_open_position, on='symbol', how='outer').fillna('NONE')
    # 'Action' 列を追加
    merged_df['Action'] = 'NONE'  # 初期値を設定
    # 条件に基づいて 'Action' 列を更新
    merged_df.loc[(merged_df['row_no_in_mf_table'] != 'NONE') & (
            merged_df['value_JPY'] != merged_df['positionValue_JPY']), 'Action'] = 'MODIFY'
    # CONSERVATIVE: If position in MF but not in IBKR, UPDATE to 0 instead of DELETE
    # This is critical for: closed positions, expired options, sold holdings
    # Preserves cost basis and historical performance data
    merged_df.loc[
        (merged_df['row_no_in_mf_table'] != 'NONE') & (merged_df['positionValue_JPY'] == 'NONE'), 'Action'] = 'MODIFY_TO_ZERO'
    merged_df.loc[
        (merged_df['row_no_in_mf_table'] == 'NONE') & (merged_df['positionValue_JPY'] != 'NONE'), 'Action'] = 'ADD'
    # print(merged_df)
    # ---更新を実施---
    df_to_modify = merged_df[(merged_df['Action'] == 'MODIFY')]
    for index, row in df_to_modify.iterrows():
        # Use improved formatting: stocks "AAPL (100)", options "AAPL Jan24 $150C (10)"
        asset_name_to_input = format_asset_name(row)
        # Only update current value (positionValue_JPY), preserve cost basis to maintain historical data
        # This allows MoneyForward to track gains/losses over time correctly
        modify_asset_in_mf(page, 'table-eq', row['asset_id'], asset_name_to_input, int(row['positionValue_JPY']),
                           update_cost_basis=False)
    # ---ゼロに更新 (削除の代わり) - Preserves historical data for closed positions---
    df_to_zero = merged_df[(merged_df['Action'] == 'MODIFY_TO_ZERO')]
    for index, row in df_to_zero.iterrows():
        # Keep the original asset name from MoneyForward (preserve position info)
        # Extract symbol from MF data (format: "SYMBOL|quantity")
        original_name = str(row['銘柄名']) if '銘柄名' in row and row['銘柄名'] != 'NONE' else row['symbol']
        print(f"Setting {original_name} position to $0 (not deleting to preserve history)")
        modify_asset_in_mf(page, 'table-eq', row['asset_id'], original_name, 0, update_cost_basis=False)
    # ---追加を実施---
    df_to_add = merged_df[(merged_df['Action'] == 'ADD')]
    for index, row in df_to_add.iterrows():
        # Use improved formatting: stocks "AAPL (100)", options "AAPL Jan24 $150C (10)"
        asset_name_to_input = format_asset_name(row)
        # Determine asset type based on currency and asset category (STK, OPT, etc.)
        asset_category = str(row.get('assetCategory', 'STK'))
        asset_type_to_input = get_asset_type_for_currency(row['currency'], asset_category)
        create_asset_in_mf(page, asset_type_to_input, asset_name_to_input, int(row['positionValue_JPY']),
                           int(row['costBasisMoney_JPY']))
    return True
