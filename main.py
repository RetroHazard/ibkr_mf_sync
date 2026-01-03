import configparser
import os
from playwright.sync_api import sync_playwright
import ibkr_flex_query_client as ibflex
import moneyforward_processing as mfproc
import utils
from contextlib import suppress
from playwright.sync_api import sync_playwright, Error as PlaywrightError


def get_config_value(env_var, config, section, key, required=True):
    """
    Get configuration value from environment variable first, fallback to config.ini.

    Args:
        env_var: Environment variable name to check
        config: ConfigParser object
        section: Config file section name
        key: Config file key name
        required: If True, raise error if value not found in either source

    Returns:
        Configuration value from environment or config file
    """
    # Try environment variable first
    value = os.environ.get(env_var)
    if value is not None:
        return value

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
    config = configparser.ConfigParser()
    config.read('config.ini')

    # 環境変数を優先、config.iniをフォールバックとして設定を取得
    # Environment variables take precedence, config.ini as fallback
    MF_EMAIL = get_config_value('MF_EMAIL', config, 'moneyforward', 'email')
    MF_PASS = get_config_value('MF_PASSWORD', config, 'moneyforward', 'password')
    MF_IB_INSTITUTION_URL = get_config_value('MF_IB_INSTITUTION_URL', config, 'moneyforward', 'ib_institution_url')
    IB_FLEX_TOKEN = get_config_value('IBKR_FLEX_TOKEN', config, 'ibkr_flex_query', 'token')
    # TODO: Add token expiration tracking (see TODO.md)
    # IBKR Flex tokens expire after 1 year - need to warn users before expiration
    IB_FLEX_QUERY_FOR_MF_ID = get_config_value('IBKR_FLEX_QUERY_ID', config, 'ibkr_flex_query', 'query_id')
    # ---GET IB FLEX REPORT---
    ib_cash_report = ibflex.get_ib_flex_report(IB_FLEX_TOKEN, IB_FLEX_QUERY_FOR_MF_ID, 'CashReport')
    ib_cash_report = utils.add_value_jpy(ib_cash_report, 'endingCash', 'endingCash_JPY')  # 現金残高を日本円に変換
    ib_open_position = ibflex.get_ib_flex_report(IB_FLEX_TOKEN, IB_FLEX_QUERY_FOR_MF_ID, 'OpenPositions')
    if not ib_open_position.empty:
        ib_open_position = utils.add_value_jpy(ib_open_position, 'costBasisMoney', 'costBasisMoney_JPY')  # 取得金額を日本円に変換
        ib_open_position = utils.add_value_jpy(ib_open_position, 'positionValue', 'positionValue_JPY')  # 現在価値を日本円に変換
    else:
        print("No open positions found.")
    with sync_playwright() as playwright:
        # Open a new browser context
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            # Change user agent 以下のようにuser_agentを偽造しないと、MoneyForwardのログイン画面が表示されないため。
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Set up a dialog handler that can be removed later
        def dialog_handler(dialog):
            dialog.accept()

        # Add the dialog handler
        page.on("dialog", dialog_handler)
        try:
            page.goto(MF_IB_INSTITUTION_URL)
            # ---MoneyForward Me Login---
            page = mfproc.login(page, MF_EMAIL, MF_PASS)
            page.wait_for_load_state('networkidle')
        except PlaywrightError as e:
            if "Cannot accept dialog which is already handled!" in str(e):
                print("Dialog was already handled, continuing execution...")
            else:
                raise  # Re-raise the exception if it's not the one we're expecting
        finally:
            # Remove the dialog handler to prevent multiple handlers
            page.remove_listener("dialog", dialog_handler)

        # ---取得したIB FLEX REPORTをMoneyForward MEに反映する---
        mfproc.reflect_to_mf_cash_deposit(page, ib_cash_report)
        mfproc.reflect_to_mf_equity(page, ib_open_position)
        # Close browser context
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
