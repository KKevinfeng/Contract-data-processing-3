# 合同数据处理工具

合同数据处理桌面应用（PySide6），支持多维度的合同统计、客户分类、行业分析及过保情况追踪。内置完整日志系统，所有关键操作和异常均可追溯。

> ### ⚠️ 必读入口（发版 / 更新版本号 / 打包前请先阅读）
>
> 涉及 **发版、更新版本号、打包 exe** 时，**必须先阅读 [`RELEASE.md`](./RELEASE.md)**，并严格按其 §6「一键发版」流程执行（含版本号 A.B.C.D 规则、文件同步、二次确认、git tag、push 与打包命令）。
>
> 本工具任何改动都需同步更新 `CHANGELOG.txt`；新增文件需同步更新本文件「项目结构」与「功能概览」。

## 项目结构

```
Contract-data-processing-3/
│
├── main.py                         # 程序入口：初始化日志、应用样式、启动 GUI
├── data_processor.py               # 核心数据处理逻辑（统计计算、合同分类、年份提取）
├── utils.py                        # 工具函数（合同编号解析、产品行拆分、年份提取、CSV 导出）
├── requirements.txt                # Python 依赖清单
├── build.ps1                       # Nuitka 打包脚本（自动检测 Python 环境、版本号命名输出）
├── RELEASE.md                      # 发版指引（版本号 A.B.C.D 规则、一键发版流程）※发版前必读
├── CHANGELOG.txt                   # 版本更新日志
├── logo.ico                        # 应用图标（打包后 exe 图标 + 窗口左上角图标）
│
├── merge_rules.json                # 产品合并规则持久化文件（运行时生成）
├── industry_dict.json              # 行业数据字典（一级/二级行业映射，运行时生成）
├── industry_overrides.json         # 行业覆盖规则（人工修正客户行业，运行时生成）
├── starred_customers.xlsx          # 重点客户缓存文件（运行时生成）
├── renewal_details.xlsx            # 续保明细缓存（已续保合同编号，运行时生成）
├── gift_channels.xlsx              # 大礼包渠道标记缓存（运行时生成）
│
├── logs/                           # 运行日志目录（按天归档，5MB 轮转）
│   ├── run_YYYYMMDD.log            # 运行日志
│   └── error.log                   # 错误日志
│
├── tmp/                            # 导入文件缓存目录（运行时生成）
│   ├── main_data.xlsx              # 工具首页导入的主合同文件缓存
│   └── expiry_data.xlsx            # Tab3 过保文件缓存
│
├── dist/                           # 打包输出目录（build.ps1 生成，按版本号命名）
│
└── ui/                             # 界面模块（PySide6）
    ├── __init__.py                 # 包入口，导出 MaintenanceApp
    ├── main_window.py              # 主窗口：Sidebar 导航、顶部状态栏、版本号、日志入口
    ├── base_tab.py                 # Tab 基类：QTableView 表格、排序、筛选、搜索、星标、CSV 导出
    ├── styles.py                   # 全局 QSS 样式系统（按钮/表格/弹窗等）
    ├── settings.py                 # 应用设置
    ├── msg_box.py                  # 统一消息框封装（信息/警告/错误/确认）
    ├── dialog_utils.py             # 对话框工具（中心定位、日期选择等）
    │
    ├── tab_customer_total.py       # Tab1 — 客户总金额统计（分年透视）
    ├── tab_customer_category.py    # Tab2 — 客户分类金额统计（维保/产品/服务）
    ├── tab_expiry_stats.py         # Tab3 — 过保情况统计（独立数据源、列筛选、意向跟踪）
    ├── tab_renewal_analysis.py     # Tab4 — 过保数据分析（P类合同续保追踪、大礼包标记）
    ├── tab_product_sales.py        # Tab5 — 产品销量统计（含产品合并规则）
    ├── tab_industry.py             # Tab6 — 行业统计（客户数/金额/分年，支持下钻）
    ├── tab_customer_profile.py     # Tab7 — 客户画像展示（行业分类、金额、产品偏好）
    │
    ├── industry_dict.py            # 行业数据字典管理（增删一级/二级行业）
    ├── industry_overrides.py       # 行业覆盖规则管理（客户行业人工修正）
    │
    ├── detail_window.py            # 客户合同详情弹窗（双击客户行打开）
    ├── merge_dialog.py             # 产品合并规则编辑弹窗
    ├── column_filter_popup.py      # 列多选筛选弹窗（Tab3 及过保弹窗共用）
    ├── starred_view.py             # 查看重点客户弹窗
    ├── starred_input_dialog.py     # 手动添加重点客户弹窗
    ├── starred_cache.py            # 重点客户缓存读写（starred_customers.xlsx）
    ├── expiry_starred_view.py      # 重点客户过保合同弹窗
    ├── log_view.py                 # 查看运行日志/错误日志弹窗
    ├── logger.py                   # 日志系统（按天归档、级别过滤、文件轮转）
    ├── cache_manager.py            # 导入文件缓存管理（tmp/ 目录、自动加载、防锁死）
    └── progress_popup.py           # 导入进度弹窗
```

