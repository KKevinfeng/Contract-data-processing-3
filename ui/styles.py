"""Qt 全局样式表 + 字体配置"""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

# ── 字体定义 ──
FONT_TITLE    = QFont("Microsoft YaHei UI", 22)
FONT_TITLE.setWeight(QFont.Weight.Bold)

FONT_HEADING  = QFont("Microsoft YaHei UI", 18)
FONT_HEADING.setWeight(QFont.Weight.DemiBold)

FONT_SUBTITLE = QFont("Microsoft YaHei UI", 12)

FONT_MAIN     = QFont("Microsoft YaHei UI", 13)
FONT_BUTTON   = QFont("Microsoft YaHei UI", 13)
FONT_BUTTON.setWeight(QFont.Weight.DemiBold)

FONT_BRAND    = QFont("Microsoft YaHei UI", 16)
FONT_BRAND.setWeight(QFont.Weight.Bold)

FONT_BRAND_SUB = QFont("Microsoft YaHei UI", 9)

FONT_TABLE_HEADER = QFont("Microsoft YaHei UI", 12)
FONT_TABLE_HEADER.setWeight(QFont.Weight.DemiBold)

FONT_TABLE_BODY = QFont("Microsoft YaHei UI", 12)

FONT_CARD_LABEL = QFont("Microsoft YaHei UI", 12)
FONT_CARD_VALUE = QFont("Microsoft YaHei UI", 20)
FONT_CARD_VALUE.setWeight(QFont.Weight.Bold)


# ── 主题色彩 ──
LIGHT = {
    "primary":       "#2563EB",
    "primary_hover": "#1D4ED8",
    "bg":            "#F7F8FA",
    "bg_card":       "#FFFFFF",
    "sidebar":       "#FFFFFF",
    "sidebar_hover": "#F1F5F9",
    "sidebar_active": "#EFF6FF",
    "text":          "#1E293B",
    "text_sub":      "#64748B",
    "text_muted":    "#94A3B8",
    "border":        "#E2E8F0",
    "table_odd":     "#F8FAFC",
    "table_even":    "#FFFFFF",
    "header_bg":     "#F1F5F9",
    "header_text":   "#475569",
    "status_bg":     "#FFFFFF",
    "status_text":   "#64748B",
    "btn_gray":      "#F1F5F9",
    "btn_gray_hover": "#E2E8F0",
    "btn_gray_text": "#475569",
    "shadow":        "rgba(0,0,0,0.06)",
}


def T(key: str) -> str:
    """获取主题色。"""
    return LIGHT[key]


