"""统一 UI 套件 —— 新页面**只从本模块取公共能力**，细则见仓库根目录 `TAB_STYLE.md`。

用法::

    from ui.ui_kit import (
        QtBaseTab,                     # A 类：主 Tab
        ListDialog, DrillDownDialog,   # B / C 类：列表弹窗、下钻弹窗
        FormDialog,                    # D 类：录入表单
        FilterBar,                     # 筛选栏
        build_table_view, apply_column_widths, is_sortable_column, format_cell,
        confirm, info, warn, error,    # 中文提示弹窗
    )

本模块只是「统一出口」，具体实现分散在 `base_tab` / `table_kit` / `filter_bar` /
`dialog_base` / `column_filter_popup` / `msg_box`。
"""

from ui.base_tab import QtBaseTab, TabSearchBar
from ui.column_filter_popup import ColumnFilterPopup
from ui.dialog_base import BaseDialog, DrillDownDialog, FormDialog, ListDialog
from ui.dialog_utils import configure_dialog, install_close_handler
from ui.filter_bar import EMPTY_LABEL, FilterBar
from ui.msg_box import confirm, error, info, warn
from ui.table_kit import (
    FIXED_WIDTHS,
    MAX_COLUMN_WIDTH,
    SEQ_COL,
    STAR_COL,
    apply_column_widths,
    build_table_view,
    format_cell,
    is_sortable_column,
)

__all__ = [
    # A 类：主 Tab
    "QtBaseTab", "TabSearchBar",
    # B / C / D 类：弹窗
    "BaseDialog", "ListDialog", "DrillDownDialog", "FormDialog",
    # 筛选
    "FilterBar", "ColumnFilterPopup", "EMPTY_LABEL",
    # 表格
    "build_table_view", "apply_column_widths", "is_sortable_column", "format_cell",
    "SEQ_COL", "STAR_COL", "MAX_COLUMN_WIDTH", "FIXED_WIDTHS",
    # 提示与弹窗工具
    "confirm", "info", "warn", "error",
    "configure_dialog", "install_close_handler",
]
