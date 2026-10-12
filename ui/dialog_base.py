"""弹窗统一基类 —— 「按钮打开的列表页 / 下钻页 / 录入表单」都从这里派生。

对应 `TAB_STYLE.md` §2.2–§2.4 与 S8：
一律**模态** `exec()`、一律提供静态 `show()` 入口、
统一 `configure_dialog` + `install_close_handler`、统一底部按钮栏与导出按钮样式。

子类约定：
- `__init__` 必须接受 `parent` 关键字参数（`show()` 依赖它）；
- **若 `title()` 需要读自身属性，必须先赋值再调用 `super().__init__()`**；
- 覆写 `build_body()` / `build_toolbar()` 组装内容，不要自己 new `QDialog`。
"""

from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout,
)

from ui.dialog_utils import configure_dialog, install_close_handler
from ui.filter_bar import EMPTY_LABEL, FilterBar, normalize_empty
from ui.logger import log_info
from ui.msg_box import warn
from ui.table_kit import (
    SEQ_COL, apply_column_widths, build_table_view, format_cell, is_sortable_column,
)
from utils import center_window, export_to_csv

DEFAULT_SIZE = (960, 620)
FORM_SIZE = (560, 420)


# ──────────────────────────────────────────────
#  BaseDialog
# ──────────────────────────────────────────────
class BaseDialog:
    """弹窗基类（组合式：内部持有 `self.dialog` 这个 QDialog）。"""

    def __init__(self, parent=None, title: str = "", size: tuple[int, int] = DEFAULT_SIZE):
        self._parent = parent
        self.dialog = QDialog(parent)
        configure_dialog(self.dialog)
        install_close_handler(self.dialog)
        self.dialog.setWindowTitle(title or self.title())

        self.layout = QVBoxLayout(self.dialog)
        self.layout.setContentsMargins(14, 14, 14, 14)
        self.layout.setSpacing(10)
        self._size = size

    # ── 子类覆写点 ──

    def title(self) -> str:
        return ""

    def build_body(self) -> None:
        """构建主体内容（往 `self.layout` 里加）。"""

    def build_toolbar(self, bar: QHBoxLayout) -> None:
        """在底部按钮栏追加按钮（bar 已右对齐，默认还会追加「关闭」）。"""

    def default_close_text(self) -> str | None:
        """默认的关闭按钮文案；返回 None 表示由子类自己提供按钮。"""
        return "关闭"

    # ── 公共能力 ──

    @staticmethod
    def make_button(text: str, object_name: str = "grayBtn", on_click=None) -> QPushButton:
        """按 S7 的 objectName 规范创建按钮。"""
        btn = QPushButton(text)
        btn.setObjectName(object_name)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if on_click is not None:
            btn.clicked.connect(on_click)
        return btn

    def build(self) -> QDialog:
        self.build_body()
        bar = QHBoxLayout()
        bar.addStretch()
        self.build_toolbar(bar)
        text = self.default_close_text()
        if text:
            bar.addWidget(self.make_button(text, "grayBtn", self.dialog.reject))
        self.layout.addLayout(bar)

        width, height = self._size
        center_window(self.dialog, width, height)
        return self.dialog

    def exec(self) -> int:
        return self.dialog.exec()

    def close(self) -> None:
        self.dialog.reject()

    @classmethod
    def show(cls, parent=None, **kwargs):
        """统一入口：`XxxDialog.show(parent, **kwargs)`。"""
        dlg = cls(parent=parent, **kwargs)
        dlg.build()
        return dlg.exec()


