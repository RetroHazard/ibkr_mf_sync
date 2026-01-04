from ibflex import client
import pandas as pd
import xml.etree.ElementTree as ET


def get_ib_flex_report(ib_flex_token, ib_flex_query_id, report_type):
    # IB FLEXレポートを取得
    # Get the IB FLEX report
    response = client.download(ib_flex_token, ib_flex_query_id)
    xml_string = response.decode('utf-8')
    root = ET.fromstring(xml_string)
    # 指定されたレポート要素を探索
    # Find the specified report element
    report_element = root.find(f'FlexStatements/FlexStatement/{report_type}')
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

            # 現金報告用 / For CashReport
            'endingCash',

            # 保有ポジション用 / For OpenPositions
            'symbol',
            'position',
            'positionValue',
            'costBasisMoney',
            'subCategory',
            'description',  # BND用の利率抽出に使用 / Used for coupon extraction in BND

            # オプション固有属性 / Option-specific attributes
            'strike',
            'expiry',
            'putCall'
        ]
        for attr in attributes_to_keep:
            if attr in element.attrib:
                row[attr] = element.attrib[attr]

        # データをリストに追加
        # Add data to list
        data_list.append(row)

    # レポートタイプに応じて要素を抽出
    # Extract elements based on report type
    if report_type == 'CashReport':
        for report_element in report_element.findall('CashReportCurrency'):
            extract_data(report_element)
    elif report_type == 'OpenPositions':
        for report_element in report_element.findall('OpenPosition'):
            extract_data(report_element)
    else:
        return False
    # リストからDataFrameを作成
    # Create DataFrame from list
    df = pd.DataFrame(data_list)
    # print(df)
    return df
