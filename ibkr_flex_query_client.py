from ibflex import client
import pandas as pd
import xml.etree.ElementTree as ET
import logging

# ロギング設定 / Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_ib_flex_report(ib_flex_token, ib_flex_query_id, report_type):
    # IB FLEXレポートを取得
    # Get the IB FLEX report
    try:
        response = client.download(ib_flex_token, ib_flex_query_id)
    except Exception as e:
        logger.error(f"Failed to download IBKR Flex report: {e}")
        raise RuntimeError(f"IBKR API download failed: {e}") from e

    if not response:
        logger.error("Empty response received from IBKR API")
        raise ValueError("Empty response from IBKR API")

    try:
        xml_string = response.decode('utf-8')
    except (UnicodeDecodeError, AttributeError) as e:
        logger.error(f"Failed to decode response: {e}")
        raise ValueError(f"Invalid response format from IBKR API: {e}") from e

    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        logger.error(f"Failed to parse XML response: {e}")
        raise ValueError(f"Malformed XML received from IBKR API: {e}") from e

    # 指定されたレポート要素を探索
    # Find the specified report element
    report_element = root.find(f'FlexStatements/FlexStatement/{report_type}')

    if report_element is None:
        logger.error(f"Report type '{report_type}' not found in XML response")
        raise ValueError(f"Report type '{report_type}' not found in IBKR response. Check your Flex Query configuration.")
    # データを格納するためのリストを作成
    # Create list to store data
    data_list = []

    def extract_data(element):
        # サポート対象の全資産カテゴリ
        # All supported asset categories
            # STK - 株式 (Stock)
            # OPT - オプション (Option)
            # FUT - 先物 (Future)
            # CFD - 差金決済取引 (Contract for Difference)
            # WAR - ワラント (Warrant)
            # SWP - 外国為替 (Forex)
            # FND - 投資信託 (Mutual Fund)
            # BND - 債券 (Bond)
            # ICS - 商品間スプレッド (Inter-Commodity Spread)
        if report_type == 'OpenPositions':
            # サポート対象の資産カテゴリリスト
            # List of supported asset categories
            supported_categories = ["STK", "OPT", "FUT", "CFD", "WAR", "SWP", "FND", "BND", "ICS"]
            if element.get('assetCategory') not in supported_categories:
                return
        elif report_type == 'CashReport':
            if element.get('currency') == "BASE_SUMMARY":
                return
        else:
            return False
        # データを格納するための辞書
        # Dictionary to store data
        row = {}
        # 必要な属性のみ辞書に追加
        # Add only required attributes to dictionary
        attributes_to_keep = [
            # 共通属性 / Common attributes
            'currency',
            'assetCategory',
            'fxRateToBase',      # IBKRの為替レート（yfinanceの代替） / IBKR FX rate (replaces yfinance)

            # 現金報告用 / For CashReport
            'endingCash',

            # 保有ポジション用 / For OpenPositions
            'symbol',
            'position',
            'positionValue',
            'costBasisMoney',
            'costBasisPrice',    # 1株あたりのコストベース / Cost basis per share
            'markPrice',         # 現在の市場価格 / Current market price
            'openPrice',         # オープン価格 / Opening price
            'percentOfNAV',      # 純資産価値の割合 / Percentage of NAV
            'subCategory',
            'description',  # BND用の利率抽出に使用 / Used for coupon extraction in BND

            # 識別子 / Identifiers
            'conid',             # IBKRコントラクトID / IBKR contract ID
            'isin',              # 国際証券識別番号 / International Securities ID
            'cusip',             # CUSIP番号 / CUSIP code

            # 日付属性 / Date attributes (if available in Flex Query)
            'openDateTime',           # ポジションオープン日時 / Position open date/time
            'holdingPeriodDateTime',  # 保有期間開始日時 / Holding period start date/time
            'reportDate',             # レポート日付 / Report date

            # オプション固有属性 / Option-specific attributes
            'strike',
            'expiry',
            'putCall'
        ]

        # デバッグ: 最初の要素で利用可能な全属性をログ出力
        # Debug: Log all available attributes for first element
        if len(data_list) == 0 and element.attrib:
            logger.info(f"Available attributes in {report_type}: {list(element.attrib.keys())}")

        for attr in attributes_to_keep:
            if attr in element.attrib:
                row[attr] = element.attrib[attr]

        # データをリストに追加
        # Add data to list
        data_list.append(row)

    # レポートタイプに応じて要素を抽出
    # Extract elements based on report type
    if report_type == 'CashReport':
        cash_elements = report_element.findall('CashReportCurrency')
        if not cash_elements:
            logger.warning("No CashReportCurrency elements found in report")
        for element in cash_elements:
            extract_data(element)
    elif report_type == 'OpenPositions':
        position_elements = report_element.findall('OpenPosition')
        if not position_elements:
            logger.info("No OpenPosition elements found in report (portfolio may be empty)")
        for element in position_elements:
            extract_data(element)
    else:
        logger.error(f"Unsupported report type: {report_type}")
        raise ValueError(f"Unsupported report type: {report_type}. Expected 'CashReport' or 'OpenPositions'")
    # リストからDataFrameを作成
    # Create DataFrame from list
    df = pd.DataFrame(data_list)
    # print(df)
    return df
