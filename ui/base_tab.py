"""BaseTab —— 所有 Tab 页共用的 QTableView 创建/填充/排序逻辑"""

from __future__ import annotations

import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QLineEdit, QLabel, QFrame, QMessageBox,
    QStyle, QStyledItemDelegate,
)
from PySide6.QtCore import (
    Qt, QModelIndex, Signal, QEvent, QObject,
)
from PySide6.QtGui import (
    QStandardItemModel, QStandardItem, QColor, QFont, QPainter,
)

from ui.styles import (
    FONT_TABLE_HEADER, FONT_TABLE_BODY, T,
)
from ui.logger import log_info
from utils import export_to_csv


# ──────────────────────────────────────────────
#  Star 列委托
# ──────────────────────────────────────────────
class _StarDelegate(QStyledItemDelegate):
    """标星列自定义渲染：★/☆ + 点击切换"""

    def __init__(self, tab: "QtBaseTab", parent=None):
        super().__init__(parent)
        self._tab = tab

    def paint(self, painter, option, index):
        painter.save()
        if index.row() % 2 == 0:
            painter.fillRect(option.rect, QColor(T("table_even")))
        else:
            painter.fillRect(option.rect, QColor(T("table_odd")))

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(T("primary")))

        text = index.data(Qt.ItemDataRole.DisplayRole) or "☆"
        painter.setFont(QFont("Microsoft YaHei UI", 14))
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(QColor("white"))
        elif text == "★":
            painter.setPen(QColor("#F59E0B"))
        else:
            painter.setPen(QColor("#CBD5E1"))
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease:
            row = index.row()
            star_item = model.item(row, 0)
            if star_item is None:
                return False
            current = star_item.text()
            new_val = "☆" if current == "★" else "★"
            star_item.setText(new_val)
            if self._tab._star_toggle_callback:
                name_item = model.item(row, 2)
                if name_item:
                    self._tab._star_toggle_callback(
                        name_item.text(), new_val == "★"
                    )
            return True
        return super().editorEvent(event, model, option, index)


