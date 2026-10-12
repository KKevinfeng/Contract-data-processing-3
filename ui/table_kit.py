"""表格统一构建工具 —— 所有 Tab / 弹窗的 QTableView 都必须从本模块创建。

对应 `TAB_STYLE.md` §3 的 S4（排序规则）、S5（列宽）、S6（格式化）、S12（枚举包装）。
"""

from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt, QEvent, QObject
from PySide6.QtWidgets import QTableView, QWidget

from ui.logger import log_error
from ui.styles import FONT_TABLE_HEADER, FONT_TABLE_BODY

# ── 统一约定 ──
SEQ_COL = "#"
SEQ_COL_CN = "序号"            # 序号列的中文写法（个别页面按需求使用）
STAR_COL = "★"
SKIP_SORT_COLUMNS = (SEQ_COL, SEQ_COL_CN, STAR_COL)
NAME_KEYWORD = "名称"          # 含"名称"的列不可排序
WIDTH_SAMPLE_ROWS = 50         # 超过此行数改为按前 N 行估算列宽
MAX_COLUMN_WIDTH = 500         # 单列宽度上限（px）
FIXED_WIDTHS = {STAR_COL: 50, SEQ_COL: 60, SEQ_COL_CN: 60}
ROW_HEIGHT = 36


class HeaderClearFilter(QObject):
    """事件过滤器：点击表头后立刻清除整列选中，消除整列高亮的闪烁。"""

    def __init__(self, table: QTableView, parent=None):
        super().__init__(parent)
        self._table = table

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            obj.event(event)               # 正常交给 QHeaderView 处理（触发排序信号）
            self._table.clearSelection()   # 紧随其后清除整列选中
            return True                    # 事件已处理，不再传播
        return False


def build_table_view(parent: QWidget | None = None) -> QTableView:
    """按统一风格创建 QTableView（对齐方式 / 行高 / 字体 / 无网格 / 交替行色）。"""
    table = QTableView(parent)
    table.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
    table.setFont(FONT_TABLE_BODY)
    table.setShowGrid(False)
    table.setAlternatingRowColors(True)

    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setFont(FONT_TABLE_HEADER)
    header.installEventFilter(HeaderClearFilter(table, header))
    return table


def is_sortable_column(df: pd.DataFrame | None, col_name: str) -> bool:
    """统一排序规则：仅数字列可排序；`#` / `★` / 含"名称"的列一律不可排序。

    见 TAB_STYLE.md S4。**禁止在业务代码里另写一套判定。**
    """
    if not col_name or col_name in SKIP_SORT_COLUMNS:
        return False
    if NAME_KEYWORD in str(col_name):
        return False
    if df is None or col_name not in df.columns:
        return False
    try:
        return bool(pd.api.types.is_numeric_dtype(df[col_name].dtype))
    except Exception:
        return False


def format_cell(val) -> str:
    """统一单元格格式化：空值 → ""，float → 2 位小数，int → 千分位。

    见 TAB_STYLE.md S6。自定义格式请覆写基类的 `_fmt_val`。
    """
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, float):
        return f"{val:,.2f}"
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


def apply_column_widths(
    table: QTableView,
    model,
    *,
    sample_rows: int = WIDTH_SAMPLE_ROWS,
    max_width: int = MAX_COLUMN_WIDTH,
) -> None:
    """统一列宽策略。见 TAB_STYLE.md S5。

    - 行数 ≤ `sample_rows`：全量 `resizeColumnsToContents()`，保证小表最贴合内容；
    - 行数 >  `sample_rows`：只按「表头 + 前 N 行」估算，避免 10 万行 × 多列的全量计算卡住主线程；
    - `★` / `#` 列固定宽度；最后一列伸展。

    **禁止在业务代码里手写 `resizeColumnsToContents()` 或列宽设置。**
    """
    if table is None or model is None:
        return
    try:
        rows = model.rowCount()
        cols = model.columnCount()
        if cols == 0:
            return

        if rows <= sample_rows:
            table.resizeColumnsToContents()
        else:
            header = table.horizontalHeader()
            fm = header.fontMetrics()
            for col in range(cols):
                title = model.headerData(
                    col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
                )
                width = fm.horizontalAdvance(str(title or ""))
                for r in range(min(sample_rows, rows)):
                    text = model.data(model.index(r, col))
                    if text:
                        width = max(width, fm.horizontalAdvance(str(text)))
                header.resizeSection(col, min(width + 24, max_width))

        for col in range(cols):
            label = model.headerData(
                col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
            )
            if label in FIXED_WIDTHS:
                table.setColumnWidth(col, FIXED_WIDTHS[label])

        table.horizontalHeader().setStretchLastSection(True)
    except Exception as e:
        # 列宽属于纯展示逻辑，失败不应影响数据展示
        log_error(f"列宽自适应失败: {e}")


def display_columns(df: pd.DataFrame) -> list[str]:
    """统一的展示列顺序：`#` 序号列 + 数据列。"""
    return [SEQ_COL] + list(df.columns)
