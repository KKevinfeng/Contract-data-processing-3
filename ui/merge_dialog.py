"""产品名称合并对话框 (PySide6 版本)"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QListWidget,
    QPushButton, QLabel, QLineEdit, QScrollArea, QWidget, QFrame,
    QMessageBox, QAbstractItemView, QSplitter,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.msg_box import confirm, info, warn, error
from ui.logger import log_info
from utils import center_window
from ui.dialog_utils import configure_dialog, install_close_handler


class ProductMergeDialog:
    """产品名称合并配置弹窗。"""

    def __init__(self, parent, product_names: list[str], merge_rules: dict, on_apply):
        self.parent = parent
        self.all_product_names = sorted(product_names, key=lambda s: s.lower())
        self.displayed_product_names = list(self.all_product_names)
        self.merge_rules: dict[str, set[str]] = {k: set(v) for k, v in merge_rules.items()} if merge_rules else {}
        self.on_apply = on_apply

        self._build()

    @classmethod
    def show(cls, parent, product_names, merge_rules, on_apply):
        dialog = cls(parent, product_names, merge_rules, on_apply)
        dialog.dialog.exec()

    def _build(self):
        dialog = QDialog(self.parent)

        configure_dialog(dialog, show_close_button=True)

        install_close_handler(dialog)
        dialog.setWindowTitle("产品名称合并")
        dialog.resize(800, 600)
        dialog.setMinimumSize(780, 460)
        self.dialog = dialog

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(6)

        # 说明
        hint = QLabel("将名称相似、实为同一类的产品合并为一个名称进行统计")
        hint.setStyleSheet("color: #666666; font-size: 13px;")
        layout.addWidget(hint)

        # 左右分栏
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._build_left_panel(splitter)
        self._build_right_panel(splitter)
        splitter.setSizes([380, 380])
        layout.addWidget(splitter, 1)

        # 底部操作栏
        layout.addLayout(self._build_bottom_bar())

    def _build_left_panel(self, parent):
        left = QWidget()
        left.setObjectName("panelLeft")
        left.setStyleSheet("QWidget#panelLeft { background: #FAFAFA; border-radius: 8px; }")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 8, 10, 8)

        header = QHBoxLayout()
        title = QLabel("全部产品")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        header.addWidget(title)
        self.product_count_label = QLabel(f"（共 {len(self.all_product_names)} 个，Ctrl/Shift 多选）")
        self.product_count_label.setStyleSheet("color: #999999; font-size: 10px;")
        header.addWidget(self.product_count_label)
        header.addStretch()
        ll.addLayout(header)

        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("输入关键词搜索产品名称")
        self.search_entry.textChanged.connect(self._on_search_change)
        ll.addWidget(self.search_entry)

        self.listbox = QListWidget()
        self.listbox.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.listbox.setFont(QFont("Microsoft YaHei", 11))
        self.listbox.setStyleSheet(
            "QListWidget { background: white; border: 1px solid #1F6AA5; border-radius: 4px; }"
            "QListWidget::item:selected { background: #1F6AA5; color: white; }"
        )
        self._fill_listbox()
        ll.addWidget(self.listbox, 1)

        parent.addWidget(left)

    def _build_right_panel(self, parent):
        right = QWidget()
        right.setObjectName("panelRight")
        right.setStyleSheet("QWidget#panelRight { background: #FAFAFA; border-radius: 8px; }")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(10, 8, 10, 8)

        header = QHBoxLayout()
        title = QLabel("合并规则")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        header.addWidget(title)
        self.rule_count_label = QLabel("共 0 条")
        self.rule_count_label.setStyleSheet("color: #888888;")
        header.addWidget(self.rule_count_label)
        header.addStretch()
        rl.addLayout(header)

        self.rules_scroll = QScrollArea()
        self.rules_scroll.setWidgetResizable(True)
        self.rules_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.rules_widget = QWidget()
        self.rules_layout = QVBoxLayout(self.rules_widget)
        self.rules_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.rules_scroll.setWidget(self.rules_widget)
        rl.addWidget(self.rules_scroll, 1)

        self._refresh_rules()
        parent.addWidget(right)

    def _build_bottom_bar(self):
        layout = QHBoxLayout()
        layout.addWidget(QLabel("合并后显示名称："))

        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText("输入统一显示的名称")
        self.display_name_edit.setFixedWidth(200)
        layout.addWidget(self.display_name_edit)

        add_btn = QPushButton("添加规则")
        add_btn.setObjectName("accentBtn")
        add_btn.clicked.connect(self._add_rule)
        layout.addWidget(add_btn)

        layout.addStretch()

        clear_btn = QPushButton("清空全部")
        clear_btn.setObjectName("grayBtn")
        clear_btn.clicked.connect(self._clear_all)
        layout.addWidget(clear_btn)

        apply_btn = QPushButton("应用并刷新")
        apply_btn.setObjectName("accentBtn")
        apply_btn.clicked.connect(self._apply)
        layout.addWidget(apply_btn)

        return layout

    def _fill_listbox(self):
        self.listbox.clear()
        for name in self.displayed_product_names:
            self.listbox.addItem(name)

    def _on_search_change(self, keyword):
        keyword = keyword.strip().lower()
        if keyword:
            self.displayed_product_names = [n for n in self.all_product_names if keyword in n.lower()]
        else:
            self.displayed_product_names = list(self.all_product_names)
        self._fill_listbox()

    def _refresh_rules(self):
        # 清空
        while self.rules_layout.count():
            item = self.rules_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.rule_count_label.setText(f"共 {len(self.merge_rules)} 条")

        if not self.merge_rules:
            empty = QLabel("暂无合并规则\n\n在左侧选择多个产品，\n输入合并后的显示名称，\n点击「添加规则」即可")
            empty.setStyleSheet("color: #BBBBBB; font-size: 12px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.rules_layout.addWidget(empty)
            return

        for display_name, names in self.merge_rules.items():
            card = QFrame()
            card.setStyleSheet("QFrame { background: #E8F0FE; border-radius: 8px; padding: 8px; }")
            cl = QVBoxLayout(card)
            cl.setSpacing(4)

            name_label = QLabel(display_name)
            name_label.setStyleSheet("color: #1F6AA5; font-weight: bold; font-size: 13px;")
            cl.addWidget(name_label)

            products_text = "、".join(sorted(names))
            prod_label = QLabel(f"包含：{products_text}")
            prod_label.setStyleSheet("color: #555555; font-size: 10px;")
            prod_label.setWordWrap(True)
            cl.addWidget(prod_label)

            del_btn = QPushButton("删除此规则")
            del_btn.setObjectName("dangerBtn")
            del_btn.clicked.connect(lambda checked, dn=display_name: self._delete_rule(dn))
            cl.addWidget(del_btn, alignment=Qt.AlignmentFlag.AlignRight)

            self.rules_layout.addWidget(card)

    def _add_rule(self):
        selected = self.listbox.selectedItems()
        if not selected:
            QMessageBox.warning(self.dialog, "提示", "请先在左侧列表中勾选要合并的产品（支持多选）")
            return

        names = [item.text() for item in selected]
        display_name = self.display_name_edit.text().strip()

        if not display_name:
            QMessageBox.warning(self.dialog, "提示", "请输入合并后的显示名称")
            return

        for exist_dn, exist_names in self.merge_rules.items():
            overlap = set(names) & exist_names
            if overlap:
                QMessageBox.warning(
                    self.dialog, "产品冲突",
                    f"以下产品已在规则「{exist_dn}」中：\n" +
                    "\n".join(f"  · {n}" for n in overlap) +
                    "\n\n请先删除冲突的规则后再添加。",
                )
                return

        msg_names = "\n".join(f"  • {name}" for name in names)
        reply = confirm(self.dialog, "确认添加规则", f"确认将以下产品合并为「{display_name}」：\n\n{msg_names}")
        if not reply:
            return

        self.merge_rules[display_name] = set(names)
        log_info(f"产品合并规则添加: {display_name} ← {names}")
        self.display_name_edit.clear()
        self.listbox.clearSelection()
        self._refresh_rules()

    def _delete_rule(self, display_name):
        names = self.merge_rules.get(display_name, set())
        msg_names = "\n".join(f"  • {name}" for name in sorted(names))
        msg = f"确定要删除合并规则「{display_name}」吗？"
        if msg_names:
            msg += f"\n\n该规则包含以下产品：\n{msg_names}"
        reply = QMessageBox.question(
            self.dialog, "确认删除规则", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply:
            del self.merge_rules[display_name]
            log_info(f"产品合并规则删除: {display_name}")
            self._refresh_rules()

    def _clear_all(self):
        if not self.merge_rules:
            return
        reply = QMessageBox.question(
            self.dialog, "确认", "确定要清空所有合并规则吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply:
            self.merge_rules.clear()
            log_info("产品合并规则全部清空")
            self._refresh_rules()

    def _apply(self):
        rules = dict(self.merge_rules)
        self.dialog.accept()
        self.on_apply(rules)
