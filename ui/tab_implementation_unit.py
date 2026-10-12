"""实施单位统计 Tab —— 主文件「实施单位名称」维度的合同明细。

- 列：序号 / 最终客户名称 / 合同编码 / 实施情况 / 实施单位名称 / 合同金额 / 负责销售
- 搜索：顶部搜索框按「合同编码」模糊搜索
- 筛选：「实施情况」+「实施单位」两个筛选按钮，可叠加使用（AND）
- 导出：CSV（导出当前视图）
- 双击：打开该行合同的详情弹窗（按需求隐藏「导出 CSV」按钮）
- 「负责销售」：取自**主文件「合同负责人*」列**（主文件没有该列时整列为空）

按 `TAB_STYLE.md` 的 A 类骨架实现（继承 `QtBaseTab` + 统一 `FilterBar`）。
"""

from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt

from ui.base_tab import QtBaseTab
from ui.detail_window import CustomerDetailWindow
from ui.logger import log_info
from ui.msg_box import warn


class ImplementationUnitTab(QtBaseTab):
    """实施单位统计页 —— 按实施单位筛选的合同明细列表。"""

    SEQ_COL = "序号"          # 本页序号列按需求显示为「序号」
    DISPLAY_COLUMNS = [
        "最终客户名称", "合同编码", "实施情况", "实施单位名称", "合同金额", "负责销售",
    ]

    def __init__(self, on_double_click=None):
        super().__init__(
            tab_name="实施单位统计",
            columns=self.DISPLAY_COLUMNS,
            on_double_click=on_double_click,
            search_column="合同编码",          # 顶部搜索框：按合同编号模糊搜索
            filter_columns=[
                ("实施情况", "实施情况"),
                ("实施单位名称", "实施单位"),
            ],
        )
        self._main_df: pd.DataFrame | None = None       # 主文件原始行，供双击弹窗取明细

    # ── 数据 ──

    def compute_data(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        self._main_df = raw_df

        # 合同编号是行的身份；源表里可能夹着多余表头行（整行只有零星几个值），跳过
        contract = raw_df["合同编号*"].fillna("").astype(str).str.strip()
        valid = contract != ""
        skipped = int((~valid).sum())
        src = raw_df[valid]

        out = pd.DataFrame()
        out["最终客户名称"] = self._text_column(src, "最终客户名称")
        out["合同编码"] = contract[valid]
        out["实施情况"] = self._text_column(src, "实施情况")
        # 主文件没有「实施单位名称」列（旧版文件）时整列留空，筛选栏仍可用（只有「（空）」一项）
        out["实施单位名称"] = self._text_column(src, "实施单位名称")
        out["合同金额"] = pd.to_numeric(src["合同金额（元）*"], errors="coerce").fillna(0.0)
        out["负责销售"] = self._text_column(src, "合同负责人")   # 负责销售 ← 主文件「合同负责人*」

        out = self._sort_by_created(out, src)
        if skipped:
            log_info(f"实施单位统计: 跳过 {skipped} 行无合同编号的记录")
        log_info(
            f"实施单位统计完成: {len(out)} 条合同, "
            f"{out['实施单位名称'].nunique()} 个实施单位"
        )
        return out

    @staticmethod
    def _sort_by_created(out: pd.DataFrame, raw_df: pd.DataFrame) -> pd.DataFrame:
        """默认按「创建时间」倒序（越新越靠前）；缺失创建时间的行排最后。

        「创建时间」只作排序键、不作为展示列（展示列按需求固定为 6 列）。
        旧版文件没有该列时，退回按合同金额倒序。
        """
        if "创建时间" in raw_df.columns:
            try:
                created = pd.to_datetime(raw_df["创建时间"], errors="coerce")
                order = created.sort_values(
                    ascending=False, na_position="last", kind="mergesort"
                ).index
                return out.loc[order].reset_index(drop=True)
            except Exception as e:
                log_info(f"创建时间解析失败，改为按合同金额排序: {e}")
        return out.sort_values("合同金额", ascending=False).reset_index(drop=True)

    @staticmethod
    def _text_column(src: pd.DataFrame, column: str) -> pd.Series:
        """取主文件的文本列：缺失该列或值为空 → 空字符串。"""
        if column not in src.columns:
            return pd.Series(["" for _ in range(len(src))], index=src.index, dtype=object)
        return src[column].fillna("").astype(str).str.strip()

    # ── 双击：打开该行合同详情（沿用 Tab2 的弹窗，隐藏导出按钮）──

    def _on_double_click(self, index):
        if self.model is None or not index.isValid() or self._main_df is None:
            return

        headers = [
            str(self.model.headerData(c, Qt.Orientation.Horizontal) or "")
            for c in range(self.model.columnCount())
        ]
        row = {}
        for c, head in enumerate(headers):
            item = self.model.item(index.row(), c)
            row[head] = item.text() if item is not None else ""

        contract = str(row.get("合同编码", "")).strip()
        customer = str(row.get("最终客户名称", "")).strip()
        if not contract:
            return

        sub = self._main_df[self._main_df["合同编号*"].astype(str).str.strip() == contract]
        if sub.empty:
            warn(self.frame, "提示", f"未在主文件中找到合同：{contract}")
            return

        log_info(f"实施单位统计双击: 合同 {contract}（{customer}）")
        CustomerDetailWindow.show(
            self.frame.window(), sub,
            f"合同详情 — {contract}",
            customer or contract,
            show_export=False,
        )
