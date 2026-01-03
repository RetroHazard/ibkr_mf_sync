"""
MoneyForward Asset Type Mapping

This module contains the complete mapping of MoneyForward ME asset_subclass_id values
to human-readable Japanese names, as extracted from the manual asset entry form.

Reference: MoneyForward ME manual asset entry form
<select name="user_asset_det[asset_subclass_id]">
"""

# MoneyForward Asset Subclass ID Mapping
# Complete list of asset_subclass_id values from MoneyForward's manual asset entry form
ASSET_SUBCLASS_MAP = {
    # 預金・現金・暗号資産 (Deposits, Cash, Cryptocurrency)
    '49': '現金',
    '50': '電子マネー',
    '1': '普通預金',
    '2': '定期預金',
    '69': '積立定期預金',
    '3': '外貨預金',
    '5': '預り金・MRF',
    '51': '保証金・証拠金',
    '66': '暗号資産',
    '6': 'その他預金',

    # 株式(現物) (Physical Stocks)
    '14': '国内株',
    '15': '米国株',
    '16': '中国株',
    '55': '外国株',
    '56': '未公開株式',
    '17': 'その他株式',

    # 株式(信用) (Margin Trading Stocks)
    '62': '保証金・証拠金(信用)',
    '57': '国内株(信用)',
    '58': '米国株(信用)',
    '59': '中国株(信用)',
    '60': '外国株(信用)',
    '61': 'その他株式(信用)',

    # 投資信託 (Investment Trusts)
    '12': '投資信託',
    '52': '外国投資信託',
    '53': '中期国債ファンド',
    '54': 'MMF',
    '4': '外貨MMF',
    '13': 'その他投信',

    # 債券 (Bonds)
    '7': '国債',
    '8': '社債',
    '9': '外債',
    '10': '仕組み債',
    '11': 'その他債券',
    '67': 'ソーシャルレンディング',

    # FX
    '64': '証拠金(FX)',
    '18': '店頭FX',
    '19': 'くりっく365',
    '20': '大証FX',
    '21': 'その他FX',

    # 先物OP (Futures & Options)
    '63': '証拠金(先物OP)',
    '22': '指数先物',
    '23': '指数OP',
    '24': 'CFD',
    '25': 'くりっく株365',
    '26': '商品先物',
    '27': 'その他先物OP',

    # ストックオプション (Stock Options)
    '70': '国内株(ストックオプション)',

    # 保険 (Insurance)
    '32': '積立型保険',

    # 不動産 (Real Estate)
    '28': '建物(自宅)',
    '29': '建物(投資・事業用)',
    '30': '土地(自宅)',
    '31': '土地(投資・事業用)',

    # 年金 (Pension)
    '33': '国民年金',
    '34': '厚生年金',
    '35': '共済年金',
    '36': '企業年金',
    '37': '厚生年金基金',
    '38': '国民年金基金',
    '39': '確定拠出年金',
    '40': '私的年金',

    # ポイント (Points & Miles)
    '48': 'ポイント・マイル',

    # その他の資産 (Other Assets)
    '41': '自動車',
    '42': '貴金属・宝石類',
    '43': 'その他',
}


def get_asset_type_for_currency(currency, asset_category='STK'):
    """
    Determine the appropriate MoneyForward asset_subclass_id based on currency and asset category.

    Args:
        currency: Currency code (e.g., 'JPY', 'USD', 'CNY', 'HKD')
        asset_category: Asset category from IBKR ('STK', 'OPT', 'FUT', etc.)

    Returns:
        asset_subclass_id as string (e.g., '14', '15', '16', '17', '55')
    """
    if asset_category == 'OPT':
        # Options are mapped to "指数OP" (Index Options)
        return '23'

    # Stock mapping based on currency
    if currency == 'JPY':
        return '14'  # 国内株（日本株）
    elif currency == 'USD':
        return '15'  # 米国株
    elif currency in {'CNY', 'HKD'}:
        return '16'  # 中国株
    elif currency in {'CAD', 'GBP', 'EUR', 'AUD', 'NZD', 'SGD'}:
        return '55'  # 外国株
    else:
        return '17'  # その他株式（fallback）


# Constants for commonly used asset types
ASSET_TYPE_CASH_DEPOSIT = '51'  # 保証金・証拠金
ASSET_TYPE_DOMESTIC_STOCK = '14'  # 国内株
ASSET_TYPE_US_STOCK = '15'  # 米国株
ASSET_TYPE_CHINA_STOCK = '16'  # 中国株
ASSET_TYPE_FOREIGN_STOCK = '55'  # 外国株
ASSET_TYPE_OTHER_STOCK = '17'  # その他株式
ASSET_TYPE_INDEX_OPTION = '23'  # 指数OP