## 功能概览

| Tab | 名称 | 功能 |
|-----|------|------|
| Tab1 | 客户总金额统计 | 按客户分年统计合同总金额，支持标星重点客户 |
| Tab2 | 客户分类金额统计 | 按维保(M)/产品(P)/服务(S)三类统计各客户金额，双击金额下钻明细 |
| Tab3 | 过保情况统计 | 独立 Excel 数据源，动态列筛选，重点客户过保筛选与续保意向跟踪 |
| Tab4 | 过保数据分析 | P类合同续保追踪、续保明细管理、大礼包渠道红色高亮标记 |
| Tab5 | 产品销量统计 | 按产品名称汇总售卖台数，支持产品名称合并规则 |
| Tab6 | 行业统计 | 按一级行业统计客户数量、总金额及分年金额，逐层下钻二级行业和客户明细 |
| Tab7 | 客户画像 | 展示客户综合画像，含行业分类、金额、产品偏好等完整信息 |

## 历史数据缓存

工具会记忆上次导入的文件，下次打开自动加载，无需手动再次导入：

- 首次通过界面人工导入主合同文件 / Tab3 过保文件时，工具会把文件复制到运行目录下的 `tmp/` 缓存目录，并统一命名为 `main_data.xlsx` / `expiry_data.xlsx`。
- 下次启动时自动检测 `tmp/` 目录，若存在有效缓存则弹出"正在读取历史数据"弹窗并自动加载，不阻塞主界面。
- 只有用户主动重新导入（点击"导入合同数据" / Tab3 "浏览..."）才会覆盖缓存。
- **防锁死**：只识别固定命名的缓存文件，忽略/自动清理 `tmp/` 中的不相干文件；读取采用线程 + 超时 + 大小限制（单文件 ≤200MB），缓存损坏或为空时自动清除并跳过，不会导致进程卡死。

## 运行环境

- Python 3.10+
- 依赖：`pip install -r requirements.txt`（pandas、openpyxl、PySide6）

## 启动方式

```bash
# 开发模式
python main.py

# 打包为 exe（Nuitka）
# 方式一：使用项目自带脚本（推荐）
.\build.ps1

# 方式二：手动执行
python -m nuitka --standalone --windows-console-mode=disable --enable-plugin=pyside6 --include-data-files="CHANGELOG.txt=CHANGELOG.txt" --include-data-files="README.md=README.md" --include-data-files="logo.ico=logo.ico" --windows-icon-from-ico=logo.ico --remove-output --output-dir=dist main.py
```

> **打包说明**：
> - 使用 Nuitka 打包为独立 exe，输出到 `dist\v{版本号}\` 目录（版本号自动从 `ui/main_window.py` 提取）。
> - 推荐用 `build.ps1` 打包，它会在临时干净目录构建，避免把本地缓存文件（`industry_dict.json`、`industry_overrides.json`、`*_cache.xlsx` 等）打包进 exe。
> - 若手动打包，请先把以下运行时自动生成的文件从项目目录移走：
>   `industry_dict.json`、`industry_overrides.json`、`merge_rules.json`、`starred_customers.xlsx`、`renewal_details.xlsx`、`gift_channels.xlsx`。
