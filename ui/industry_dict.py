"""行业数据字典 — 存储所有一级行业 / 二级行业，持久化到 JSON 文件。"""

import json
import os
from typing import Optional

from ui.logger import log_info, log_error

DICT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "industry_dict.json")


def _load() -> dict[str, list[str]]:
    """读取 JSON，返回 {"一级行业": [...], "二级行业": [...]}。"""
    try:
        if os.path.exists(DICT_FILE):
            with open(DICT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log_error(f"读取行业数据字典文件失败: {e}")
    return {"一级行业": [], "二级行业": []}


def _save(data: dict[str, list[str]]) -> None:
    """保存到 JSON 文件。"""
    try:
        os.makedirs(os.path.dirname(DICT_FILE), exist_ok=True)
        with open(DICT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_error(f"保存行业数据字典文件失败: {e}")


def get_all() -> dict[str, list[str]]:
    """获取全部字典数据。"""
    return _load()


def get_primary() -> list[str]:
    """获取所有一级行业列表。"""
    return _load().get("一级行业", [])


def get_secondary() -> list[str]:
    """获取所有二级行业列表。"""
    return _load().get("二级行业", [])


def add_primary(name: str) -> None:
    """新增一级行业（去重）。"""
    data = _load()
    items = data.setdefault("一级行业", [])
    if name not in items:
        items.append(name)
        items.sort()
        _save(data)
        log_info(f"新增一级行业: {name}")


def add_secondary(name: str) -> None:
    """新增二级行业（去重）。"""
    data = _load()
    items = data.setdefault("二级行业", [])
    if name not in items:
        items.append(name)
        items.sort()
        _save(data)
        log_info(f"新增二级行业: {name}")


def remove_primary(name: str) -> None:
    """删除某个一级行业。"""
    data = _load()
    items = data.get("一级行业", [])
    if name in items:
        items.remove(name)
        _save(data)
        log_info(f"删除一级行业: {name}")


def remove_secondary(name: str) -> None:
    """删除某个二级行业。"""
    data = _load()
    items = data.get("二级行业", [])
    if name in items:
        items.remove(name)
        _save(data)
        log_info(f"删除二级行业: {name}")


def merge_from_dataframe(df: "pd.DataFrame") -> None:
    """从 DataFrame 中提取一级/二级行业，合并到字典中（去重）。"""
    data = _load()
    changed = False
    added_count = 0

    for col, key in [("一级行业", "一级行业"), ("二级行业", "二级行业")]:
        if col not in df.columns:
            continue
        items = data.setdefault(key, [])
        existing = set(items)
        for val in df[col].dropna().unique():
            val = str(val).strip()
            if val and val != "未知" and val not in existing:
                items.append(val)
                existing.add(val)
                changed = True
                added_count += 1

    if changed:
        data["一级行业"] = sorted(data["一级行业"])
        data["二级行业"] = sorted(data["二级行业"])
        _save(data)
        log_info(f"自动合并行业字典: 新增 {added_count} 个条目")
