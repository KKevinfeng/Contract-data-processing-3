"""数据处理模块：各个 Tab 页的数据计算逻辑"""

import pandas as pd
from ui.logger import log_info
from utils import (
    classify_contract,
    parse_product_lines,
    extract_contract_year,
)


def compute_customer_total(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tab 1：按客户汇总全部合同金额，并按年份分列展示，降序排列。

    年份列根据合同编号自动提取：合同编号第一个 "-" 前的两位数字代表年份，
    如 "AH11-P11-015" → 2011。只呈现数据中实际出现的年份。

    返回:
        DataFrame[最终客户名称, 合同总金额, 2011, 2018, ...]
    """
    df = df.copy()
    df["年份"] = df["合同编号*"].apply(extract_contract_year)

    # 剔除无法提取年份的行，并把年份强转为 int
    df = df[df["年份"].notna()]
    df["年份"] = df["年份"].astype(int)

    # 按客户 × 年份透视
    pivot = df.pivot_table(
        values="合同金额（元）*",
        index="最终客户名称",
        columns="年份",
        aggfunc="sum",
        fill_value=0.0,
    )

    # 动态获取数据中实际出现的年份，倒序排列（最近年份在前）
    year_range = sorted(df["年份"].unique(), reverse=True)

    # 确保每个年份都有列
    for y in year_range:
        if y not in pivot.columns:
            pivot[y] = 0.0

    # 按年份排序
    pivot = pivot[year_range]

    # 合同总金额 = 各年之和
    pivot["合同总金额"] = pivot.sum(axis=1)

    # 重置索引 → 显式构建结果
    pivot = pivot.reset_index()
    result = pd.DataFrame()
    result["最终客户名称"] = pivot["最终客户名称"]
    result["合同总金额"] = pivot["合同总金额"]
    for y in year_range:
        result[str(y)] = pivot[y]

    result = result.sort_values("合同总金额", ascending=False).reset_index(drop=True)
    log_info(f"客户总金额统计完成: {len(result)} 个客户, {year_range[-1]}-{year_range[0]} 年")
    return result


def compute_customer_category(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tab 2：按客户分别统计维保(M)、产品(P)、服务(S)三类合同金额。

    返回:
        DataFrame[最终客户名称, 维保合同总金额, 产品合同总金额, 服务合同总金额, 合计总金额]
    """
    df = df.copy()
    df["合同类型"] = df["合同编号*"].apply(classify_contract)

    # 透视表：客户 × 合同类型
    pivot = df.pivot_table(
        values="合同金额（元）*",
        index="最终客户名称",
        columns="合同类型",
        aggfunc="sum",
        fill_value=0,
    )

    # 确保 M/P/S 三列都存在
    for col in ["M", "P", "S"]:
        if col not in pivot.columns:
            pivot[col] = 0.0

    pivot = pivot[["M", "P", "S"]]
    pivot.columns = ["维保合同总金额", "产品合同总金额", "服务合同总金额"]
    pivot["合计总金额"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("合计总金额", ascending=False).reset_index()

    log_info(f"客户分类统计完成: {len(pivot)} 个客户")
    return pivot


def compute_product_sales(df: pd.DataFrame, merge_rules=None) -> pd.DataFrame:
    """
    Tab 4：按产品名称汇总售卖台数。
    - 仅统计 P（产品）类合同
    - 从产品名称型号列解析每行数据
    - 可选：根据合并规则将多个产品名称合并统计

    参数:
        df: 原始合同 DataFrame
        merge_rules: {显示名称: {产品A, 产品B, ...}}，合并规则字典

    返回:
        DataFrame[产品名称, 售卖总台数]
    """
    df = df.copy()
    df["合同类型"] = df["合同编号*"].apply(classify_contract)

    # 仅统计产品类合同
    df_p = df[df["合同类型"] == "P"]

    # 解析产品行并汇总
    product_totals: dict[str, int] = {}
    for _, row in df_p.iterrows():
        products = parse_product_lines(row["产品名称型号"])
        for p in products:
            name = p["name"]
            product_totals[name] = product_totals.get(name, 0) + p["qty"]

    # 应用合并规则
    if merge_rules:
        # 构建反向映射：原始名称 → 合并后显示名称
        name_map: dict[str, str] = {}
        for display_name, names in merge_rules.items():
            for name in names:
                name_map[name] = display_name

        merged_totals: dict[str, int] = {}
        for name, qty in product_totals.items():
            target = name_map.get(name, name)
            merged_totals[target] = merged_totals.get(target, 0) + qty
        product_totals = merged_totals

    result = pd.DataFrame(
        [{"产品名称": k, "售卖总台数": v} for k, v in product_totals.items()]
    ).sort_values("售卖总台数", ascending=False).reset_index(drop=True)

    log_info(f"产品销量统计完成: {len(result)} 个产品")
    return result


def compute_industry_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tab 5：按一级行业统计不重复客户数量、合同总金额及分年金额，降序排列。

    返回:
        DataFrame[一级行业, 数量, 行业总金额, 2026, 2025, ...]
    """
    df = df.copy()

    # 不重复客户数量
    customer_count = df.groupby("一级行业")["最终客户名称"].nunique()

    # 提取年份用于分年统计
    df["年份"] = df["合同编号*"].apply(extract_contract_year)
    df = df[df["年份"].notna()]
    df["年份"] = df["年份"].astype(int)

    # 按行业 × 年份透视金额
    pivot = df.pivot_table(
        values="合同金额（元）*",
        index="一级行业",
        columns="年份",
        aggfunc="sum",
        fill_value=0.0,
    )

    year_range = sorted(df["年份"].unique(), reverse=True)
    for y in year_range:
        if y not in pivot.columns:
            pivot[y] = 0.0
    pivot = pivot[year_range]

    # 行业总金额 = 各年之和
    pivot["行业总金额"] = pivot.sum(axis=1)

    pivot = pivot.reset_index()

    # 合并不重复客户数量
    pivot["数量"] = pivot["一级行业"].map(customer_count).fillna(0).astype(int)

    # 构建结果
    result = pd.DataFrame()
    result["一级行业"] = pivot["一级行业"]
    result["数量"] = pivot["数量"]
    result["行业总金额"] = pivot["行业总金额"]
    for y in year_range:
        result[str(y)] = pivot[y]

    result = result.sort_values("行业总金额", ascending=False).reset_index(drop=True)
    log_info(f"行业统计完成: {len(result)} 个行业, {year_range[-1]}-{year_range[0]} 年")
    return result


def get_secondary_industries(df: pd.DataFrame, primary: str) -> pd.DataFrame:
    """
    查询指定一级行业下的二级行业统计（按不重复客户计数）。

    参数:
        df: 原始合同 DataFrame
        primary: 一级行业名称

    返回:
        DataFrame[二级行业, 数量]
    """
    subset = df[df["一级行业"] == primary]
    result = subset.groupby("二级行业")["最终客户名称"].nunique().reset_index(name="数量")
    result = result.sort_values("数量", ascending=False).reset_index(drop=True)
    log_info(f"下钻二级行业 [{primary}]: {len(result)} 个")
    return result


def get_industry_customers(df: pd.DataFrame, primary: str, secondary: str) -> pd.DataFrame:
    """
    查询指定一级+二级行业下的客户名单。

    参数:
        df: 原始合同 DataFrame
        primary: 一级行业名称
        secondary: 二级行业名称

    返回:
        DataFrame[最终客户名称]
    """
    subset = df[(df["一级行业"] == primary) & (df["二级行业"] == secondary)]
    if subset.empty:
        return pd.DataFrame(columns=["最终客户名称"])
    result = subset[["最终客户名称"]].drop_duplicates()
    result = result.sort_values("最终客户名称").reset_index(drop=True)
    log_info(f"下钻客户名单 [{primary} / {secondary}]: {len(result)} 个")
    return result


def get_product_p_contracts(df: pd.DataFrame, product_name: str, merge_rules=None) -> pd.DataFrame:
    """
    查询与指定产品名称关联的所有 P 类合同明细。
    - 仅统计 P（产品）类合同
    - 如果产品名称是合并后的显示名称，则包含所有被合并的原始产品

    参数:
        df: 原始合同 DataFrame
        product_name: 产品名称（可能是合并后的显示名称）
        merge_rules: {显示名称: {产品A, 产品B, ...}}，合并规则字典

    返回:
        DataFrame[合同编号*, 最终客户名称, 产品名称型号, 合同金额（元）*]
    """
    df = df.copy()
    df["合同类型"] = df["合同编号*"].apply(classify_contract)
    df_p = df[df["合同类型"] == "P"].copy()

    # 确定要匹配的产品名称集合（考虑合并规则）
    target_names: set[str] = {product_name}
    if merge_rules:
        if product_name in merge_rules:
            target_names = merge_rules[product_name]

    # 筛选包含目标产品的合同行
    matched_rows = []
    for _, row in df_p.iterrows():
        products = parse_product_lines(row["产品名称型号"])
        row_names = {p["name"] for p in products}
        if row_names & target_names:
            matched_rows.append({
                "合同编号*": row["合同编号*"],
                "最终客户名称": row["最终客户名称"],
                "产品名称型号": row["产品名称型号"],
                "合同金额（元）*": row["合同金额（元）*"],
            })

    if not matched_rows:
        return pd.DataFrame(columns=["合同编号*", "最终客户名称", "产品名称型号", "合同金额（元）*"])

    result = pd.DataFrame(matched_rows)
    result = result.sort_values("合同金额（元）*", ascending=False).reset_index(drop=True)
    log_info(f"产品关联合同查询 [{product_name}]: {len(result)} 条")
    return result
