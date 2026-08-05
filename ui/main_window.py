"""主窗口 — Sidebar 侧边栏布局 / 顶部状态条 / Metric 卡片 / 多 Tab 切换 (PySide6)"""

from __future__ import annotations

import threading

import pandas as pd
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QListWidget,
    QListWidgetItem, QStackedWidget, QPushButton, QLabel,
    QFileDialog, QApplication,
)
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QFont

from ui.styles import (
    FONT_HEADING, FONT_SUBTITLE, FONT_BUTTON,
    FONT_BRAND, FONT_BRAND_SUB,
    FONT_CARD_LABEL, FONT_CARD_VALUE,
    T,
)
from ui.logger import log_error, log_info, install_qt_hook
from ui.log_view import LogViewer
from ui.tab_customer_total import CustomerTotalTab
from ui.tab_customer_category import CustomerCategoryTab
from ui.tab_expiry_stats import ExpiryStatsTab
from ui.tab_product_sales import ProductSalesTab
from ui.tab_industry import IndustryTab
from ui.tab_customer_profile import CustomerProfileTab
from ui.tab_renewal_analysis import RenewalAnalysisTab
from ui.starred_cache import StarredCache
from ui.starred_view import StarredView
from ui.starred_input_dialog import StarredInputDialog
from ui.progress_popup import ProgressPopup
from ui.industry_overrides import apply_overrides
from ui.msg_box import info, warn, error, show_about
from ui.settings import AppSettings
from ui import cache_manager
from utils import classify_contract


