"""标星缓存管理 —— 持久化重点客户到 starred_customers.xlsx"""

from __future__ import annotations

import os
import pandas as pd

from ui.logger import log_error

_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "starred_customers.xlsx")
_COLUMNS = ["序号", "最终客户名称"]


class StarredCache:
    """标星客户缓存，持久化到程序目录 Excel 文件。"""

    def __init__(self):
        self._cache_path = os.path.normpath(_CACHE_FILE)

    # ── 读写 ────────────────────────────────────────────────

    def _read(self) -> pd.DataFrame:
        """读取缓存文件，不存在则返回空 DataFrame。"""
        try:
            if not os.path.exists(self._cache_path):
                return pd.DataFrame(columns=_COLUMNS)
            return pd.read_excel(self._cache_path)
        except Exception as e:
            log_error(f"读取标星缓存文件失败: {e}")
            return pd.DataFrame(columns=_COLUMNS)

    def _write(self, df: pd.DataFrame) -> None:
        """写入缓存文件并重新编号。"""
        try:
            df = df.reset_index(drop=True)
            df["序号"] = range(1, len(df) + 1)
            df.to_excel(self._cache_path, index=False)
        except Exception as e:
            log_error(f"写入标星缓存文件失败: {e}")

    # ── 公共接口 ────────────────────────────────────────────

    def add(self, name: str) -> None:
        """添加客户（已存在则忽略）。"""
        name = str(name).strip()
        if not name:
            return
        df = self._read()
        if not df[df["最终客户名称"] == name].empty:
            return
        df = pd.concat([df, pd.DataFrame([[0, name]], columns=_COLUMNS)], ignore_index=True)
        self._write(df)

    def add_batch(self, names: list[str]) -> int:
        """批量添加客户（已存在则跳过），返回新增数量。"""
        names = [str(n).strip() for n in names if str(n).strip()]
        if not names:
            return 0
        df = self._read()
        existing = set(df["最终客户名称"].tolist())
        new = [n for n in names if n not in existing]
        if not new:
            return 0
        new_df = pd.DataFrame({"序号": [0] * len(new), "最终客户名称": new})
        df = pd.concat([df, new_df], ignore_index=True)
        self._write(df)
        return len(new)

    def remove(self, name: str) -> None:
        """删除客户。"""
        name = str(name).strip()
        df = self._read()
        df = df[df["最终客户名称"] != name]
        self._write(df)

    def clear_all(self) -> int:
        """清空所有缓存，返回被清空的条目数。"""
        df = self._read()
        count = len(df)
        empty = pd.DataFrame(columns=_COLUMNS)
        self._write(empty)
        return count

    def contains(self, name: str) -> bool:
        """检查客户是否已标星。"""
        df = self._read()
        return not df[df["最终客户名称"] == str(name).strip()].empty

    def get_all(self) -> list[str]:
        """获取所有标星客户名称（有序）。"""
        df = self._read()
        return df["最终客户名称"].tolist()

    def get_dataframe(self) -> pd.DataFrame:
        """获取完整缓存表（序号 + 客户名称）。"""
        return self._read()
