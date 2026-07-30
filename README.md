# 合同数据处理工具

合同数据处理桌面应用，支持多维度的合同统计、客户分类、行业分析及过保情况追踪。内置完整日志系统，所有关键操作和异常均可追溯。

## 项目结构

```
maintenance-repurchase-1/
│
├── main.py                         # 程序入口，初始化日志、启动 GUI
├── data_processor.py               # 核心数据处理逻辑（统计计算、合同分类、年份提取）
├── utils.py                        # 工具函数（合同编号解析、产品行拆分、年份提取、CSV 导出）
├── requirements.txt                # Python 依赖清单
├── build.ps1                       # Nuitka 打包脚本（自动检测 Python 环境）
├── CHANGELOG.txt                   # 版本更新日志
│
├── merge_rules.json                # 产品合并规则持久化文件
├── industry_dict.json              # 行业数据字典（一级/二级行业映射）
├── industry_overrides.json         # 行业覆盖规则（人工修正客户行业）
├── starred_customers.xlsx          # 重点客户缓存文件
├── renewal_details.xlsx            # 续保明细缓存（已续保合同编号）
├── gift_channels.xlsx              # 大礼包渠道标记缓存
│
├── logs/                           # 运行日志目录（按天归档，5MB 轮转）
│   ├── run_YYYY-MM-DD.log          # 运行日志
│   └── error.log                   # 错误日志
│
└── ui/                             # 界面模块
    ├── __init__.py                 # 包初始化，导出公共常量（字体、颜色）
    ├── main_window.py              # 主窗口：Tab 容器、菜单栏、导入进度、碰撞检测、日志入口
    ├── base_tab.py                 # Tab 基类：Treeview 表格、排序、筛选、搜索、Star、CSV 导出
    │
    ├── tab_customer_total.py       # Tab1 — 客户总金额统计（分年透视）
    ├── tab_customer_category.py    # Tab2 — 客户分类金额统计（维保/产品/服务）
    ├── tab_expiry_stats.py         # Tab3 — 过保情况统计（含意向筛选）
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
    ├── starred_cache.py            # 重点客户缓存读写
    ├── expiry_starred_view.py      # 重点客户过保合同弹窗
    ├── log_view.py                 # 查看运行日志弹窗
    ├── logger.py                   # 日志系统（按天归档、级别过滤、文件轮转）
    ├── progress_popup.py           # 导入进度弹窗
    └── styles.py                   # UI 样式常量
```

## 功能概览

| Tab | 名称 | 功能 |
|-----|------|------|
| Tab1 | 客户总金额统计 | 按客户分年统计合同总金额，支持标星重点客户 |
| Tab2 | 客户分类金额统计 | 按维保(M)/产品(P)/服务(S)三类统计各客户金额 |
| Tab3 | 过保情况统计 | 追踪重点客户的续保意向和不续保原因 |
| Tab4 | 过保数据分析 | P类合同续保追踪、大礼包渠道红色高亮标记 |
| Tab5 | 产品销量统计 | 按产品名称汇总售卖台数，支持产品名称合并 |
| Tab6 | 行业统计 | 按一级行业统计客户数量、总金额及分年金额，支持下钻到二级行业和客户明细 |
| Tab7 | 客户画像 | 展示客户综合画像，含行业分类、标签等完整信息 |

## 运行环境

- Python 3.10+
- 依赖：`pip install -r requirements.txt`

## 启动方式

```bash
# 开发模式
python main.py

# 打包为 exe（Nuitka）
# 方式一：使用项目自带脚本（推荐）
.\build.ps1

# 方式二：手动执行
python -m nuitka --standalone --windows-console-mode=disable --enable-plugin=tk-inter --include-package-data=customtkinter --include-data-files="CHANGELOG.txt=CHANGELOG.txt" --include-data-files="README.md=README.md" --remove-output --output-dir=dist main.py
```

> **打包说明**：
> - 使用 Nuitka 打包为独立 exe，输出到 `dist\` 目录。
> - 不要使用 PyInstaller，会导致 customtkinter 主题问题。
> - 推荐用 `build.ps1` 打包，它会自动在临时干净目录构建，避免把本地缓存文件（`industry_dict.json`、`industry_overrides.json`、`*_cache.xlsx` 等）打包进 exe。
> - 若手动打包，请先把以下运行时自动生成的文件从项目目录移走：
>   `industry_dict.json`、`industry_overrides.json`、`merge_rules.json`、`starred_customers.xlsx`、`renewal_details.xlsx`、`gift_channels.xlsx`。