# ──────────────────────────────────────────────
#  Metric 卡片
# ──────────────────────────────────────────────
class MetricCard(QFrame):
    """单个 Metric 卡片：标题 + 大数值 + 短横线占位"""

    def __init__(self, label_text: str = "", value_text: str = "—", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedHeight(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(4)

        self.label = QLabel(label_text)
        self.label.setFont(FONT_CARD_LABEL)
        self.label.setStyleSheet(f"color: {T('text_sub')};")
        layout.addWidget(self.label)

        self.value = QLabel(value_text)
        self.value.setFont(FONT_CARD_VALUE)
        self.value.setStyleSheet(f"color: {T('text')};")
        layout.addWidget(self.value)

        self.set_label(label_text)
        self.set_value(value_text)

    def set_label(self, label_text: str):
        self.label.setText(label_text)

    def set_value(self, value_text: str):
        self.value.setText(value_text)


class MetricRow(QWidget):
    """横向并排 1-4 个 MetricCard（默认 4 个，多余的可隐藏）。"""

    def __init__(self, n: int = 4, parent=None):
        super().__init__(parent)
        if n < 1 or n > 4:
            n = 4
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        self.cards = []
        for _ in range(n):
            card = MetricCard("—", "—")
            self.cards.append(card)
            layout.addWidget(card, 1)

    def ensure_count(self, n: int):
        """确保至少有 n 张卡片，不足时追加（layout 中可见性由后续手动控制）。"""
        while len(self.cards) < n:
            card = MetricCard("—", "—")
            self.cards.append(card)
            self.layout().addWidget(card, 1)
        # 显示前 n 张，隐藏多余
        for i, c in enumerate(self.cards):
            c.setVisible(i < n)

    def update_values(self, *values, **kwargs):
        """两种调用方式都支持：
        - 位置参数：update_values(v1, v2, v3) — 顺序赋给 card1/2/3/4
        - 关键字参数：update_values(count=..., total=..., starred=...) — 按名赋给 card1/2/3
        """
        if kwargs:
            for key, val in kwargs.items():
                idx = {"count": 0, "total": 1, "starred": 2, "c1": 0, "c2": 1, "c3": 2, "c4": 3}.get(key)
                if idx is not None and idx < len(self.cards):
                    self.cards[idx].set_value(val)
        else:
            for i, v in enumerate(values):
                if i < len(self.cards):
                    self.cards[i].set_value(v if v is not None else "—")

    def set_labels(self, *labels):
        """位置参数：set_labels(l1, l2, l3, ...)"""
        for i, lbl in enumerate(labels):
            if i < len(self.cards):
                self.cards[i].set_label(lbl)


# ──────────────────────────────────────────────
#  Sidebar
# ──────────────────────────────────────────────
class Sidebar(QFrame):
    """左侧侧边栏：Logo + 导航 + 底部操作。"""

    nav_changed = Signal(int)
    starred_clicked = Signal()
    starred_input_clicked = Signal()
    error_log_clicked = Signal()
    run_log_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarFrame")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(0)

        # ── Logo 区 ──
        logo_box = QVBoxLayout()
        logo_box.setContentsMargins(20, 8, 20, 16)
        logo_box.setSpacing(2)

        logo = QLabel("合同数据中心")
        logo.setFont(FONT_BRAND)
        logo.setStyleSheet(f"color: {T('primary')};")
        logo_box.addWidget(logo)

        sub = QLabel("Maintenance Analytics")
        sub.setFont(FONT_BRAND_SUB)
        sub.setStyleSheet(f"color: {T('text_sub')}; letter-spacing: 1px;")
        logo_box.addWidget(sub)
        layout.addLayout(logo_box)

        # ── 导航列表 ──
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navList")
        self.nav_list.setFont(QFont("Microsoft YaHei UI", 12))
        nav_items = [
            "客户总金额", "客户分类", "过保情况",
            "过保分析", "产品销量", "行业统计", "客户画像",
        ]
        for text in nav_items:
            item = QListWidgetItem(text)
            item.setSizeHint(QSize(0, 44))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.nav_list.addItem(item)
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self.nav_changed.emit)
        layout.addWidget(self.nav_list, 1)

        # ── 底部操作 ──
        bottom = QVBoxLayout()
        bottom.setContentsMargins(12, 0, 12, 12)
        bottom.setSpacing(4)

        actions = [
            ("重点客户管理", self.starred_clicked),
            ("录入重点客户", self.starred_input_clicked),
            ("查看报错日志", self.error_log_clicked),
            ("查看运行日志", self.run_log_clicked),
        ]
        for label, sig in actions:
            btn = QPushButton(label)
            btn.setObjectName("ghostBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(sig)
            bottom.addWidget(btn)

        layout.addLayout(bottom)


# ──────────────────────────────────────────────
#  主窗口
# ──────────────────────────────────────────────
class MaintenanceApp(QMainWindow):
    """合同数据处理工具 — 现代化 Sidebar 布局版本"""

    REQUIRED_COL_KEYWORDS = [
        "合同编号*", "产品名称型号", "最终客户名称",
        "合同金额（元）*", "一级行业", "二级行业",
    ]

    TAB_TITLES = [
        ("客户总金额", "按客户查看合同总额与年度趋势"),
        ("客户分类", "按客户查看维保 / 产品 / 服务三种合同类型的金额分布"),
        ("过保情况", "过保合同统计与续保分析"),
        ("过保分析", "重点客户过保合同深度分析"),
        ("产品销量", "各产品售卖台数与合并规则管理"),
        ("行业统计", "按一级行业 / 二级行业下钻客户分布"),
        ("客户画像", "客户产品清单与行业归属详情"),
    ]

    def __init__(self):
        super().__init__()
        install_qt_hook()
        self.setWindowTitle("合同数据处理工具")
        self.setMinimumSize(1100, 700)

        self.df: pd.DataFrame | None = None
        self.starred_cache = StarredCache()
        self.settings = AppSettings()

        # 居中
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(1280, 800)
        self.move(
            (screen.width() - 1280) // 2,
            (screen.height() - 800) // 2,
        )

        self._setup_ui()

        # 恢复窗口布局
        geometry = self.settings.load_window_geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)
        state = self.settings.load_window_state()
        if state is not None:
            self.restoreState(state)
        idx = self.settings.load_sidebar_index()
        if idx and self.sidebar.nav_list.count() > idx:
            self.sidebar.nav_list.setCurrentRow(idx)

    # ── 整体 UI ──

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.nav_changed.connect(self._on_tab_changed)
        self.sidebar.starred_clicked.connect(self._view_starred)
        self.sidebar.starred_input_clicked.connect(self._input_starred)
        self.sidebar.error_log_clicked.connect(self._view_error_log)
        self.sidebar.run_log_clicked.connect(self._view_run_log)
        main_layout.addWidget(self.sidebar)

        # 主区域
        main_area = QWidget()
        ma_layout = QVBoxLayout(main_area)
        ma_layout.setContentsMargins(0, 0, 0, 0)
        ma_layout.setSpacing(0)

        ma_layout.addWidget(self._build_top_bar())
        ma_layout.addWidget(self._build_content(), 1)
        ma_layout.addWidget(self._build_status_bar())

        main_layout.addWidget(main_area, 1)

        self.setCentralWidget(central)
        self.statusBar().setSizeGripEnabled(False)

    # ── 顶部状态条 ──

    def _build_top_bar(self) -> QFrame:
        top = QFrame()
        top.setObjectName("topBar")
        top.setFixedHeight(64)

        layout = QHBoxLayout(top)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(16)

        self.file_status_label = QLabel("尚未选择合同数据")
        self.file_status_label.setFont(QFont("Microsoft YaHei UI", 12))
        self.file_status_label.setStyleSheet(f"color: {T('text_sub')};")
        layout.addWidget(self.file_status_label)

        layout.addStretch()

        self.import_btn = QPushButton("导入合同数据")
        self.import_btn.setObjectName("primaryBtn")
        self.import_btn.setFont(FONT_BUTTON)
        self.import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_btn.setFixedHeight(38)
        self.import_btn.clicked.connect(self._browse_file)
        layout.addWidget(self.import_btn)
        return top

    # ── 内容区 ──

    def _build_content(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(16)

        # Heading
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)
        self.heading_label = QLabel("合同数据处理工具")
        self.heading_label.setFont(FONT_HEADING)
        self.heading_label.setStyleSheet(f"color: {T('text')};")
        header_layout.addWidget(self.heading_label)

        self.subtitle_label = QLabel("请导入合同数据文件以开始分析")
        self.subtitle_label.setFont(FONT_SUBTITLE)
        self.subtitle_label.setStyleSheet(f"color: {T('text_sub')};")
        header_layout.addWidget(self.subtitle_label)

        layout.addLayout(header_layout)

        # Metric Row
        self.metric_row = MetricRow(3)
        layout.addWidget(self.metric_row)

        # Stacked widget 切换 Tab
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"QStackedWidget {{ background: {T('bg_card')}; border-radius: 12px; }}")
        self._build_tabs()
        layout.addWidget(self.stack, 1)

        return container

    # ── 状态栏 ──

    def _build_status_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("statusBar")
        frame.setFixedHeight(36)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(28, 0, 28, 0)

        self.status_label = QLabel("就绪 — 请选择 Excel 文件")
        self.status_label.setFont(QFont("Microsoft YaHei UI", 11))
        self.status_label.setStyleSheet(f"color: {T('text_sub')};")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # 关于按钮
        about_btn = QPushButton("关于 v3.0.1.0")
        about_btn.setObjectName("ghostBtn")
        about_btn.setFont(QFont("Microsoft YaHei UI", 11))
        about_btn.clicked.connect(self._show_about)
        layout.addWidget(about_btn)

        return frame

    # ── 构建 Tab ──

    def _build_tabs(self):
        """构建 7 个 Tab 页面并放入 QStackedWidget。"""

        # Tab 0: 客户总金额统计 — 接 sidebar 的 metric
        self.tab_customer_total = CustomerTotalTab(
            on_double_click=self._on_tab_customer_total_double_click,
            on_star_toggle=self._on_star_toggle,
            get_starred_names=self._get_starred_names,
        )
        self.stack.addWidget(self._wrap_tab(self.tab_customer_total, idx=0))

        self.tab_customer_category = CustomerCategoryTab(
            on_double_click=self._on_tab_customer_category_double_click,
        )
        self.stack.addWidget(self._wrap_tab(self.tab_customer_category, idx=1))

        # Tab 2: 过保情况统计
        self.tab_expiry_stats = ExpiryStatsTab(starred_cache=self.starred_cache)
        self.stack.addWidget(self.tab_expiry_stats.build())

        # Tab 3: 过保数据分析
        self.tab_renewal_analysis = RenewalAnalysisTab(
            expiry_tab=self.tab_expiry_stats,
            main_df_provider=lambda: self.df,
        )
        def _on_expiry_data_change():
            # Tab3 数据变更：刷新 Tab4 + 当前所在 Tab 的 metric
            self.tab_renewal_analysis.refresh()
            cur = self.stack.currentIndex()
            if cur in (2, 3):
                self._refresh_metric_for_tab(cur)
        self.tab_expiry_stats._on_data_change = _on_expiry_data_change
        self.stack.addWidget(self.tab_renewal_analysis.build())

        self.tab_product_sales = ProductSalesTab(
            on_double_click=None,
            on_data_change=self._on_product_sales_data_change,
        )
        self.stack.addWidget(self._wrap_tab(self.tab_product_sales, idx=4))

        self.tab_industry = IndustryTab(on_double_click=None)
        self.stack.addWidget(self._wrap_tab(self.tab_industry, idx=5))

        self.tab_customer_profile = CustomerProfileTab(
            on_double_click=None,
            get_starred_names=self._get_starred_names,
        )
        self.stack.addWidget(self._wrap_tab(self.tab_customer_profile, idx=6))

        self._shared_tabs = [
            self.tab_customer_total,
            self.tab_customer_category,
            self.tab_product_sales,
            self.tab_industry,
            self.tab_customer_profile,
        ]

    def _wrap_tab(self, tab, idx: int) -> QWidget:
        """包装 Tab：把 QtBaseTab 自身按钮栏塞到下方，并把 metric 卡片的更新回调接上。"""
        # 重写 build —— 因为 base 的 build 已经创建按钮栏，下面我们直接调用 build，
        # 并在 stack 里只放 base 的 frame。
        frame = tab.build()
        if idx == 0:
            # 客户总金额 Tab：把 metric 卡片与该 Tab 数据联动
            self._wire_metric_to_total_tab(tab)
        return frame

    # ── Tab 切换 ──

    def _on_tab_changed(self, idx: int):
        if idx < 0 or idx >= self.stack.count():
            return
        self.stack.setCurrentIndex(idx)
        title, subtitle = self.TAB_TITLES[idx]
        self.heading_label.setText(title)
        self.subtitle_label.setText(subtitle)

        # 切换 metric 标签 + 计算对应数值
        self._refresh_metric_for_tab(idx)

    # ── Metric 联动 ──

    def _refresh_metric_for_tab(self, idx: int):
        """根据当前 Tab 计算 metric 卡片的 labels 和 values。"""
        # Tab3 / Tab4 优先处理：它们有独立的数据源（不过保情况表），不依赖主合同数据
        if idx in (2, 3):
            self.metric_row.ensure_count(4)
            self.metric_row.set_labels("已续保", "有意向", "考虑中", "不续保")
            src_df = self.tab_expiry_stats.source_df
            if src_df is None or src_df.empty or "*客户意向" not in src_df.columns:
                self.metric_row.update_values("—", "—", "—", "—")
            else:
                intent = src_df["*客户意向"].fillna("").astype(str).str.strip()
                self.metric_row.update_values(
                    f"{int((intent == '已续保').sum()):,}",
                    f"{int((intent == '有意向').sum()):,}",
                    f"{int((intent == '考虑中').sum()):,}",
                    f"{int((intent == '不续保').sum()):,}",
                )
            return

        # 其他 Tab 默认 3 卡
        self.metric_row.ensure_count(3)
        if self.df is None:
            self.metric_row.set_labels("—", "—", "—")
            self.metric_row.update_values("—", "—", "—")
            return

        try:
            if idx == 0:
                self.metric_row.set_labels("客户数量", "合同总金额", "重点客户")
                totals = self._compute_total_metrics()
                self.metric_row.update_values(
                    count=f"{totals['count']:,}",
                    total=f"¥ {totals['total']:,.2f}",
                    starred=f"{len(self.starred_cache.get_all())}",
                )
            elif idx == 1:
                # 客户分类：M / P / S 三类合同总金额
                self.metric_row.set_labels("M 维保总额", "P 产品总额", "S 服务总额")
                from data_processor import compute_customer_category
                df_cat = compute_customer_category(self.df)
                m_sum = df_cat["维保合同总金额"].sum() if "维保合同总金额" in df_cat.columns else 0
                p_sum = df_cat["产品合同总金额"].sum() if "产品合同总金额" in df_cat.columns else 0
                s_sum = df_cat["服务合同总金额"].sum() if "服务合同总金额" in df_cat.columns else 0
                self.metric_row.update_values(
                    count=f"¥ {m_sum:,.2f}",
                    total=f"¥ {p_sum:,.2f}",
                    starred=f"¥ {s_sum:,.2f}",
                )
            elif idx == 4:
                # 产品销量
                self.metric_row.set_labels("产品种类", "总销量", "—")
                from data_processor import compute_product_sales
                df_prod = compute_product_sales(self.df, merge_rules=self.tab_product_sales.merge_rules or None)
                product_count = len(df_prod)
                total_qty = int(df_prod["售卖总台数"].sum()) if "售卖总台数" in df_prod.columns else 0
                self.metric_row.update_values(
                    count=f"{product_count:,}",
                    total=f"{total_qty:,}",
                    starred="—",
                )
            elif idx == 5:
                self.metric_row.set_labels("行业数量", "客户总数", "—")
                from data_processor import compute_industry_stats
                df_ind = compute_industry_stats(self.df)
                ind_count = len(df_ind)
                # 用主 df 的 .nunique() 算唯一客户数（不用行业级 sum，否则一个客户跨多个行业会被算多次）
                cust_count = self.df["最终客户名称"].nunique() if "最终客户名称" in self.df.columns else 0
                self.metric_row.update_values(
                    count=f"{ind_count}",
                    total=f"{cust_count:,}",
                    starred="—",
                )
            elif idx == 6:
                self.metric_row.set_labels("客户数", "重点客户数", "—")
                metrics = self._compute_total_metrics()
                self.metric_row.update_values(
                    count=f"{metrics['count']:,}",
                    total=f"{len(self.starred_cache.get_all())}",
                    starred="—",
                )
            else:
                self.metric_row.set_labels("—", "—", "—")
                self.metric_row.update_values("—", "—", "—")
        except Exception as e:
            log_error(f"计算 Tab{idx} metric 失败: {e}")
            self.metric_row.set_labels("—", "—", "—")
            self.metric_row.update_values("—", "—", "—")

    # ── Metric 联动 ──

    def _wire_metric_to_total_tab(self, tab: CustomerTotalTab):
        """在 tab 数据填充后回调，更新 metric。"""
        original_populate = tab.populate

        def wrapped_populate(df: pd.DataFrame):
            original_populate(df)
            try:
                total_amount = f"{df['合同总金额'].sum():,.2f}" if '合同总金额' in df.columns else "—"
                count = f"{len(df):,}" if df is not None else "—"
                starred_count = f"{len(self.starred_cache.get_all())}"
                self.metric_row.update_values(
                    count=count,
                    total=f"¥ {total_amount}" if total_amount != "—" else "—",
                    starred=starred_count,
                )
            except Exception as e:
                log_error(f"更新 metric 卡片失败: {e}")

        tab.populate = wrapped_populate

    # ── 文件操作 ──

    def _browse_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择合同数据文件", "",
            "Excel 文件 (*.xlsx *.xls);;所有文件 (*.*)",
        )
        if filepath:
            self.file_status_label.setText(filepath)
            self._load_file(filepath)

    def _view_error_log(self):
        LogViewer.show_error(self)

    def _view_run_log(self):
        LogViewer.show_run(self)

    def _show_about(self):
        """显示关于对话框。"""
        # 用结构化数据 + QGridLayout 渲染，避免 Qt RichText 不支持现代 CSS 的问题
        rows = [
            ("版本信息：", "3.0.1.0"),
            ("制作人：", "Kevin"),
            ("主页：", "https://kkevinfeng.github.io/"),
            ("源代码：", "https://github.com/KKevinfeng/Contract-data-processing-3.git"),
        ]
        show_about(self, "关于", "合同数据处理工具", rows)

    def _view_starred(self):
        def on_cache_changed():
            if self.df is not None:
                self._refresh_shared_tabs()
                self._check_starred_collision()

        StarredView.show(self, self.starred_cache, on_changed=on_cache_changed)

    def _input_starred(self):
        def on_done(new_count: int, dup_count: int, input_count: int):
            parts = []
            if new_count > 0:
                parts.append(f"已新增 {new_count} 个")
            if dup_count > 0:
                parts.append(f"{dup_count} 个重复已跳过")
            if parts:
                self.status_label.setText("；".join(parts))
                log_info(f"手动录入完成：{'; '.join(parts)}")
            if new_count > 0:
                if self.df is not None:
                    self._refresh_shared_tabs()
                    self._check_starred_collision()

        self._starred_dlg = StarredInputDialog(self, self.starred_cache, on_done=on_done)

    def _on_star_toggle(self, customer_name: str, is_starred: bool):
        if is_starred:
            self.starred_cache.add(customer_name)
            log_info(f"标星客户: {customer_name}")
        else:
            self.starred_cache.remove(customer_name)
            log_info(f"取消标星客户: {customer_name}")
        self._refresh_tab_profile()
        self._refresh_metric()

    def _get_starred_names(self) -> list[str]:
        return self.starred_cache.get_all()

    def _refresh_metric(self):
        """根据当前 Tab 重算 metric 值。"""
        if self.df is None:
            return
        # 委托给 _refresh_metric_for_tab，按当前 stack index 计算
        self._refresh_metric_for_tab(self.stack.currentIndex())

    def _compute_total_metrics(self):
        from data_processor import compute_customer_total
        df_total = compute_customer_total(self.df)
        return {
            "count": len(df_total),
            "total": df_total["合同总金额"].sum() if '合同总金额' in df_total.columns else 0,
        }

    # ── 数据加载 ──

    def _init_cache_load_tracker(self, count: int):
        """初始化缓存加载完成计数跟踪。"""
        self._cache_load_pending = count
        self._cache_load_done = 0

    def _cache_display_progress(self, real: float) -> float:
        """把"实际加载进度"映射为"显示进度"（实际 × 2，上限 100%）。

        例如实际 16% → 显示 32%；实际 45% → 显示 90%；
        实际 ≥50% → 显示 100%。这样进度条在真实加载完成（实际 50%+）
        时恰好显示 100%，不会出现"加载完了进度却还在半路"的脱节。
        """
        return min(real * 2.0, 1.0)

    def _on_cache_load_item_done(self):
        """单个缓存数据源加载完成时回调。

        数据源完成即"实际完成比例"已达相应份额，全部完成后关闭启动弹窗。
        显示进度由数据源内部阶段 ×2 驱动（见 _cache_display_progress）。
        """
        if getattr(self, "_cache_load_cancelled", False):
            return
        self._cache_load_done = getattr(self, "_cache_load_done", 0) + 1
        pending = getattr(self, "_cache_load_pending", 0)
        if pending <= 0:
            return
        if self._cache_load_done >= pending:
            self._finish_cache_load()

    def _finish_cache_load(self):
        """所有缓存加载完成：关闭启动弹窗、更新状态栏。

        显示进度在真实加载过程中已按 ×2 驱动到 100%（见 _cache_display_progress），
        因此这里直接关闭，不再模拟补全。
        """
        splash = getattr(self, "_startup_splash", None)
        if splash is not None:
            try:
                splash.set_progress(1.0, "加载完成！")
                splash.close()
            except Exception:
                pass
            self._startup_splash = None
        self.status_label.setText(
            "已从缓存自动加载上次导入的数据（可点击「导入合同数据」重新导入）"
        )
        log_info("历史数据缓存加载完成")

    def _cancel_cache_load(self):
        """用户点击 × 关闭启动弹窗：取消后台缓存导入。

        已加载完成的数据保留；尚未启动/正在进行的后续加载停止，
        避免弹窗关闭后数据仍在后台导入。
        """
        self._cache_load_cancelled = True
        splash = getattr(self, "_startup_splash", None)
        if splash is not None:
            try:
                splash.close()
            except Exception:
                pass
            self._startup_splash = None
        self.status_label.setText("已取消自动加载历史数据（可点击「导入合同数据」手动导入）")
        log_info("用户取消了缓存自动加载")

    def load_main_from_cache(self):
        """启动时自动加载缓存中的主合同文件（若存在且有效）。"""
        if self.df is not None:
            return False
        snap = cache_manager.scan_cache()
        cache_manager.clean_junk_files(snap)
        if snap.main.valid:
            log_info(f"检测到主数据缓存: {snap.main.path}")
            self._load_file(snap.main.path, from_cache=True)
            return True
        return False

    def load_expiry_from_cache(self):
        """启动时自动加载缓存中的过保文件（若存在且有效）。"""
        if self.tab_expiry_stats.source_df is not None:
            return False
        snap = cache_manager.scan_cache()
        if snap.expiry.valid:
            log_info(f"检测到过保数据缓存: {snap.expiry.path}")
            self.tab_expiry_stats._load_from_cache_path(snap.expiry.path)
            return True
        return False

    def try_load_all_caches(self):
        """启动时按顺序加载主数据与过保数据缓存。

        每个数据源异步加载，加载完成各自回调 _on_cache_load_item_done，
        全部完成后进度平滑补全到 100% 并关闭启动弹窗。
        """
        self._cache_load_cancelled = False
        loaded_main = self.load_main_from_cache()
        # 主数据加载期间用户可能已取消，则不再启动过保数据
        if self._cache_load_cancelled:
            loaded_expiry = False
        else:
            loaded_expiry = self.load_expiry_from_cache()
        pending = (1 if loaded_main else 0) + (1 if loaded_expiry else 0)
        if pending == 0:
            self._finish_cache_load()
            return False
        self._init_cache_load_tracker(pending)
        # 进度条由数据源内部真实阶段 ×2 驱动，无需定时器模拟
        return True

    def _progress_popup(self):
        """获取当前应显示进度的弹窗。

        - 缓存自动加载时：返回主窗口的启动弹窗（_startup_splash）。
          进度值由数据源内部真实阶段上报，并经 _cache_display_progress（×2）映射后显示。
        - 人工导入时：返回内部自建的 ProgressPopup 正常显示分步进度。
        """
        if self._load_from_cache:
            splash = getattr(self, "_startup_splash", None)
            if splash is not None:
                return splash
            return None
        return getattr(self, "_popup", None)

    def _load_file(self, filepath: str, from_cache: bool = False):
        if getattr(self, "_loading", False):
            return
        self._loading = True

        self._load_error: str | None = None
        self._load_df: pd.DataFrame | None = None
        self._load_step: int = 0
        self._load_filepath: str = filepath
        self._load_from_cache: bool = from_cache

        if from_cache:
            # 缓存加载：复用主窗口启动弹窗，不再新建弹窗
            self._popup = None
            splash = getattr(self, "_startup_splash", None)
            if splash is not None:
                splash.set_progress(0.0, "正在读取历史数据文件...")
        else:
            self._popup = ProgressPopup(self, title="正在导入合同数据...")
            self._popup.set_progress(0.0, "正在读取文件...")

        def worker():
            try:
                raw_df = pd.read_excel(filepath, header=1)
                col_map: dict[str, str] = {}
                missing: list[str] = []
                for keyword in self.REQUIRED_COL_KEYWORDS:
                    found = [c for c in raw_df.columns if keyword in str(c)]
                    if found:
                        col_map[keyword] = found[0]
                    else:
                        missing.append(keyword)

                if missing:
                    missing_text = "、".join(f"【{k}】" for k in missing)
                    self._load_error = f"没有{missing_text}列，请提供正确的文件"
                    log_error(f"文件 {filepath} 缺少必要列：{missing_text}")
                    return

                result_df = raw_df[list(col_map.values())].rename(
                    columns={v: k for k, v in col_map.items()}
                ).copy()
                self._load_df = result_df
                log_info(f"数据文件加载成功: {filepath}，共 {len(result_df)} 行")
            except FileNotFoundError:
                self._load_error = f"文件不存在：\n{filepath}"
                log_error(f"文件不存在：{filepath}")
            except Exception as e:
                self._load_error = f"加载文件失败：\n{e}"
                log_error(f"加载文件失败：{filepath}")

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        QTimer.singleShot(50, lambda: self._poll_file_read(thread))

    def _poll_file_read(self, thread: threading.Thread):
        # 缓存加载被用户取消：停止轮询，保留已加载的数据（如有）
        if self._load_from_cache and getattr(self, "_cache_load_cancelled", False):
            self._loading = False
            if self.df is None and self._load_df is not None:
                self.df = self._load_df
            return
        if thread.is_alive():
            popup = self._progress_popup()
            if popup is not None:
                # 读取阶段：随轮询次数在 0~20% 间平滑推进，让用户看到读取进度在实时变化。
                # 缓存模式：显示 = 实际 × 2（封顶 95%），见 _cache_display_progress
                self._read_poll_count = getattr(self, "_read_poll_count", 0) + 1
                read_progress = min(0.02 + self._read_poll_count * 0.01, 0.20)
                if self._load_from_cache:
                    read_progress = min(read_progress * 2.0, 0.95)
                    # 缓存模式：文字固定为"正在读取历史数据..."
                    popup.set_progress(read_progress, "正在读取历史数据...")
                else:
                    popup.set_progress(read_progress, "正在读取 Excel 文件...")
            QTimer.singleShot(50, lambda: self._poll_file_read(thread))
            return

        if self._load_error:
            # 人工导入时关闭自建弹窗；缓存加载时自建弹窗为 None，无需关闭
            if not self._load_from_cache and self._popup is not None:
                self._popup.close()
            self._loading = False
            # 若本次加载的是缓存且失败，清除无效缓存，避免下次反复读取
            if self._load_from_cache:
                self._load_from_cache = False
                cache_manager.remove_main_cache()
                self._on_cache_load_item_done()
            QTimer.singleShot(100, lambda: error(self, "错误", self._load_error))
            self.status_label.setText("就绪 — 请选择 Excel 文件")
            return

        self.df = self._load_df
        self._load_step = 0
        self._read_poll_count = 0
        popup = self._progress_popup()
        if popup is not None:
            read_done = 0.20 if not self._load_from_cache else min(0.20 * 2.0, 0.95)
            text = "文件读取完成，开始统计..." if not self._load_from_cache else "正在读取历史数据..."
            popup.set_progress(read_done, text)

        # 人工导入成功：写入缓存目录（下次启动自动加载）。
        # 缓存自动加载时不重复写缓存（避免复制自身造成冗余）。
        if not self._load_from_cache:
            cache_manager.write_cache(self._load_filepath, "main")

        QTimer.singleShot(20, self._compute_next_tab)

    def _compute_next_tab(self):
        # 缓存加载被用户取消：停止统计（已统计的 Tab 保留）
        if self._load_from_cache and getattr(self, "_cache_load_cancelled", False):
            self._loading = False
            return

        tabs = self._shared_tabs
        total = len(tabs)
        i = self._load_step

        if i >= total:
            self._finish_loading()
            return

        tab = tabs[i]
        title = self.TAB_TITLES[i][0] if i < len(self.TAB_TITLES) else "..."
        # 统计阶段：20% ~ 95%，每个 Tab 精确推进。
        # 缓存模式：显示 = 实际 × 2（封顶 95%），真实完成时才由 _finish_cache_load 设 100%
        progress = 0.20 + 0.75 * ((i + 1) / total)
        if self._load_from_cache:
            progress = min(progress * 2.0, 0.95)
            # 缓存模式：文字固定为"正在读取历史数据..."
            text = "正在读取历史数据..."
        else:
            text = f"正在统计: {title} ({i+1}/{total})..."
        popup = self._progress_popup()
        if popup is not None:
            popup.set_progress(progress, text)

        try:
            computed = tab.compute_data(self.df)
            tab.populate(computed)
        except Exception as e:
            log_error(f"Tab {title} 计算失败: {e}")

        self._load_step += 1
        QTimer.singleShot(10, self._compute_next_tab)

    def _finish_loading(self):
        self._loading = False

        try:
            if self.tab_expiry_stats.source_df is not None:
                self.tab_renewal_analysis.refresh()
        except Exception as e:
            log_error(f"过保数据分析刷新失败: {e}")

        popup = self._progress_popup()
        # 缓存模式：不在此处设 100%，避免与过保并发时进度回退（往复），
        # 由 _finish_cache_load 在真实全部完成时统一设 100% 并关闭。
        if popup is not None and not self._load_from_cache:
            popup.set_progress(1.0, "加载完成！")
        # 人工导入：关闭自建弹窗；缓存加载：自建弹窗为 None，启动弹窗由协调器统一关闭
        if not self._load_from_cache and self._popup is not None:
            self._popup.close()
        self.status_label.setText(f"已加载 {len(self.df)} 行数据 — {self._load_filepath}")

        # 更新 metric 卡片
        self._refresh_metric()

        # 若本次是从缓存加载，通知启动弹窗协调器
        if self._load_from_cache:
            self._on_cache_load_item_done()

        QTimer.singleShot(100, self._check_starred_collision)

    def _check_starred_collision(self):
        starred = self.starred_cache.get_all()
        if not starred or self.df is None:
            return

        col_names = set(self.df["最终客户名称"].dropna().unique())
        unmatched = [name for name in starred if name not in col_names]
        if not unmatched:
            return

        lines = "\n".join(f"  · {name}" for name in unmatched)
        QTimer.singleShot(100, lambda: warn(
            self, "未碰撞提示",
            f"以下 {len(unmatched)} 个重点客户未在本次导入数据中匹配到：\n\n"
            f"{lines}\n\n如需更新缓存表，请使用「录入重点客户」管理。",
        ))

    # ── 数据刷新 ──

    def _refresh_shared_tabs(self):
        if self.df is None:
            return
        try:
            for tab in self._shared_tabs:
                computed = tab.compute_data(self.df)
                tab.populate(computed)
            log_info(f"数据已刷新 — 共 {len(self.df)} 行合同数据")
            self.status_label.setText(f"数据已刷新 — 共 {len(self.df)} 行合同数据")
            self._refresh_metric()
        except Exception as e:
            log_error("数据处理失败")
            error(self, "错误", f"数据处理失败：\n{e}")

    def _refresh_tab_profile(self):
        if self.df is None:
            return
        try:
            computed = self.tab_customer_profile.compute_data(self.df)
            self.tab_customer_profile.populate(computed)
        except Exception as e:
            log_error(f"刷新客户画像 Tab 失败: {e}")

    def _on_product_sales_data_change(self):
        if self.df is None:
            return
        try:
            computed = self.tab_product_sales.compute_data(self.df)
            self.tab_product_sales.populate(computed)
            rule_count = len(self.tab_product_sales.merge_rules)
            self.status_label.setText(
                f"产品合并规则已应用（{rule_count} 条）— 共 {len(self.df)} 行合同数据"
            )
            log_info(f"产品合并规则已应用，共 {rule_count} 条")
            self._switch_to_tab(4)
        except Exception as e:
            log_error("产品合并刷新失败")
            error(self, "错误", f"刷新产品销量数据失败：\n{e}")

    def _switch_to_tab(self, idx: int):
        if 0 <= idx < self.stack.count():
            self.stack.setCurrentIndex(idx)
            self.sidebar.nav_list.setCurrentRow(idx)

    # ── 双击事件 ──

    def _on_tab_customer_total_double_click(self, table, index):
        if self.df is None:
            return
        model = table.model()
        if model is None:
            return
        row = index.row()
        name_item = model.item(row, 2)
        if name_item:
            self._show_customer_detail(name_item.text())

    def _on_tab_customer_category_double_click(self, table, index):
        if self.df is None:
            return
        model = table.model()
        if model is None:
            return
        row = index.row()
        col = index.column()

        name_item = model.item(row, 1)
        if not name_item:
            return

        customer_name = name_item.text()
        type_map = {2: ("M", "维保"), 3: ("P", "产品"), 4: ("S", "服务")}
        if col in type_map:
            ct, label = type_map[col]
            self._show_customer_detail(customer_name, contract_type=ct, type_label=label)
        elif col == 1:
            self._show_customer_detail(customer_name)

    def _show_customer_detail(self, customer_name: str,
                               contract_type: str | None = None, type_label: str = ""):
        if self.df is None:
            return
        from ui.detail_window import CustomerDetailWindow

        customer_df = self.df[self.df["最终客户名称"] == customer_name].copy()
        if customer_df.empty:
            info(self, "提示", f'未找到客户"{customer_name}"的合同记录')
            return

        customer_df = apply_overrides(customer_df)

        if contract_type:
            customer_df["_type"] = customer_df["合同编号*"].apply(classify_contract)
            customer_df = customer_df[customer_df["_type"] == contract_type]
            if customer_df.empty:
                info(
                    self, "提示",
                    f'客户"{customer_name}"没有{type_label}类合同记录',
                )
                return

        if contract_type:
            title_text = f'客户：{customer_name} — {type_label}合同（共 {len(customer_df)} 条）'
        else:
            title_text = f'客户：{customer_name}（共 {len(customer_df)} 条合同）'

        log_info(f"查看客户详情: {customer_name}，共 {len(customer_df)} 条合同")
        CustomerDetailWindow.show(self, customer_df, title_text, customer_name)

    # ── 关闭事件 ──

    def closeEvent(self, event):
        """保存窗口状态后安全退出。"""
        self.settings.save_window_geometry(self.saveGeometry())
        self.settings.save_window_state(self.saveState())
        self.settings.save_sidebar_index(self.sidebar.nav_list.currentRow())
        self.settings.sync()
        event.accept()
