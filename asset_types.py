"""
MoneyForward資産タイプマッピング
MoneyForward Asset Type Mapping

このモジュールは、手動資産入力フォームから抽出された、
MoneyForward MEのasset_subclass_id値と人間が読める日本語名の完全なマッピングを含みます。
This module contains the complete mapping of MoneyForward ME asset_subclass_id values
to human-readable Japanese names, as extracted from the manual asset entry form.

IBKR資産カテゴリとMoneyForward資産タイプのマッピングロジックを提供します：
Provides mapping logic between IBKR asset categories and MoneyForward asset types:
    - STK (株式) → 通貨ベースの株式分類 (Currency-based stock classification)
    - OPT (オプション) → 指数OP (Index Options)
    - FUT (先物) → 指数先物/商品先物 (Index/Commodity Futures)
    - CFD (差金決済取引) → CFD
    - WAR (ワラント) → 通貨ベースの株式分類 (Currency-based stock classification)
    - SWP/CASH (外国為替) → 店頭FX (OTC Forex)
    - FND (投資信託) → 投資信託/外国投資信託 (Domestic/Foreign Funds)
    - BND (債券) → 国債/社債/外債 (Govt/Corp/Foreign Bonds)
    - ICS (商品間スプレッド) → 商品先物 (Commodity Futures)

参照: MoneyForward ME 手動資産入力フォーム
Reference: MoneyForward ME manual asset entry form
<select name="user_asset_det[asset_subclass_id]">
"""

# MoneyForward資産サブクラスIDマッピング
# MoneyForward Asset Subclass ID Mapping
# MoneyForwardの手動資産入力フォームからのasset_subclass_id値の完全なリスト
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


def get_asset_type_for_currency(currency, asset_category='STK', subcategory=None):
    """
    通貨と資産カテゴリに基づいて適切なMoneyForward asset_subclass_idを決定します。
    Determine the appropriate MoneyForward asset_subclass_id based on currency and asset category.

    引数:
    Args:
        currency: 通貨コード（例: 'JPY', 'USD', 'CNY', 'HKD'）
                  Currency code (e.g., 'JPY', 'USD', 'CNY', 'HKD')
        asset_category: IBKRからの資産カテゴリ（'STK', 'OPT', 'FUT'など）
                        Asset category from IBKR ('STK', 'OPT', 'FUT', etc.)
        subcategory: IBKRからのサブカテゴリ（オプション、詳細な分類用）
                     Subcategory from IBKR (optional, for detailed classification)

    戻り値:
    Returns:
        文字列としてのasset_subclass_id（例: '14', '15', '16', '17', '55'）
        asset_subclass_id as string (e.g., '14', '15', '16', '17', '55')
    """
    # オプション取引
    # Options trading
    if asset_category == 'OPT':
        # オプションは「指数OP」（インデックスオプション）にマップ
        # Options are mapped to "指数OP" (Index Options)
        return '23'

    # 先物取引
    # Futures trading
    if asset_category == 'FUT':
        # 先物タイプを判定
        # Determine futures type
        if subcategory and 'CMDTY' in subcategory:
            # 商品先物
            # Commodity futures
            return '26'
        else:
            # 指数先物（デフォルト）
            # Index futures (default)
            return '22'

    # CFD（差金決済取引）
    # CFD (Contract for Difference)
    if asset_category == 'CFD':
        return '24'  # CFD

    # ワラント
    # Warrants
    if asset_category == 'WAR':
        # ワラントは株式として分類（通貨ベース）
        # Warrants are classified as stocks (currency-based)
        # 国内ワラントと外国ワラントを区別
        # Distinguish between domestic and foreign warrants
        if currency == 'JPY':
            return '14'  # 国内株
        elif currency == 'USD':
            return '15'  # 米国株
        elif currency in {'CNY', 'HKD'}:
            return '16'  # 中国株
        else:
            return '55'  # 外国株

    # 外国為替（スワップ/FX）
    # Forex (Swaps/FX)
    if asset_category == 'SWP' or asset_category == 'CASH':
        # FX取引として分類
        # Classified as FX trading
        return '18'  # 店頭FX（デフォルトの店頭FX取引）

    # 投資信託
    # Mutual Funds
    if asset_category == 'FND':
        # 通貨ベースで分類
        # Classify by currency
        if currency == 'JPY':
            return '12'  # 投資信託（国内）
        else:
            return '52'  # 外国投資信託

    # 債券
    # Bonds
    if asset_category == 'BND':
        # サブカテゴリまたは通貨で債券タイプを判定
        # Determine bond type by subcategory or currency
        if subcategory and 'GOVT' in subcategory:
            # 国債
            # Government bonds
            return '7'
        elif subcategory and 'CORP' in subcategory:
            # 社債
            # Corporate bonds
            return '8'
        elif currency != 'JPY':
            # 外債
            # Foreign bonds
            return '9'
        else:
            # その他債券（デフォルト）
            # Other bonds (default)
            return '11'

    # 商品間スプレッド
    # Inter-Commodity Spreads
    if asset_category == 'ICS':
        # 商品先物として分類
        # Classified as commodity futures
        return '26'

    # 株式（現物）
    # Physical Stocks
    # 通貨に基づく株式マッピング
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


# よく使用される資産タイプの定数
# Constants for commonly used asset types

# 保証金・現金
# Deposits & Cash
ASSET_TYPE_CASH_DEPOSIT = '51'  # 保証金・証拠金
ASSET_TYPE_FX_MARGIN = '64'  # 証拠金(FX)
ASSET_TYPE_FUTURES_MARGIN = '63'  # 証拠金(先物OP)

# 株式（現物）
# Physical Stocks
ASSET_TYPE_DOMESTIC_STOCK = '14'  # 国内株
ASSET_TYPE_US_STOCK = '15'  # 米国株
ASSET_TYPE_CHINA_STOCK = '16'  # 中国株
ASSET_TYPE_FOREIGN_STOCK = '55'  # 外国株
ASSET_TYPE_OTHER_STOCK = '17'  # その他株式

# デリバティブ
# Derivatives
ASSET_TYPE_INDEX_OPTION = '23'  # 指数OP
ASSET_TYPE_INDEX_FUTURE = '22'  # 指数先物
ASSET_TYPE_COMMODITY_FUTURE = '26'  # 商品先物
ASSET_TYPE_CFD = '24'  # CFD

# FX
ASSET_TYPE_OTC_FX = '18'  # 店頭FX
ASSET_TYPE_CLICK365 = '19'  # くりっく365

# 投資信託
# Investment Trusts
ASSET_TYPE_DOMESTIC_FUND = '12'  # 投資信託
ASSET_TYPE_FOREIGN_FUND = '52'  # 外国投資信託

# 債券
# Bonds
ASSET_TYPE_GOVT_BOND = '7'  # 国債
ASSET_TYPE_CORP_BOND = '8'  # 社債
ASSET_TYPE_FOREIGN_BOND = '9'  # 外債
ASSET_TYPE_STRUCTURED_BOND = '10'  # 仕組み債
ASSET_TYPE_OTHER_BOND = '11'  # その他債券