# ──────────────────────────────────────────────
#  ListDialog —— B 类：按钮打开的一张表
# ──────────────────────────────────────────────
class ListDialog(BaseDialog):
    """列表弹窗：标题 + 可选搜索框 + 可选筛选栏 + 表格 + 底部按钮栏。

    子类覆写：
      - `get_dataframe()`         必须，返回要展示的 DataFrame
      - `column_spec()`           展示列（默认取全部列）
      - `search_column()`         需要搜索框时返回列名
      - `filter_column_spec()`    需要筛选栏时返回 `[(列名, 显示名), ...]`
      - `on_row_activated(row)`   双击某行时的回调（row 为 `{列名: 文本}`）
      - `enable_export()`         是否提供「导出 CSV」
    """

    def __init__(self, parent=None, title: str = "", size: tuple[int, int] = DEFAULT_SIZE):
        super().__init__(parent=parent, title=title, size=size)
        self.table = None
        self.model = None
        self._df = pd.DataFrame()
        self._bar: FilterBar | None = None
        self._search: QLineEdit | None = None
        self.sort_col: str | None = None
        self.sort_asc: bool = True

    # ── 子类覆写点 ──

    def get_dataframe(self) -> pd.DataFrame:
        raise NotImplementedError

    def column_spec(self) -> list[str]:
        return list(self._df.columns)

    def search_column(self) -> str | None:
        return None

    def filter_column_spec(self) -> list:
        return []

    def on_row_activated(self, row: dict) -> None:
        """双击某行。`row` 的键是显示列名，值是单元格文本。"""

    def enable_export(self) -> bool:
        return True

    # ── 主体构建 ──

    def build_body(self) -> None:
        self._df = self.get_dataframe()
        if self._df is None:
            self._df = pd.DataFrame()

        search_col = self.search_column()
        if search_col:
            self._search = QLineEdit()
            self._search.setPlaceholderText(f"搜索 {search_col}...")
            self._search.setFixedHeight(36)
            self._search.textChanged.connect(lambda _text: self._rebuild())
            self.layout.addWidget(self._search)

        filters = list(self.filter_column_spec())
        if filters:
            self._bar = FilterBar(
                values_provider=self._filter_values,
                on_change=lambda _active: self._rebuild(),
                parent=self.dialog,
            )
            self._bar.set_columns(filters)
            self.layout.addWidget(self._bar)

        self.table = build_table_view(self.dialog)
        self.table.doubleClicked.connect(self._on_double_click)
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_header_clicked)
        self.layout.addWidget(self.table, 1)

        self._rebuild()

    def build_toolbar(self, bar: QHBoxLayout) -> None:
        if self.enable_export():
            bar.addWidget(self.make_button("导出 CSV", "accentBtn", self._export_csv))

    # ── 数据 ──

    def _search_text(self) -> str:
        return self._search.text().strip() if self._search is not None else ""

    def _pass_filter(self, df: pd.DataFrame, filters: dict) -> pd.DataFrame:
        for col, selected in filters.items():
            if col in df.columns:
                df = df[normalize_empty(df[col]).isin(selected)]
        return df

    def _current_df(self) -> pd.DataFrame:
        """当前视图的数据（搜索 + 筛选后）。"""
        df = self._df
        if df is None or df.empty:
            return pd.DataFrame() if df is None else df
        if self._bar is not None:
            df = self._pass_filter(df, self._bar.active_filters)
        text = self._search_text()
        col = self.search_column()
        if text and col and col in df.columns:
            df = df[df[col].astype(str).str.contains(text, case=False, na=False)]
        return df

    def _filter_values(self, col: str) -> list[str]:
        """级联取值：计算某列可选值时跳过该列自身的筛选。"""
        if col not in self._df.columns:
            return []
        df = self._df
        if self._bar is not None:
            others = {c: s for c, s in self._bar.active_filters.items() if c != col}
            df = self._pass_filter(df, others)
        return FilterBar.column_values(df[col])

    def _rebuild(self) -> None:
        if self.table is None:
            return
        df = self._current_df()
        if self.sort_col and self.sort_col in df.columns:
            df = df.sort_values(self.sort_col, ascending=self.sort_asc).reset_index(drop=True)

        cols = [c for c in self.column_spec() if c in df.columns]
        display = [SEQ_COL] + cols
        model = QStandardItemModel(len(df), len(display))
        model.setHorizontalHeaderLabels(display)

        pos = [df.columns.get_loc(c) for c in cols]
        for row_idx, row in enumerate(df.itertuples(index=False)):
            seq = QStandardItem(str(row_idx + 1))
            seq.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            seq.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
            model.setItem(row_idx, 0, seq)
            for i, p in enumerate(pos):
                item = QStandardItem(format_cell(row[p]))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
                model.setItem(row_idx, i + 1, item)

        self.model = model
        self.table.setModel(model)
        apply_column_widths(self.table, model)

    # ── 交互 ──

    def _header_label(self, logical_index: int) -> str:
        if self.model is None:
            return ""
        return str(self.model.headerData(
            logical_index, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
        ) or "")

    def _on_header_clicked(self, logical_index: int) -> None:
        if self.model is None:
            return
        header = self.table.horizontalHeader()
        label = self._header_label(logical_index)
        # 统一排序规则（TAB_STYLE.md S4）：只有数字列可排序
        if not is_sortable_column(self._df, label):
            header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            return
        if self.sort_col == label:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = label
            self.sort_asc = True
        order = Qt.SortOrder.AscendingOrder if self.sort_asc else Qt.SortOrder.DescendingOrder
        header.setSortIndicator(logical_index, order)
        self._rebuild()

    def _on_double_click(self, index) -> None:
        if self.model is None or not index.isValid():
            return
        row = {
            self._header_label(c): self.model.data(self.model.index(index.row(), c))
            for c in range(self.model.columnCount())
        }
        log_info(f"[{self.dialog.windowTitle()}] 双击行: {row}")
        self.on_row_activated(row)

    def _export_csv(self) -> None:
        df = self._current_df()
        if df is None or df.empty:
            warn(self.dialog, "提示", "没有数据可导出")
            return
        export_to_csv(df, self.dialog, f"{self.dialog.windowTitle()}.csv")


