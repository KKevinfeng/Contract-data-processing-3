"""行业覆盖规则 — 人工设定某个客户的一级行业 / 二级行业，持久化到 JSON 文件。"""

import json
import os
from typing import Optional

from ui.logger import log_info, log_error

OVERRIDES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "industry_overrides.json")


def _load() -> dict[str, dict[str, str]]:
    """读取 JSON，返回 {客户名: {一级行业: xxx, 二级行业: xxx}}。

    支持 UTF-8 与 UTF-16（含 BOM），读取后自动重写到 UTF-8 统一编码。
    """
    import codecs
    try:
        if not os.path.exists(OVERRIDES_FILE):
            return {}

        # 自动判断编码：优先 utf-8-sig，失败则尝试 utf-16
        with open(OVERRIDES_FILE, "rb") as f:
            raw = f.read()

        data = None
        try:
            text = raw.decode("utf-8-sig")
            data = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            try:
                text = raw.decode("utf-16")
                data = json.loads(text)
            except Exception as e:
                # 兜底再试 gbk
                text = raw.decode("gbk", errors="replace")
                data = json.loads(text)

        # 自动转写为 UTF-8（兼容现有其它依赖 utf-8 的代码）
        if data is not None:
            try:
                with open(OVERRIDES_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass  # 重写失败不影响读取

        return data or {}
    except Exception as e:
        log_error(f"读取行业覆盖规则文件失败: {e}")
        return {}


def _save(data: dict[str, dict[str, str]]) -> None:
    """保存到 JSON 文件。"""
    try:
        os.makedirs(os.path.dirname(OVERRIDES_FILE), exist_ok=True)
        with open(OVERRIDES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_error(f"保存行业覆盖规则文件失败: {e}")


def get_all() -> dict[str, dict[str, str]]:
    """获取全部覆盖规则。"""
    return _load()


def get_override(customer: str) -> Optional[dict[str, str]]:
    """获取某个客户的覆盖规则，没有则返回 None。"""
    return _load().get(customer.strip())


def set_override(customer: str, primary: str, secondary: str) -> None:
    """设置 / 更新某个客户的一级 + 二级行业。"""
    data = _load()
    data[customer.strip()] = {"一级行业": primary.strip(), "二级行业": secondary.strip()}
    _save(data)
    log_info(f"设置行业覆盖规则: {customer.strip()} → {primary.strip()} / {secondary.strip()}")


def remove_override(customer: str) -> None:
    """删除某个客户的覆盖规则。"""
    data = _load()
    data.pop(customer.strip(), None)
    _save(data)
    log_info(f"删除行业覆盖规则: {customer.strip()}")


def apply_overrides(df: "pd.DataFrame") -> "pd.DataFrame":
    """将覆盖规则应用到 DataFrame：对匹配的客户替换一二级行业值。"""
    overrides = _load()
    if not overrides:
        return df

    df = df.copy()
    # 先去掉客户名两端空格，确保匹配一致
    df["最终客户名称"] = df["最终客户名称"].astype(str).str.strip()
    matched = 0
    for customer, mapping in overrides.items():
        customer_clean = customer.strip()
        mask = df["最终客户名称"] == customer_clean
        if mask.any():
            df.loc[mask, "一级行业"] = mapping["一级行业"]
            df.loc[mask, "二级行业"] = mapping["二级行业"]
            matched += 1
    log_info(f"应用行业覆盖规则: {matched}/{len(overrides)} 条生效")
    return df
