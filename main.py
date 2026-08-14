"""合同数据处理工具 - 入口文件 (PySide6 版本)"""

import sys
import os
import platform
import warnings
from datetime import datetime

from PySide6.QtWidgets import QApplication

# 屏蔽 openpyxl 默认样式警告
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# 性能优化：缩小 GIL 切换间隔，让后台线程（读取大 Excel / 统计）更频繁让出 GIL，
# 保证主线程 Qt 事件循环在导入期间保持响应，避免 UI 冻结卡顿。
# 默认 5ms 改小到 1ms，代价是极小 CPU 开销，换取 UI 流畅。
try:
    sys.setswitchinterval(0.001)
except Exception:
    pass

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
        from ui.progress_popup import ProgressPopup
        from PySide6.QtCore import QTimer

        window = MaintenanceApp()
        window.show()

        # 启动时自动加载历史数据缓存（若存在）。
        # 说明：
        #  - 缓存加载使用线程 + QTimer 轮询，必须在事件循环（app.exec）运行后才能推进，
        #    因此用 singleShot 延迟到 show 之后、事件循环内触发，不阻塞窗口显示。
        #  - 若检测到有效缓存，先展示"正在读取历史数据"启动弹窗；缓存内部各数据源会
        #    自行更新进度，全部加载完成后由窗口统一关闭该启动弹窗（见 _finish_cache_load）。
        from ui import cache_manager

        snap = cache_manager.scan_cache()
        cache_manager.clean_junk_files(snap)
        has_cache = snap.main.valid or snap.expiry.valid

        if has_cache:
            # 用户点击 × 关闭弹窗时取消后台缓存导入（见 _cancel_cache_load）
            splash = ProgressPopup(
                window, title="正在读取历史数据...", on_close=window._cancel_cache_load
            )
            splash.set_progress(0.0, "正在检查历史数据缓存...")
            window._startup_splash = splash
            QTimer.singleShot(120, window.try_load_all_caches)
        else:
            log_info("未检测到有效缓存，等待手动导入")

        log_info("MaintenanceApp 初始化完成，进入主循环")

        sys.exit(app.exec())

    except Exception as e:
        log_error(f"程序运行异常: {e}")
        raise


if __name__ == "__main__":
    main()
