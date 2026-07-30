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

    def save_sidebar_index(self, index: int) -> None:
        self._settings.setValue("sidebar/index", index)

    def load_sidebar_index(self) -> int:
        val = self._settings.value("sidebar/index", 0)
        return int(val) if val else 0

    # ── 通用读写 ──

    def set(self, key: str, value) -> None:
        self._settings.setValue(key, value)

    def get(self, key: str, default=None):
        return self._settings.value(key, default)

    def sync(self) -> None:
        self._settings.sync()
