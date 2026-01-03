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
        # 株式とオプションの両方でフィルタリング
        # Filter for both stocks and options
            # サポート対象
            # Supported
                # STK - 株式 (Stock)
                # OPT - オプション (Option)
            # 現在サポート対象外（実装ロードマップについてはTODO.md参照）
            # Not Currently Supported (see TODO.md for implementation roadmap)
                # TODO: FUT - 先物のサポートを追加 (Future)
                # TODO: CFD - 差金決済取引のサポートを追加 (Contract for Difference)
                # TODO: WAR - ワラントのサポートを追加 (Warrant)
                # TODO: SWP - 外国為替のサポートを追加 (Forex)
                # TODO: FND - 投資信託のサポートを追加 (Mutual Fund)
                # TODO: BND - 債券のサポートを追加 (Bond)
                # TODO: ICS - 商品間スプレッドのサポートを追加 (Inter-Commodity Spread)
        if report_type == 'OpenPositions':
            # TODO: 新しいタイプが実装されたらサポート対象資産カテゴリを拡張
            # TODO: Expand supported asset categories as new types are implemented
            if element.get('assetCategory') not in ["STK", "OPT"]:
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
            'accountId',
            'currency',
            'fromDate',
            'toDate',
            'reportDate',
            'endingCash',
            'assetCategory',
            'subCategory',
            'symbol',
            'description',
            'listingExchange',
            'openPrice',
            'costBasisPrice',
            'costBasisMoney',
            'side',
            'positionValue',
            'fifoPnlUnrealized',
            'position',
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
