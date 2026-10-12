# Tab 开发统一风格规范（TAB_STYLE）

> **本文档是新增 / 修改任何 Tab 页、弹窗、下钻页、筛选栏之前必读的硬约束。**
>
> 目标：消除"每个 AI 各写一套"的问题 —— **同样的功能，全项目只允许一种写法**。
> 新增代码必须遵守本文档；**严禁复制第 7 节列出的"遗留写法"**。

---

## 0. 60 秒上手

新页面需要的公共能力，**只允许**从下面这些入口取：

| 需求 | 正确用法 |
|---|---|
| 主 Tab 骨架（左侧导航页） | `from ui.base_tab import QtBaseTab` → 继承 |
| 筛选栏 | `from ui.filter_bar import FilterBar` |
| 列表弹窗（按钮打开） | `from ui.dialog_base import ListDialog` |
| 下钻弹窗（继续下钻） | `from ui.dialog_base import DrillDownDialog` |
| 表单弹窗（录入 / 编辑） | `from ui.dialog_base import FormDialog` |
| 表格创建 / 列宽 / 排序规则 / 单元格格式化 | `from ui.table_kit import ...` |
| 中文提示与确认 | `from ui.msg_box import confirm, info, warn, error` |
| 导出 CSV | `from utils import export_to_csv`（主 Tab 直接用基类 `_export_csv()`） |

**禁止事项**（出现即为不合规）：

- 直接调用 `QMessageBox.question` / `QMessageBox.information` 等英文按钮弹窗；
- 自行 `self.table.doubleClicked.connect(...)`（双击必须走基类回调）；
- 自己手写筛选按钮栏、自己写列宽设置、自己 `QDialog(...)` 搭弹窗骨架；
- 在业务代码里重复写 `resizeColumnsToContents()` / `setStretchLastSection()` 等表格配置。

---

## 1. 页面四分类

| 类型 | 触发方式 | 典型页面 | 骨架类 |
|---|---|---|---|
| **A. 主 Tab** | 左侧导航栏切换 | Tab1~Tab7 | `QtBaseTab` |
| **B. 列表弹窗** | 按钮打开，展示一张表 | 重点客户、过保重点客户、客户详情、日志 | `ListDialog` |
| **C. 下钻弹窗** | 表格双击，进入下一层 | 行业：一级 → 二级 → 客户 | `DrillDownDialog` |
| **D. 表单弹窗** | 按钮打开，录入 / 编辑 | 录入重点客户、续保明细、大礼包、行业修正 | `FormDialog` |

> 判断方法：**是否被左侧导航直接挂载** → 是 = A；**是否由按钮触发且只有一张表** → B；
> **是否由表格双击触发并可能再往下钻** → C；**是否以"填表后确定/取消"为主** → D。

---

## 2. 各类页面骨架

### 2.1 A 类：主 Tab

```python
from ui.base_tab import QtBaseTab

class FooTab(QtBaseTab):
    def __init__(self, on_double_click=None, on_data_change=None):
        super().__init__(
            tab_name="Foo统计",              # 用于日志与导出文件名
            columns=["客户名称", "金额"],     # 展示列（不含 # / ★）
            on_double_click=on_double_click, # 双击回调，见 S9
            has_star=False,                  # 是否需要星标列
            search_column="客户名称",         # 需要搜索框就传，不需要传 None
        )

    def compute_data(self, raw_df):          # 唯一必须实现的方法
        return raw_df.groupby("客户名称")["金额"].sum().reset_index()
```

**固定布局顺序**：`#card` 卡片 → 搜索/筛选栏 → 表格 → 底部按钮栏。
`build()` 已内置，子类**只在需要额外按钮时**覆写，并把按钮插入搜索栏（参考 `tab_product_sales.py:66`）。

**新增页面的登记（必做）**：页面身份由 `main_window.MainWindow.TABS` 注册表统一管理：

```python
TABS = [
    #  key(稳定身份)  中文名(显示)      副标题
    ("total", "客户总金额", "按客户查看合同总额与年度趋势"),
    ("impl",  "实施单位统计", "按实施单位查看合同明细与实施情况"),
    # ...
]
```

- `key` 一经确定**不得更改**（设置持久化、页面跳转、"上次所在页"都按 key 存）；
- 中文名 / 副标题可随时调整，不影响任何逻辑；
- 导航项、页面标题、stack 挂载顺序**全部由这张注册表派生** —— 不要再单独维护导航文案列表；
- 左侧导航允许用户**拖动排序**，只改变显示顺序；stack 顺序与注册表顺序始终一致，
  因此业务代码里的 stack 下标（如卡片分支 `idx == N`）不会被拖动影响。

### 2.2 B 类：列表弹窗