def build_qss() -> str:
    """根据当前主题构建全局 QSS。"""
    primary = T("primary")
    primary_hover = T("primary_hover")
    bg = T("bg")
    bg_card = T("bg_card")
    text = T("text")
    text_sub = T("text_sub")
    border = T("border")
    header_bg = T("header_bg")
    header_text = T("header_text")
    sidebar = T("sidebar")
    sidebar_hover = T("sidebar_hover")
    sidebar_active = T("sidebar_active")
    btn_gray = T("btn_gray")
    btn_gray_hover = T("btn_gray_hover")
    btn_gray_text = T("btn_gray_text")
    status_bg = T("status_bg")
    status_text = T("status_text")

    return f"""
/* ===== 全局 ===== */
QWidget {{
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
    color: {text};
    background: transparent;
}}
QMainWindow {{ background: {bg}; }}

/* ===== 主区域框架 ===== */
QFrame#sidebarFrame {{
    background: {sidebar};
    border-right: 1px solid {border};
}}
QFrame#topBar {{
    background: {bg_card};
    border-bottom: 1px solid {border};
}}
QFrame#statusBar {{
    background: {status_bg};
    border-top: 1px solid {border};
}}
QFrame#card {{
    background: {bg_card};
    border: 1px solid {border};
    border-radius: 12px;
}}

/* ===== Sidebar 导航列表 ===== */
QListWidget#navList {{
    background: {sidebar};
    border: none;
    outline: 0;
    padding: 8px 8px;
}}
QListWidget#navList::item {{
    color: {text_sub};
    background: transparent;
    border: 1px solid {border};
    border-radius: 8px;
    padding: 12px 16px;
    margin: 3px 4px;
    font-size: 14px;
    text-align: center;
}}
QListWidget#navList::item:hover {{
    background: {sidebar_hover};
    color: {text};
    border-color: {primary};
}}
QListWidget#navList::item:selected {{
    background: {sidebar_active};
    color: {primary};
    font-weight: bold;
    border-color: {primary};
    border-width: 2px;
}}

/* ===== 表格 ===== */
QTableView {{
    background: {bg_card};
    selection-background-color: #E2E8F0;
    selection-color: {text};
    border: none;
    outline: 0;
    font-size: 12px;
    gridline-color: transparent;
}}
/* 注：不要在 QTableView::item 设 border 等样式，
   这会屏蔽单元格级别的 setBackground 颜色（Qt 已知行为）。
   改用 setData(QColor, Qt.BackgroundRole) 设置行/单元格颜色。 */
QHeaderView::section {{
    background: {header_bg};
    color: {header_text};
    font-weight: bold;
    padding: 10px 4px;
    border: none;
    border-right: 1px solid {border};
    border-bottom: 2px solid {primary};
}}
QHeaderView::section:hover {{
    background: {sidebar_hover};
}}

/* ===== 按钮 ===== */
QPushButton {{
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#primaryBtn {{
    background: {primary};
    color: white;
}}
QPushButton#primaryBtn:hover {{
    background: {primary_hover};
}}
QPushButton#primaryBtn:pressed {{
    background: {primary_hover};
}}
QPushButton#grayBtn {{
    background: {btn_gray};
    color: {btn_gray_text};
    border: 1px solid {border};
}}
QPushButton#grayBtn:hover {{
    background: #EFF6FF;
    border-color: {primary};
    color: {primary};
}}
QPushButton#grayBtn:pressed {{
    background: #DBEAFE;
    border-color: {primary};
    color: {primary};
}}
QPushButton#ghostBtn {{
    background: transparent;
    color: {text_sub};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 6px 12px;
}}
QPushButton#ghostBtn:hover {{
    background: {sidebar_hover};
    color: {text};
    border-color: {primary};
}}

/* ===== 按钮扩展 ===== */
QPushButton#dangerBtn {{
    background: #D9534F;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton#dangerBtn:hover {{
    background: #C9302C;
}}
QPushButton#dangerBtn:pressed {{
    background: #B22B27;
}}
QPushButton#dangerBtn:disabled {{
    background: #F1F5F9;
    color: #94A3B8;
}}
QPushButton#warningBtn {{
    background: #E8960C;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton#warningBtn:hover {{
    background: #C47D0A;
}}
QPushButton#warningBtn:pressed {{
    background: #A66A09;
}}
QPushButton#accentBtn {{
    background: #1F6AA5;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
}}
QPushButton#accentBtn:hover {{
    background: #155485;
}}
QPushButton#accentBtn:pressed {{
    background: #0E4270;
}}
QPushButton#accentBtn:disabled {{
    background: #94A3B8;
    color: #E2E8F0;
}}
QPushButton#filterBtn {{
    background: #F1F5F9;
    color: {text_sub};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 2px 10px;
    font-size: 12px;
}}
QPushButton#filterBtn:hover {{
    background: #EFF6FF;
    color: {primary};
    border-color: {primary};
}}
QPushButton#filterBtn:checked {{
    background: {primary};
    color: white;
    border-color: {primary};
}}

/* ===== 输入框 ===== */
QLineEdit {{
    background: {bg_card};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: {primary};
    color: {text};
}}
QLineEdit:focus {{
    border-color: {primary};
}}
QLineEdit::placeholder {{
    color: {text_sub};
}}

/* ===== 下拉框 ===== */
QComboBox {{
    background: {bg_card};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px 12px;
    color: {text};
}}
QComboBox:focus {{
    border-color: {primary};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {bg_card};
    border: 1px solid {border};
    selection-background-color: {primary};
    selection-color: white;
    outline: 0;
}}

/* ===== 进度条 ===== */
QProgressBar {{
    border: none;
    border-radius: 6px;
    background: {sidebar_hover};
    text-align: center;
    font-size: 12px;
    height: 18px;
    color: {text};
}}
QProgressBar::chunk {{
    background: {primary};
    border-radius: 6px;
}}

/* ===== 滚动条 ===== */
QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {border};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {T("text_muted")};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {border};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {T("text_muted")};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ===== 消息弹窗 ===== */
QMessageBox {{
    background: {bg_card};
}}
QMessageBox QLabel {{
    color: {text};
}}

/* ===== 状态栏 ===== */
QStatusBar {{
    background: {status_bg};
    color: {status_text};
    border: none;
}}

/* ===== Dialog ===== */
QDialog {{
    background: {bg};
}}
QDialog QLabel {{
    color: {text};
}}

/* ===== 右键菜单 ===== */
QMenu {{
    background: {bg_card};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px 4px;
}}
QMenu::item {{
    background: transparent;
    color: {text};
    padding: 8px 28px;
    margin: 1px 4px;
    border-radius: 6px;
    font-size: 13px;
}}
QMenu::item:selected {{
    background: {primary};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background: {border};
    margin: 4px 8px;
}}
"""


def setup_app_style(app: QApplication) -> None:
    """应用全局 QSS 样式表。"""
    app.setStyleSheet(build_qss())
