"""统一筛选栏组件 —— 所有需要"列筛选"的页面都用它。

对应 `TAB_STYLE.md` §3 的 S3：
按钮文案 `▽ 列名` / 激活后 `▼ 列名(N)` 并高亮、值列表含「（空）」、
多选弹窗统一用 `ColumnFilterPopup`、`清除筛选` 仅在存在激活筛选时显示。

**禁止再手写筛选按钮栏**（现有 Tab3/Tab4 的写法属历史遗留，见 TAB_STYLE.md §6）。
"""

from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ui.column_filter_popup import ColumnFilterPopup

EMPTY_LABEL = "（空）"


def normalize_empty(series: pd.Series) -> pd.Series:
    """空值统一成「（空）」：NaN 与空字符串都算空（见 TAB_STYLE.md S3）。

    取值与筛选比较必须走同一个函数，否则「（空）」筛不出结果。
    """
    return series.fillna(EMPTY_LABEL).astype(str).replace({"": EMPTY_LABEL})


class FilterBar(QWidget):
    """筛选按钮栏。

    参数:
        values_provider: 回调 `(col) -> list[str]`，返回该列全部可选值（需含「（空）」）。
                         可直接用 `FilterBar.column_values(series)` 生成。
        on_change:       回调 `(active: dict[str, set]) -> None`，筛选变化后触发，
                         页面据此重新过滤并刷新表格。
        label:           前缀文案，默认「筛选：」。
    """

    def __init__(self, values_provider=None, on_change=None, label: str = "筛选：", parent=None):
        super().__init__(parent)
        self._values_provider = values_provider
        self._on_change = on_change
        self._columns: list[tuple[str, str]] = []
        self._buttons: dict[str, QPushButton] = {}
        self._active: dict[str, set] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._label = QLabel(label)
        self._label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self._label)

        layout.addStretch()

        self._clear_btn = QPushButton("清除筛选")
        self._clear_btn.setObjectName("ghostBtn")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self.clear)
        self._clear_btn.setVisible(False)
        layout.addWidget(self._clear_btn)

    # ── 对外接口 ──

    @property
    def active_filters(self) -> dict[str, set]:
        """当前激活的筛选：`{列名: 选中值集合}`（未激活的列不出现）。"""
        return {col: set(sel) for col, sel in self._active.items()}

    @staticmethod
    def column_values(series) -> list[str]:
        """统一的取值方式：NaN/空串 → 「（空）」，去重排序。"""
        return sorted(normalize_empty(series).unique().tolist())

    def set_columns(self, columns):
        """声明筛选项：`[(列名, 显示名), ...]`；也可直接传 `["列名", ...]`。"""
        for btn in self._buttons.values():
            btn.deleteLater()
        self._buttons.clear()
        self._columns.clear()
        self._active.clear()

        for item in columns:
            col, disp = item if isinstance(item, (tuple, list)) else (item, item)
            self._columns.append((col, disp))
            btn = QPushButton(f"▽ {disp}")
            btn.setObjectName("filterBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, c=col: self._open(c))
            self._insert_before_stretch(btn)
            self._buttons[col] = btn
        self.refresh()

    def set_active(self, col: str, selected) -> None:
        """以代码方式设置某列筛选（用于"是否续保""年份"等特殊筛选）。

        与用户点击筛选一样，会触发 `on_change` 让页面刷新表格。
        """
        if selected:
            self._active[col] = set(selected)
        else:
            self._active.pop(col, None)
        self.refresh()
        self._notify()

    def refresh(self) -> None:
        """同步按钮文案 / 选中态 / 「清除筛选」按钮显隐。"""
        for col, btn in self._buttons.items():
            sel = self._active.get(col)
            disp = self._display(col)
            if sel:
                btn.setText(f"▼ {disp}({len(sel)})")
                btn.setChecked(True)
            else:
                btn.setText(f"▽ {disp}")
                btn.setChecked(False)
        self._clear_btn.setVisible(bool(self._active))

    def clear(self) -> None:
        """清空全部筛选。"""
        if not self._active:
            return
        self._active.clear()
        self.refresh()
        self._notify()

    def select_all(self) -> None:
        """重置为"未筛选"状态（不触发回调）。"""
        self._active.clear()
        self.refresh()

    # ── 内部 ──

    def _display(self, col: str) -> str:
        for c, disp in self._columns:
            if c == col:
                return disp
        return str(col)

    def _values(self, col: str) -> list[str]:
        if self._values_provider is None:
            return []
        values = list(self._values_provider(col) or [])
        if EMPTY_LABEL not in values:
            values.append(EMPTY_LABEL)
        return values

    def _insert_before_stretch(self, widget: QWidget) -> None:
        layout = self.layout()
        for i in range(layout.count()):
            if layout.itemAt(i).spacerItem():
                layout.insertWidget(i, widget)
                return
        layout.addWidget(widget)

    def _open(self, col: str) -> None:
        values = self._values(col)
        if not values:
            return
        selected = self._active.get(col, set(values))
        ColumnFilterPopup(
            self.window(), self._display(col), values, selected,
            on_apply=lambda _, sel: self._apply(col, sel, values),
        )

    def _apply(self, col: str, selected, all_values) -> None:
        selected = set(selected)
        # 全选 / 空选都视为"未筛选"，与既有行为保持一致
        if not selected or selected >= set(all_values):
            self._active.pop(col, None)
        else:
            self._active[col] = selected
        self.refresh()
        self._notify()

    def _notify(self) -> None:
        if self._on_change is not None:
            self._on_change(self.active_filters)