```python
from ui.dialog_base import ListDialog

class StarredView(ListDialog):
    def get_dataframe(self):            # 提供数据
        return self._df

    def title(self):                    # 弹窗标题
        return "重点客户管理"

    def column_spec(self):              # 展示列（顺序即展示顺序）
        return ["客户名称", "所属行业"]

    def build_toolbar(self, layout):    # 可选：底部/标题栏额外按钮
        layout.addWidget(self.make_button("清空", "dangerBtn", self._on_clear))
```

调用方统一用：`StarredView.show(parent, df=df)`。

### 2.3 C 类：下钻弹窗

```python
from ui.dialog_base import DrillDownDialog

class SecondaryIndustryDialog(DrillDownDialog):
    def get_dataframe(self):
        return get_secondary_industries(self._raw_df, self._primary)

    def on_drill_down(self, row_dict):   # 双击某行 → 进入下一层
        CustomersDialog.show(self, raw_df=self._raw_df, primary=self._primary,
                             secondary=row_dict["二级行业"])
```

**统一规则**：标题用「上级 / 当前级」面包屑；**只传标识（字符串）+ 数据源，子窗口自己重查**，
不跨窗口直传 DataFrame；双击进入下一层；各级均为模态 `exec()`，关闭即返回上级。

### 2.4 D 类：表单弹窗

```python
from ui.dialog_base import FormDialog

class StarredInputDialog(FormDialog):
    def build_form(self, layout):
        self.editor = QTextEdit()
        layout.addWidget(self.editor)

    def validate(self) -> str | None:    # 返回错误文案则拒绝提交
        return None if self.editor.toPlainText().strip() else "请输入客户名称"

    def collect(self):
        return [n.strip() for n in self.editor.toPlainText().splitlines() if n.strip()]

StarredInputDialog.show(parent, on_submit=self._apply)
```

---

## 3. 硬约定（S1–S12）

### S1 布局顺序
所有页面统一为：**卡片(`#card`) → 搜索/筛选栏 → 表格 → 底部按钮栏**。
底部按钮栏**右对齐**，主动作按钮放最右。

### S2 数据流
主 Tab 只实现 `compute_data(raw_df) -> DataFrame`；由 `MainWindow` 调 `populate(df)` 灌数据。
**禁止**在 Tab 内直接读 Excel / 直接持有原始文件路径（Tab3 独立数据源是历史特例，新页面不得模仿）。

### S3 筛选栏
一律使用 `FilterBar`（见 `ui/filter_bar.py`）：
- 按钮文案固定为 `▽ 列名`；激活后为 `▽ 列名(N)` 且按钮高亮（`setChecked(True)`）；
- 值列表统一由 `FilterBar.values_provider` 提供，**必须包含「（空）」**表示空值；
- 多选弹窗一律用 `ui/column_filter_popup.py` 的 `ColumnFilterPopup`；
- 「清除筛选」按钮**仅在存在激活筛选时显示**。

### S4 排序
只允许**数字列**排序；`#`、`★`、列名含"名称"的列一律不可排序。
判定一律调用 `table_kit.is_sortable_column(df, col_name)`，**不得自行写规则**。

### S5 列宽
一律调用 `table_kit.apply_column_widths(table, model)`：
行数 ≤ 50 走全量 `resizeColumnsToContents()`；超过则按**表头 + 前 50 行**估算，单列上限 500px。
`★` 列固定 50px、`#` 列固定 60px、最后一列伸展。**禁止**在业务代码里手写列宽。

> 序号列默认表头为 `#`（`table_kit.SEQ_COL`）；个别页面按产品要求可用中文 `序号`
> （`table_kit.SEQ_COL_CN`，子类覆盖 `SEQ_COL = "序号"` 即可，宽度同样按 60px 固定）。

### S6 单元格格式化
一律 `table_kit.format_cell(val)`：空值 → `""`、float → `{:,.2f}`、int → `{:,}`。
需要自定义时**覆写基类的 `_fmt_val`**，不要在循环里内联格式化。

### S7 导出
一律 `utils.export_to_csv(df, parent, "名称.csv")`，导出**当前视图（筛选/排序后）**的数据。
按钮 objectName：**页面内 = `grayBtn`；弹窗底部 = `accentBtn`**；次要动作 = `ghostBtn`；危险动作 = `dangerBtn`。

### S8 弹窗
- 一律**模态**：`exec()`（`BaseDialog` 已封装）；
- 一律提供**静态 `show(parent, **kwargs)`** 入口，调用方不手动 `new`；
- 窗口属性与关闭处理一律用 `ui/dialog_utils.py` 的 `configure_dialog` / `install_close_handler`；
- 弹窗内表格同样用 `table_kit.build_table_view()` + `apply_column_widths()`。

### S9 双击
主 Tab 一律**传 `on_double_click` 回调**或**覆写 `_on_double_click`**，不得自行 connect 信号。
下钻弹窗覆写 `DrillDownDialog.on_drill_down(row_dict)`。