# ──────────────────────────────────────────────
#  Tab 搜索/导出/表格组合组件
# ──────────────────────────────────────────────
class TabSearchBar(QWidget):
    """搜索框 + 导出按钮横向布局"""

    search_changed = Signal(str)
    export_clicked = Signal()

    def __init__(self, placeholder: str = "搜索当前页面...", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(placeholder)
        self.search_edit.setFixedHeight(36)
        self.search_edit.setMinimumWidth(300)
        self.search_edit.textChanged.connect(self.search_changed.emit)
        layout.addWidget(self.search_edit, 1)

        self.export_btn = QPushButton("导出 CSV")
        self.export_btn.setObjectName("grayBtn")
        self.export_btn.setFixedHeight(36)
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.clicked.connect(self.export_clicked.emit)
        layout.addWidget(self.export_btn)

    def text(self) -> str:
        return self.search_edit.text()

    def clear(self):
        self.search_edit.clear()


# ──────────────────────────────────────────────
#  自定义 Header —— 禁止点击表头时选中整列（事件过滤器方式）
# ──────────────────────────────────────────────
class _HeaderClearFilter(QObject):
    """事件过滤器：点击表头后立刻清除整列选中，消除闪烁。"""

    def __init__(self, table: QTableView, parent=None):
        super().__init__(parent)
        self._table = table

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            obj.event(event)          # 正常交给 QHeaderView 处理（触发选中 + 排序信号）
            self._table.clearSelection()  # 紧随其后清除列选中
            return True               # 事件已处理，不再传播
        return False


# ──────────────────────────────────────────────
#  QtBaseTab
# ──────────────────────────────────────────────
class QtBaseTab:
    SEQ_COL = "#"
    STAR_COL = "★"

    def __init__(
        self,
        tab_name: str,
        columns: list[str],
        on_double_click=None,
        has_star: bool = False,
        on_star_toggle=None,
        get_starred_names=None,
        search_column: str | None = None,
    ):
        self.tab_name = tab_name
        self.columns = columns
        self.on_double_click_callback = on_double_click
        self.has_star = has_star
        self._star_toggle_callback = on_star_toggle
        self._get_starred = get_starred_names
        self._search_column = search_column

        self.frame: QWidget | None = None
        self.table: QTableView | None = None
        self.model: QStandardItemModel | None = None
        self.search_bar: TabSearchBar | None = None
        self.source_df: pd.DataFrame | None = None
        self.sort_col: str | None = None
        self.sort_asc: bool = True

        self._search_text: str = ""

    # ── UI 构建 ──

    def build(self) -> QWidget:
        """构建 Tab：搜索栏 + 表格（导出按钮在搜索栏内）。"""
        frame = QFrame()
        frame.setObjectName("card")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        if self._search_column:
            self.search_bar = TabSearchBar(
                placeholder=f"搜索 {self._search_column}...",
            )
            self.search_bar.search_changed.connect(self._on_search_changed)
            self.search_bar.export_clicked.connect(self._export_csv)
            outer.addWidget(self.search_bar)
        else:
            # 没有搜索列也要放导出按钮到右侧
            bar = QHBoxLayout()
            bar.addStretch()
            btn = QPushButton("导出 CSV")
            btn.setObjectName("grayBtn")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(self._export_csv)
            bar.addWidget(btn)
            bar_w = QWidget()
            bar_w.setLayout(bar)
            outer.addWidget(bar_w)

        # 表格
        self.table = QTableView()
        self.table.horizontalHeader().installEventFilter(_HeaderClearFilter(self.table, self.table.horizontalHeader()))
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setFont(FONT_TABLE_HEADER)
        self.table.setFont(FONT_TABLE_BODY)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.doubleClicked.connect(self._on_double_click)

        outer.addWidget(self.table, 1)

        self.frame = frame
        return frame

    # ── 搜索 ──

    def _on_search_changed(self, text: str):
        self._search_text = text.strip()
        self._apply_search_filter()

    def _apply_search_filter(self):
        if self.source_df is None:
            return
        self._fill_table(self.source_df.copy())

    def _get_filtered_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self._search_text or not self._search_column:
            return df
        if self._search_column not in df.columns:
            return df
        return df[df[self._search_column].astype(str).str.contains(
            self._search_text, case=False, na=False
        )]

    # ── 数据 ──

    def compute_data(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError

    def populate(self, df: pd.DataFrame):
        self.source_df = df.copy()
        self._fill_table(df)

    def _fill_table(self, df: pd.DataFrame):
        df = self._get_filtered_df(df)
        self._rebuild_model(df)

    def _rebuild_model(self, df: pd.DataFrame):
        df_cols = list(df.columns)
        starred = set(self._get_starred()) if self.has_star and self._get_starred else set()

        display_cols = []
        if self.has_star:
            display_cols.append(self.STAR_COL)
        display_cols.append(self.SEQ_COL)
        display_cols.extend(df_cols)

        model = QStandardItemModel(len(df), len(display_cols))
        model.setHorizontalHeaderLabels(display_cols)

        for row_idx, (_, row) in enumerate(df.iterrows()):
            col_offset = 0
            if self.has_star:
                name_val = str(row[df_cols[0]]) if df_cols else ""
                star = "★" if name_val in starred else "☆"
                item = QStandardItem(star)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                model.setItem(row_idx, 0, item)
                col_offset = 1

            seq_item = QStandardItem(str(row_idx + 1))
            seq_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            seq_item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
            model.setItem(row_idx, col_offset, seq_item)
            col_offset += 1

            for col_idx, col in enumerate(df_cols):
                val = row[col]
                text = self._format_cell(val)
                item = QStandardItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
                if isinstance(val, (int, float)) and not pd.isna(val):
                    item.setData(float(val), Qt.ItemDataRole.UserRole)
                model.setItem(row_idx, col_offset + col_idx, item)

        self.model = model
        self.table.setModel(model)

        if self.has_star:
            self.table.setItemDelegateForColumn(0, _StarDelegate(self, self.table))

        self.table.resizeColumnsToContents()
        # 标星列宽固定
        if self.has_star:
            self.table.setColumnWidth(0, 50)
        # 序号列固定
        seq_col_idx = 1 if self.has_star else 0
        self.table.setColumnWidth(seq_col_idx, 60)
        # 第一列（标星或序号）居中
        # 最后一列伸展
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)

        # 表头点击排序（只 connect 一次，避免每次 refresh 重复绑定）
        header.setSortIndicatorShown(True)
        if not getattr(self, '_header_connected', False):
            header.sectionClicked.connect(self._on_header_clicked)
            self._header_connected = True

        # 为第一个可排序列显示排序箭头，提示用户哪些列可排序
        self._show_sort_hint(header, df)

        # ── 排序箭头提示 ──

    def _show_sort_hint(self, header, df: pd.DataFrame):
        """在第一个可排序列上显示排序箭头（↑），提示用户该列可排序。
        如果用户已手动排过序，则保持之前的排序状态。"""
        if self.sort_col is not None:
            # 用户已排过序，保持当前排序列
            for col_idx in range(self.model.columnCount()):
                if self.model.headerData(col_idx, Qt.Orientation.Horizontal) == self.sort_col:
                    order = Qt.SortOrder.AscendingOrder if self.sort_asc else Qt.SortOrder.DescendingOrder
                    header.setSortIndicator(col_idx, order)
                    return
            # 排序列已不存在（罕见），fallback 到清空
            self.sort_col = None

        # 未排过序：在第一个可排序列上显示 ↑ 作为提示
        for col_idx in range(self.model.columnCount()):
            col_name = self.model.headerData(col_idx, Qt.Orientation.Horizontal)
            if col_name in (self.SEQ_COL, self.STAR_COL):
                continue
            if "名称" in col_name:
                continue
            if col_name in df.columns and pd.api.types.is_numeric_dtype(df[col_name].dtype):
                header.setSortIndicator(col_idx, Qt.SortOrder.AscendingOrder)
                return

        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)

    # ── 格式化 ──

    @staticmethod
    def _format_cell(val) -> str:
        if pd.isna(val):
            return ""
        if isinstance(val, float):
            return f"{val:,.2f}"
        if isinstance(val, int):
            return f"{val:,}"
        return str(val)

    # ── 排序 ──

    def _on_header_clicked(self, logical_index: int):
        if self.model is None:
            return

        header_labels = []
        for i in range(self.model.columnCount()):
            header_labels.append(self.model.headerData(i, Qt.Orientation.Horizontal))

        if logical_index < 0 or logical_index >= len(header_labels):
            return

        col_name = header_labels[logical_index]
        header = self.table.horizontalHeader()

        if col_name in (self.SEQ_COL, self.STAR_COL):
            header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            return
        if "名称" in col_name:
            header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            return

        # 只有数字列才能排序，文字列（如行业、客户名等）忽略
        if self.source_df is not None and col_name in self.source_df.columns:
            dtype = self.source_df[col_name].dtype
            if not pd.api.types.is_numeric_dtype(dtype):
                header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
                return

        if self.sort_col == col_name:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = col_name
            self.sort_asc = True

        direction = "升序" if self.sort_asc else "降序"
        log_info(f"排序 [{self.tab_name}]: {col_name} {direction}")

        order = Qt.SortOrder.AscendingOrder if self.sort_asc else Qt.SortOrder.DescendingOrder
        header.setSortIndicator(logical_index, order)

        if self.source_df is not None and col_name in self.source_df.columns:
            sorted_df = self.source_df.sort_values(
                col_name, ascending=self.sort_asc
            ).reset_index(drop=True)
            self._fill_table(sorted_df)

    # ── 双击 ──

    def _on_double_click(self, index):
        if self.on_double_click_callback:
            self.on_double_click_callback(self.table, index)

    # ── 导出 ──

    def _export_csv(self):
        if self.source_df is None or self.source_df.empty:
            QMessageBox.warning(self.frame, "提示", "没有数据可导出")
            return
        export_df = self._get_filtered_df(self.source_df)
        if export_df.empty:
            QMessageBox.warning(self.frame, "提示", "没有数据可导出")
            return
        log_info(f"导出CSV [{self.tab_name}]: {self.tab_name}.csv，共 {len(export_df)} 行")
        export_to_csv(export_df, self.frame, f"{self.tab_name}.csv")
