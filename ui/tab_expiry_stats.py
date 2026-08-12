"""Tab 3：过保情况统计 (PySide6 版本) —— 独立导入 Excel 并展示"""

from __future__ import annotations

import math
import threading

import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QLineEdit, QLabel, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont

from ui.expiry_starred_view import ExpiryStarredView
from ui.progress_popup import ProgressPopup
from ui.column_filter_popup import ColumnFilterPopup
from ui import cache_manager
from ui.logger import log_error, log_info
from utils import classify_contract, export_to_csv


class ExpiryStatsTab:
    """过保情况统计页 —— 自带导入按钮，展示独立 Excel 数据。"""

    SEQ_COL = "#"
    FILTER_KEYWORDS = ["客户意向", "不续保原因"]

    def __init__(self, starred_cache=None):
        self.starred_cache = starred_cache
        self.frame: QWidget | None = None
        self.table: QTableView | None = None
        self.file_path: str = ""
        self.source_df: pd.DataFrame | None = None
        self.columns_display: list[str] = []
        self.sort_col: str | None = None
        self.sort_asc: bool = True
        self.active_filters: dict[str, set] = {}
        self.filter_btns: dict[str, QPushButton] = {}
        self._on_data_change = None
        self.load_from_cache = False  # 启动自动加载缓存标记

    def build(self) -> QWidget:
        frame = QWidget()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # ── 导入栏 ──
        import_bar = QHBoxLayout()
        import_bar.addWidget(QLabel("过保文件:"))

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setFixedHeight(32)
        self.file_path_edit.setStyleSheet(
            "QLineEdit { border: 1px solid #D0D0D0; border-radius: 6px; padding: 4px 8px; }"
        )
        import_bar.addWidget(self.file_path_edit, 1)

        browse_btn = QPushButton("浏览...")
        browse_btn.setObjectName("grayBtn")
        browse_btn.setFixedSize(80, 32)
        browse_btn.clicked.connect(self._browse_file)
        import_bar.addWidget(browse_btn)

        starred_btn = QPushButton("筛选重点客户过保合同")
        starred_btn.setObjectName("grayBtn")
        starred_btn.setFixedSize(180, 32)
        starred_btn.clicked.connect(self._filter_starred_expiry)
        import_bar.addWidget(starred_btn)

        layout.addLayout(import_bar)

        # ── 筛选栏（动态构建）──
        self.filter_layout = QHBoxLayout()
        layout.addLayout(self.filter_layout)

        # ── 表格 ──
        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_click)
        layout.addWidget(self.table, 1)

        # ── 导出按钮 ──
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        export_btn = QPushButton("导出 CSV")
        export_btn.setObjectName("accentBtn")
        export_btn.clicked.connect(self._export_csv)
        btn_bar.addWidget(export_btn)
        layout.addLayout(btn_bar)

        self.frame = frame
        return frame

    # ── 文件加载 ──

    def _browse_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self.frame, "选择过保情况统计文件", "",
            "Excel 文件 (*.xlsx *.xls);;所有文件 (*.*)",
        )
        if filepath:
            self.file_path_edit.setText(filepath)
            self._load_file()

    def _progress_popup(self):
        """获取当前应显示进度的弹窗。

        缓存加载时返回 None：过保数据不参与启动弹窗的进度更新，
        避免与主数据并发时进度互相覆盖（回退/往复）。进度条统一由主数据驱动。
        人工导入时返回自建弹窗正常显示分步进度。
        """
        if self.load_from_cache:
            return None
        return getattr(self, "_popup", None)

    def _load_file(self):
        filepath = self.file_path_edit.text().strip()
        if not filepath:
            QMessageBox.warning(self.frame, "提示", "请先选择 Excel 文件")
            return

        if getattr(self, "_loading", False):
            return
        self._loading = True

        self._load_error = None
        self._load_df = None

        if self.load_from_cache:
            # 缓存加载：复用主窗口启动弹窗，不再新建弹窗
            self._popup = None
            splash = self._progress_popup()
            if splash is not None:
                splash.set_progress(0.0, "正在读取过保历史数据...")
        else:
            self._popup = ProgressPopup(self.frame, title="正在导入过保情况数据...")
            self._popup.set_progress(0.0, "正在读取文件...")

        def worker():
            try:
                df = pd.read_excel(filepath)
                if df.empty:
                    self._load_error = "文件内容为空"
                    return
                self._load_df = df
                log_info(f"过保情况文件加载成功: {filepath}，共 {len(df)} 行")
            except Exception as e:
                self._load_error = f"加载文件失败：\n{e}"

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        QTimer.singleShot(50, lambda: self._poll_file_read(thread))

    def _load_from_cache_path(self, path: str):
        """启动自动加载过保缓存（独立于人工导入，避免与 _load_file 的 _loading 冲突）。"""
        if self.source_df is not None or getattr(self, "_loading", False):
            return
        self.file_path_edit.setText(path)
        self.load_from_cache = True
        self._load_file()

    def _poll_file_read(self, thread):
        # 缓存加载被用户取消：停止轮询，保留已加载的数据（如有）
        if self.load_from_cache:
            top = self.frame.window() if self.frame else None
            if top is not None and getattr(top, "_cache_load_cancelled", False):
                self._loading = False
                self.load_from_cache = False
                if self.source_df is None and self._load_df is not None:
                    self.source_df = self._load_df
                return
        if thread.is_alive():
            popup = self._progress_popup()
            if popup is not None:
                # 读取阶段（实际 0.05）。缓存模式：显示 = 实际 × 2，封顶 0.95
                show = 0.05 if not self.load_from_cache else min(0.05 * 2.0, 0.95)
                popup.set_progress(show, "正在读取 Excel 文件...")
            QTimer.singleShot(50, lambda: self._poll_file_read(thread))
            return

        if self._load_error:
            # 人工导入时关闭自建弹窗；缓存加载时自建弹窗为 None，启动弹窗由协调器统一处理
            if not self.load_from_cache and self._popup is not None:
                self._popup.close()
            self._loading = False
            # 若本次加载的是缓存且失败，清除该无效缓存，避免下次反复读取
            if self.load_from_cache:
                self.load_from_cache = False
                cache_manager.remove_expiry_cache()
                # 通知主窗口协调器（避免启动弹窗悬挂）
                top = self.frame.window() if self.frame else None
                if top is not None and hasattr(top, "_on_cache_load_item_done"):
                    top._on_cache_load_item_done()
            QTimer.singleShot(100, lambda: QMessageBox.critical(self.frame, "错误", self._load_error))
            return

        self.source_df = self._load_df
        self.active_filters.clear()
        self.sort_col = None
        self.sort_asc = True

        popup = self._progress_popup()
        if popup is not None:
            show = 0.10 if not self.load_from_cache else min(0.10 * 2.0, 0.95)
            popup.set_progress(show, "正在处理过保数据...")
        self._fill_table(self._load_df)
        # 缓存模式：不在此处设 100%（避免与主数据并发回退），由 _finish_cache_load 统一关闭
        if not self.load_from_cache:
            if popup is not None:
                popup.set_progress(1.0, "加载完成！")
            if self._popup is not None:
                self._popup.close()
        self._loading = False

        # 人工导入成功：写入缓存目录（自动加载缓存时不重复写）
        was_from_cache = self.load_from_cache
        if not self.load_from_cache:
            cache_manager.write_cache(self.file_path_edit.text(), "expiry")
        self.load_from_cache = False

        self._build_filter_bar()
        log_info(f"过保情况表格渲染完成，共 {len(self._load_df)} 行")

        # 若本次从缓存加载，通知主窗口的启动弹窗协调器
        if was_from_cache and self.frame is not None:
            top = self.frame.window()
            if hasattr(top, "_on_cache_load_item_done"):
                top._on_cache_load_item_done()

        if self._on_data_change:
            self._on_data_change()

    # ── 筛选重点客户 ──

    def _filter_starred_expiry(self):
        df = self.source_df
        if df is None:
            QMessageBox.warning(self.frame, "提示", "请先导入过保情况数据")
            return
        if self.starred_cache is None:
            QMessageBox.warning(self.frame, "提示", "缓存功能未初始化")
            return

        starred_names = self.starred_cache.get_all()
        if not starred_names:
            QMessageBox.warning(self.frame, "提示", "暂无重点客户")
            return

        gift_col = enduser_col = contract_col = None
        for col in df.columns:
            col_str = str(col).replace("\n", " ")
            if gift_col is None and "渠道大礼包最终客户" in col_str:
                gift_col = col
            if enduser_col is None and "最终客户" in col_str and "大礼包" not in col_str:
                enduser_col = col
            if contract_col is None and ("合同编号" in col_str or "合同编码" in col_str):
                contract_col = col

        if contract_col is None:
            QMessageBox.critical(self.frame, "错误", "未找到合同编号列")
            return

        starred_set = set(starred_names)
        mask = pd.Series(False, index=df.index)
        if gift_col:
            mask = mask | df[gift_col].isin(starred_set)
        if enduser_col:
            unmatched = ~mask
            mask = mask | df.loc[unmatched, enduser_col].isin(starred_set).reindex(df.index, fill_value=False)

        filtered = df[mask].copy()
        if filtered.empty:
            QMessageBox.information(self.frame, "提示", "没有找到重点客户的过保合同")
            return

        filtered["_type"] = filtered[contract_col].apply(classify_contract)
        filtered = filtered[filtered["_type"] == "P"].drop(columns=["_type"])
        if filtered.empty:
            QMessageBox.information(self.frame, "提示", "重点客户无 P 类合同")
            return

        top = self.frame.window()
        ExpiryStarredView.show(top, filtered)

    # ── 表格 ──

    @staticmethod
    def _reorder_columns(columns) -> list:
        cols = list(columns)
        priority = []
        for kw in ["过保日期", "客户意向", "不续保原因"]:
            for c in cols:
                if kw in str(c) and c not in priority:
                    priority.append(c)
                    break
        result = [c for c in priority if c in cols]
        result += [c for c in cols if c not in result]
        return result

    def _fill_table(self, df: pd.DataFrame):
        self._display_df = df.copy()
        reordered = self._reorder_columns(list(df.columns))
        display = [self.SEQ_COL] + reordered
        self.columns_display = display

        model = QStandardItemModel(len(df), len(display))
        model.setHorizontalHeaderLabels(display)

        for row_idx, (_, row) in enumerate(df.iterrows()):
            # 序号
            item = QStandardItem(str(row_idx + 1))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
            model.setItem(row_idx, 0, item)

            for col_idx, col in enumerate(reordered):
                val = row[col]
                text = self._fmt_val(val)
                item = QStandardItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
                model.setItem(row_idx, col_idx + 1, item)

        self.table.setModel(model)
        self.table.resizeColumnsToContents()

    # ── 筛选栏 ──

    def _get_filter_columns(self) -> list[str]:
        df = self.source_df
        if df is None:
            return []
        result = []
        for col in df.columns:
            for kw in self.FILTER_KEYWORDS:
                if kw in str(col) and col not in result:
                    result.append(col)
        return result

    def _build_filter_bar(self):
        """首次构建筛选栏（只调用一次）。"""
        # 清除旧按钮（确保干净初始）
        while self.filter_layout.count():
            item = self.filter_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.filter_btns.clear()

        filter_cols = self._get_filter_columns()
        if not filter_cols:
            return

        label = QLabel("筛选：")
        label.setStyleSheet("color: #888888; font-size: 12px;")
        self.filter_layout.addWidget(label)

        for col in filter_cols:
            clean = self._clean_col(col)
            # 初始状态下从原始数据计算全部可选值
            all_vals = sorted(self.source_df[col].fillna("（空）").astype(str).unique().tolist())
            btn = QPushButton(f"▽ {clean}")
            btn.setObjectName("filterBtn")
            btn.setCheckable(True)
            btn.setChecked(False)
            btn.clicked.connect(lambda checked, c=col: self._open_filter(c))
            self.filter_layout.addWidget(btn)
            self.filter_btns[col] = btn

        self.filter_layout.addStretch()

        # 同步按钮状态（初始无筛选，全部为原色）

    def _refresh_filter_buttons(self):
        """同步筛选按钮文字和选中态，不清除重建（类似 Tab4 逻辑）。"""
        if not self.filter_btns:
            return
        for col, btn in list(self.filter_btns.items()):
            if col not in self.source_df.columns:
                continue
            clean = self._clean_col(col)
            selected = self.active_filters.get(col)
            if selected is not None and selected != set(self.source_df[col].fillna("（空）").astype(str).unique()):
                btn.setText(f"▼ {clean}({len(selected)})")
                btn.setChecked(True)
            else:
                btn.setText(f"▽ {clean}")
                btn.setChecked(False)

        # 清除筛选按钮
        has_active = any(v for c, v in self.active_filters.items())
        if has_active and not any(
            isinstance(self.filter_layout.itemAt(i).widget(), QPushButton)
            and self.filter_layout.itemAt(i).widget().text() == "清除筛选"
            for i in range(self.filter_layout.count())
        ):
            clear_btn = QPushButton("清除筛选")
            clear_btn.setObjectName("dangerBtn")
            clear_btn.clicked.connect(self._clear_filters)
            # 插入到 stretch 之前
            for i in range(self.filter_layout.count()):
                if self.filter_layout.itemAt(i).spacerItem():
                    self.filter_layout.insertWidget(i, clear_btn)
                    break
            else:
                self.filter_layout.addWidget(clear_btn)
        elif not has_active:
            for i in range(self.filter_layout.count()):
                item = self.filter_layout.itemAt(i)
                if item.widget() and item.widget().text() == "清除筛选":
                    item.widget().deleteLater()
                    break

    def _open_filter(self, col):
        """打开筛选弹窗，计算可用选项时跳过自身筛选（选项级联）。"""
        if self.source_df is None or col not in self.source_df.columns:
            return
        # 计算可用值：跳过 col 自身的筛选，模拟 Excel 级联
        saved = self.active_filters.pop(col, None)
        filtered = self._get_display_df()
        if saved is not None:
            self.active_filters[col] = saved
        if filtered is None or col not in filtered.columns:
            vals = sorted(self.source_df[col].fillna("（空）").astype(str).unique().tolist())
        else:
            vals = sorted(filtered[col].fillna("（空）").astype(str).unique().tolist())

        selected = self.active_filters.get(col, set(vals))
        ColumnFilterPopup(self.frame, self._clean_col(col), vals, selected,
                          on_apply=lambda _, sel: self._apply_filter(col, sel))

    def _apply_filter(self, col, selected):
        self.active_filters[col] = selected
        log_info(f"过保情况筛选: {col} {len(selected)} 项")
        self.sort_col = None
        self.sort_asc = True
        self._fill_table(self._get_display_df())
        self._refresh_filter_buttons()

    def _clear_filters(self):
        self.active_filters.clear()
        self.sort_col = None
        self.sort_asc = True
        self._fill_table(self.source_df)
        self._refresh_filter_buttons()

    def _get_display_df(self):
        df = self.source_df
        if df is None:
            return None
        df = df.copy()
        for col, allowed in self.active_filters.items():
            if col not in df.columns:
                continue
            if not allowed:
                return df.iloc[:0].copy()
            ser = df[col].fillna("（空）").astype(str)
            df = df[ser.isin(allowed)]
        if self.sort_col and self.sort_col in df.columns:
            df = df.sort_values(self.sort_col, ascending=self.sort_asc).reset_index(drop=True)
        return df

    # ── 排序 ──

    def _on_header_click(self, logical_index):
        model = self.table.model()
        col = model.headerData(logical_index, Qt.Orientation.Horizontal)
        if col == self.SEQ_COL or "名称" in str(col):
            return

        display_df = self._get_display_df()
        if display_df is None or col not in display_df.columns:
            return

        self.sort_asc = not self.sort_asc if self.sort_col == col else True
        self.sort_col = col
        sorted_df = display_df.sort_values(col, ascending=self.sort_asc).reset_index(drop=True)
        self._fill_table(sorted_df)
        log_info(f"排序 [过保情况]: {col} {'升序' if self.sort_asc else '降序'}")

    # ── 工具方法 ──

    @staticmethod
    def _clean_col(col):
        return str(col).replace("\n", " ") if isinstance(col, str) else str(col)

    @staticmethod
    def _fmt_val(val):
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                return ""
            if val == int(val):
                return f"{int(val):,}"
            return f"{val:,.2f}"
        if isinstance(val, int):
            return f"{val:,}"
        if pd.isna(val):
            return ""
        return str(val)

    def _export_csv(self):
        df = getattr(self, "_display_df", None)
        if df is None or df.empty:
            QMessageBox.warning(self.frame, "提示", "没有数据可导出")
            return
        log_info(f"导出CSV [过保情况]: 过保情况统计.csv，共 {len(df)} 行")
        export_to_csv(df, self.frame, "过保情况统计.csv")
