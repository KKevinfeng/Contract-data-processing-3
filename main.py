"""合同数据处理工具 - 入口文件 (PySide6 版本)"""

import sys
import os
import platform
import warnings
from datetime import datetime

from PySide6.QtWidgets import QApplication

# 屏蔽 openpyxl 默认样式警告
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# ── 尽早初始化日志 ──
from ui.logger import log_info, log_error, install_exception_hook, APP_LOGGER

install_exception_hook()

log_info("=" * 50)
log_info("程序启动")
log_info(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log_info(f"  系统: {platform.platform()}")
log_info(f"  用户: {os.environ.get('USERNAME', 'unknown')}")
log_info(f"  打包模式: {'frozen exe' if getattr(sys, 'frozen', False) else 'python 脚本'}")
log_info(f"  工作目录: {os.getcwd()}")
log_info(f"  Python: {sys.version}")
log_info(f"  日志目录: {os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')}")


def _app_icon():
    """加载应用图标（打包后与 exe 同目录，源码运行则在项目根目录）。"""
    from PySide6.QtGui import QIcon

    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), "logo.ico"))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico"))
    candidates.append(os.path.join(os.getcwd(), "logo.ico"))
    for path in candidates:
        if os.path.exists(path):
            log_info(f"应用图标: {path}")
            return QIcon(path)
    log_info("未找到 logo.ico，使用默认图标")
    return QIcon()


def main():
    try:
        log_info("正在初始化主窗口...")

        app = QApplication(sys.argv)
        app.setApplicationName("合同数据处理工具")
        app.setWindowIcon(_app_icon())

        from ui.styles import setup_app_style
        setup_app_style(app)

        from ui import MaintenanceApp
        window = MaintenanceApp()
        window.show()
        log_info("MaintenanceApp 初始化完成，进入主循环")

        sys.exit(app.exec())

    except Exception as e:
        log_error(f"程序运行异常: {e}")
        raise


if __name__ == "__main__":
    main()
