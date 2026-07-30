"""工具函数模块：合同类型识别、产品名称型号列解析、窗口居中、CSV 导出"""

from __future__ import annotations

import re
import pandas as pd

from PySide6.QtWidgets import QWidget, QFileDialog, QMessageBox, QApplication
from PySide6.QtCore import Qt

# 合同编号正则：匹配 -M/P/S 后跟数字的模式
CONTRACT_TYPE_PATTERN = re.compile(r'-(M|P|S)\d')

# 合同年份正则：提取第一个 "-" 前的两位数字年份
CONTRACT_YEAR_PATTERN = re.compile(r'(\d{2})-')

# 合同类型中文映射
TYPE_LABEL = {
    "M": "维保",
    "P": "产品",
    "S": "服务",
}


def center_window(widget: QWidget, width: int, height: int) -> None:
    """将窗口定位到屏幕中央。"""
    screen = QApplication.primaryScreen().availableGeometry()
    x = (screen.width() - width) // 2
    y = (screen.height() - height) // 2
    widget.setGeometry(x, y, width, height)


def extract_contract_year(contract_id: str) -> int | None:
    """从合同编号中提取年份。规则：第一个 "-" 前的两位数字代表年份，如 "26" → 2026。"""
    if pd.isna(contract_id):
        return None
    match = CONTRACT_YEAR_PATTERN.search(str(contract_id))
    if match:
        yy = int(match.group(1))
        return 2000 + yy
    return None


def classify_contract(contract_id: str) -> str | None:
    """根据合同编号识别合同类型。返回 "M" / "P" / "S" 或 None。"""
    if pd.isna(contract_id):
        return None
    match = CONTRACT_TYPE_PATTERN.search(str(contract_id))
    return match.group(1) if match else None


def parse_product_lines(cell_value) -> list[dict]:
    """
    解析产品名称型号列，提取每条产品信息。
    每行格式："产品名称 | 产品型号 | 数量" 或 "产品名称 | 数量"
    """
    if pd.isna(cell_value):
        return []

    results = []
    for line in str(cell_value).split('\n'):
        line = line.strip()
        if not line:
            continue

        parts = [p.strip() for p in line.split('|')]

        if len(parts) == 3:
            try:
                qty = int(float(parts[2]))
                results.append({"name": parts[0], "model": parts[1], "qty": qty})
            except (ValueError, IndexError):
                from ui.logger import log_error
                log_error(f"解析产品行数量失败(3段格式): {line}")
                continue
        elif len(parts) == 2:
            try:
                qty = int(float(parts[1]))
                results.append({"name": parts[0], "model": None, "qty": qty})
            except (ValueError, IndexError):
                from ui.logger import log_error
                log_error(f"解析产品行数量失败(2段格式): {line}")
                continue

    return results


def export_to_csv(df: pd.DataFrame, parent: QWidget, default_filename: str = "export.csv") -> None:
    """弹出保存对话框，将 DataFrame 导出为 CSV 文件（UTF-8 BOM）。"""
    if df is None or df.empty:
        QMessageBox.warning(parent, "提示", "没有数据可导出")
        return

    filepath, _ = QFileDialog.getSaveFileName(
        parent,
        "导出 CSV 文件",
        default_filename,
        "CSV 文件 (*.csv);;所有文件 (*.*)",
    )
    if filepath:
        try:
            df.to_csv(filepath, index=False, encoding="utf-8-sig")
            from ui.logger import log_info
            log_info(f"导出 CSV 成功: {filepath}，共 {len(df)} 行")
            QMessageBox.information(parent, "导出成功", f"已成功导出到：\n{filepath}")
        except Exception as e:
            from ui.logger import log_error
            log_error(f"导出 CSV 失败: {e}")
            QMessageBox.critical(parent, "导出失败", f"导出 CSV 文件失败：\n{e}")