# ──────────────────────────────────────────────
#  DrillDownDialog —— C 类：继续下钻
# ──────────────────────────────────────────────
class DrillDownDialog(ListDialog):
    """下钻弹窗：面包屑标题 + 双击进入下一层。

    子类覆写：
      - `breadcrumb()`      返回层级名列表，如 `["行业统计", "制造业"]` → 标题「行业统计 / 制造业」
      - `on_drill_down(row)` 双击某行时打开下一层
      - 其余同 `ListDialog`

    只传标识（字符串）+ 数据源，子窗口自行重查，不跨窗口直传 DataFrame。
    """

    def breadcrumb(self) -> list[str]:
        return []

    def on_drill_down(self, row: dict) -> None:
        """双击进入下一层。"""

    def title(self) -> str:
        parts = [p for p in self.breadcrumb() if p]
        return " / ".join(parts) if parts else super().title()

    def on_row_activated(self, row: dict) -> None:
        self.on_drill_down(row)


# ──────────────────────────────────────────────
#  FormDialog —— D 类：录入 / 编辑
# ──────────────────────────────────────────────
class FormDialog(BaseDialog):
    """表单弹窗：取消 / 确定，提交前统一校验。

    子类覆写：
      - `build_form(layout)`  放置表单控件
      - `validate()`          返回错误文案则拒绝提交（弹 `warn`），返回 None 通过
      - `collect()`           校验通过后收集返回值，存到 `self.result_value`
    """

    def __init__(self, parent=None, title: str = "", size: tuple[int, int] = FORM_SIZE):
        super().__init__(parent=parent, title=title, size=size)
        self.result_value = None

    # ── 子类覆写点 ──

    def build_form(self, layout: QVBoxLayout) -> None:
        """构建表单控件。"""

    def validate(self) -> str | None:
        return None

    def collect(self):
        return None

    # ── 组装 ──

    def build_body(self) -> None:
        self.build_form(self.layout)

    def build_toolbar(self, bar: QHBoxLayout) -> None:
        bar.addWidget(self.make_button("取消", "ghostBtn", self.dialog.reject))
        bar.addWidget(self.make_button("确定", "accentBtn", self._on_ok))

    def default_close_text(self) -> str | None:
        # 表单弹窗用「取消 / 确定」，不再额外加「关闭」
        return None

    def _on_ok(self) -> None:
        error = self.validate()
        if error:
            warn(self.dialog, "提示", error)
            return
        self.result_value = self.collect()
        self.dialog.accept()

    @classmethod
    def show(cls, parent=None, **kwargs):
        """统一入口，返回 `collect()` 的结果（取消则为 None）。"""
        dlg = cls(parent=parent, **kwargs)
        dlg.build()
        dlg.exec()
        return dlg.result_value
