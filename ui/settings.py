"""应用设置管理 — 基于 QSettings 的持久化配置"""

from __future__ import annotations

from PySide6.QtCore import QSettings, QByteArray


class AppSettings:
    """应用设置管理器（单例）"""

    _instance: AppSettings | None = None

    def __new__(cls) -> AppSettings:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._settings = QSettings(
                "MaintenanceRepurchase", "ContractTool"
            )
        return cls._instance

    # ── 窗口布局 ──

    def save_window_geometry(self, geometry: QByteArray) -> None:
        self._settings.setValue("window/geometry", geometry)

    def load_window_geometry(self) -> QByteArray | None:
        return self._settings.value("window/geometry")

    def save_window_state(self, state: QByteArray) -> None:
        self._settings.setValue("window/state", state)

    def load_window_state(self) -> QByteArray | None:
        return self._settings.value("window/state")

    # ── 最近文件 ──

    def save_last_file(self, filepath: str) -> None:
        self._settings.setValue("last/file", filepath)

    def load_last_file(self) -> str:
        val = self._settings.value("last/file", "")
        return str(val) if val else ""

    # ── 侧边栏 ──
    # 注意：这里存的是 Tab 的 key（稳定身份）而不是行号 —— 导航支持拖动排序后，
    # 行号会随顺序变化，只有 key 能稳定定位页面（见 TAB_STYLE.md 相关说明）。

    def save_nav_order(self, keys: list[str]) -> None:
        self._settings.setValue("sidebar/order", list(keys))

    def load_nav_order(self) -> list[str]:
        val = self._settings.value("sidebar/order", [])
        if isinstance(val, str):        # QSettings 单个元素会退化成字符串
            val = [val]
        return [str(v) for v in (val or [])]

    def save_last_tab(self, key: str) -> None:
        self._settings.setValue("sidebar/last_tab", key)

    def load_last_tab(self) -> str:
        return str(self._settings.value("sidebar/last_tab", "") or "")

    # ── 通用读写 ──

    def set(self, key: str, value) -> None:
        self._settings.setValue(key, value)

    def get(self, key: str, default=None):
        return self._settings.value(key, default)

    def sync(self) -> None:
        self._settings.sync()
