import streamlit as st
import os
from playwright.sync_api import sync_playwright
import ibkr_flex_query_client as ibflex
import moneyforward_processing as mfproc
import utils


def main(MF_EMAIL, MF_PASS, IB_FLEX_QUERY_FOR_MF_ID, IB_FLEX_TOKEN, MF_IB_INSTITUTION_URL):
    # ---IB FLEXレポートを取得---
    # ---GET IB FLEX REPORT---
    ib_cash_report = ibflex.get_ib_flex_report(IB_FLEX_TOKEN, IB_FLEX_QUERY_FOR_MF_ID, 'CashReport')
    # 現金残高を日本円に変換
    # Convert cash balance to JPY
    ib_cash_report = utils.add_value_jpy(ib_cash_report, 'endingCash', 'endingCash_JPY')
    ib_open_position = ibflex.get_ib_flex_report(IB_FLEX_TOKEN, IB_FLEX_QUERY_FOR_MF_ID, 'OpenPositions')
    # 取得金額を日本円に変換
    # Convert acquisition cost to JPY
    ib_open_position = utils.add_value_jpy(ib_open_position, 'costBasisMoney', 'costBasisMoney_JPY')
    # 現在価値を日本円に変換
    # Convert current value to JPY
    ib_open_position = utils.add_value_jpy(ib_open_position, 'positionValue', 'positionValue_JPY')
    with sync_playwright() as playwright:
        # 新しいブラウザコンテキストを開く
        # Open a new browser context
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            # ユーザーエージェントを変更 - MoneyForwardのログイン画面を表示するために必要
            # Change user agent - Required to display MoneyForward login screen
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"
        )
        page = context.new_page()
        # ダイアログ（ポップアップ）を処理 - 表示されるダイアログを自動的に承認（OKボタンを押す）
        # Handle dialog (popup) - Automatically accept displayed dialogs (click OK button)
        page.once("dialog", lambda dialog: dialog.accept())
        # ---MoneyForward Meログイン---
        # ---MoneyForward Me Login---
        page = mfproc.login(page, MF_EMAIL, MF_PASS)
        # ---MoneyForward上で手動登録したIBKRのページに遷移---
        # ---Navigate to manually registered IBKR page on MoneyForward---
        page.goto(MF_IB_INSTITUTION_URL)
        page.wait_for_load_state('networkidle')
        # ---取得したIB FLEXレポートをMoneyForward MEに反映---
        # ---Reflect retrieved IB FLEX report to MoneyForward ME---
        mfproc.reflect_to_mf_cash_deposit(page, ib_cash_report)
        mfproc.reflect_to_mf_equity(page, ib_open_position)
        # ブラウザコンテキストを閉じる
        # Close browser context
        context.close()
        browser.close()


def app():
    st.title('IBKR to MoneyForward Syncer')

    # 環境変数から利用可能な場合はデフォルト値を読み込む
    # Load default values from environment variables if available
    MF_EMAIL = st.text_input('MF_EMAIL', value=os.environ.get('MF_EMAIL', ''))
    MF_PASS = st.text_input('MF_PASSWORD', value=os.environ.get('MF_PASSWORD', ''), type='password')
    IB_FLEX_QUERY_FOR_MF_ID = st.text_input('IBKR_FLEX_QUERY_ID', value=os.environ.get('IBKR_FLEX_QUERY_ID', ''))
    IB_FLEX_TOKEN = st.text_input('IBKR_FLEX_TOKEN', value=os.environ.get('IBKR_FLEX_TOKEN', ''), type='password')
    MF_IB_INSTITUTION_URL = st.text_input('MF_IB_INSTITUTION_URL', value=os.environ.get('MF_IB_INSTITUTION_URL', ''))

    if st.button('Sync'):
        if not all([MF_EMAIL, MF_PASS, IB_FLEX_QUERY_FOR_MF_ID, IB_FLEX_TOKEN, MF_IB_INSTITUTION_URL]):
            st.error('All fields are required!')
            return
        main(MF_EMAIL, MF_PASS, IB_FLEX_QUERY_FOR_MF_ID, IB_FLEX_TOKEN, MF_IB_INSTITUTION_URL)
        st.success('Finished!')


if __name__ == "__main__":
    app()