### S10 提示弹窗
一律用 `ui/msg_box.py`：`confirm` / `info` / `warn` / `error`。
**严禁**出现英文 `Yes/No` 按钮。

### S11 命名
统一命名，不得再造同义词：

| 用途 | 统一名称 |
|---|---|
| 填表 | `_fill_table(df)` |
| 格式化单元格 | `_fmt_val(val)` |
| 列名清洗 | `_clean_col(col)` |
| 列重排 | `_reorder_columns(cols)` |
| 取筛选列全部可选值 | `_get_filter_values(col, skip_col=None)` |

### S12 枚举与 Flag
一律使用 PySide6 枚举成员并**显式包装 Flag**：
`Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)`；
对齐用 `Qt.AlignmentFlag.AlignCenter`。**不得**传裸 int（如 `headerData(c, 1, 0)` 会 TypeError）。

---

## 4. 公共组件清单

| 模块 | 提供 |
|---|---|
| `ui/base_tab.py` | `QtBaseTab`（A 类骨架）、`TabSearchBar` |
| `ui/table_kit.py` | `build_table_view`、`apply_column_widths`、`is_sortable_column`、`format_cell`、`HeaderClearFilter`、常量 `SEQ_COL`/`STAR_COL` |
| `ui/filter_bar.py` | `FilterBar`（筛选按钮栏） |
| `ui/dialog_base.py` | `BaseDialog`、`ListDialog`、`DrillDownDialog`、`FormDialog` |
| `ui/column_filter_popup.py` | `ColumnFilterPopup`（列多选弹窗，唯一实现） |
| `ui/msg_box.py` | `confirm` / `info` / `warn` / `error` / `show_about` |
| `ui/dialog_utils.py` | `configure_dialog` / `install_close_handler` |
| `ui/styles.py` | 主题色、字体、全局 QSS（objectName 见 S7） |

---

## 5. 新增页面自查清单

- [ ] 页面类型判定正确（A/B/C/D），用了对应骨架类
- [ ] 使用了 `table_kit.build_table_view()`，没有手写 `QTableView` 配置
- [ ] 列宽走 `apply_column_widths()`，没有手写 `resizeColumnsToContents`
- [ ] 排序走 `is_sortable_column()` 规则
- [ ] 如有筛选：用了 `FilterBar` + `ColumnFilterPopup`，含「（空）」
- [ ] 如有弹窗：`exec()` 模态 + 静态 `show()` + `configure_dialog`/`install_close_handler`
- [ ] 所有提示走 `ui/msg_box.py`，无英文 Yes/No
- [ ] 导出按钮 objectName 符合 S7
- [ ] 双击走回调/覆写，没有自行 `connect`
- [ ] 命名符合 S11
- [ ] `README.md` 项目结构已登记新文件；`CHANGELOG.txt` 已记录

---

## 6. 历史遗留（待收敛，新代码禁止模仿）

| # | 遗留写法 | 位置 | 目标 |
|---|---|---|---|
| 1 | Tab3/Tab4 未继承 `QtBaseTab`，各自手写筛选栏/排序/导出 | `tab_expiry_stats.py`、`tab_renewal_analysis.py` | 迁移到 `QtBaseTab` + `FilterBar` |
| 2 | 非模态 `show()` 弹窗（全项目唯一） | `starred_input_dialog.py:75` | 改 `FormDialog`（模态） |
| 3 | 三份手写排序副本，规则与基类不一致 | `tab_expiry_stats.py`、`tab_renewal_analysis.py`、`expiry_starred_view.py` | 统一走 `table_kit` |
| 4 | 导出按钮 objectName 混用 `grayBtn`/`accentBtn`/`ghostBtn` | 各弹窗 | 按 S7 统一 |
| 5 | `QMessageBox` 裸调用与 `msg_box` 混用（同文件并存） | `merge_dialog.py`、`starred_view.py`、`tab_industry.py` | 全部改 `msg_box` |
| 6 | 列宽逻辑重复 7 处 | `base_tab.py`、`tab_product_sales.py`、`tab_customer_profile.py`、`tab_industry.py`、`starred_view.py`、`detail_window.py`、`expiry_starred_view.py` | 统一 `apply_column_widths` |
| 7 | 方法命名分裂（`_format_cell` vs `_fmt_val` 等） | `base_tab.py` vs `tab_expiry_stats.py` / `expiry_starred_view.py` | 按 S11 统一 |
| 8 | 弹窗无统一基类，`configure_dialog`/`install_close_handler` 到处重复 | 各弹窗文件 | 改 `BaseDialog` 子类 |
| 9 | Tab3/Tab4 无搜索框 | `tab_expiry_stats.py`、`tab_renewal_analysis.py` | 补 `search_column` |
| 10 | 星标列位置硬编码第 0 列、客户名硬编码第 2 列 | `base_tab.py:66,264` | 改为按 `STAR_COL`/名称列定位 |
