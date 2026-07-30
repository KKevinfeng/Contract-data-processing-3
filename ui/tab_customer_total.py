"""Tab 1：客户总金额统计（按年份分列），支持标星重点客户。"""

from ui.base_tab import QtBaseTab
from data_processor import compute_customer_total


class CustomerTotalTab(QtBaseTab):
    """客户总金额统计页 —— 双击客户名称可查看合同详情，点击 ★ 列标星。"""

    def __init__(self, on_double_click=None,
                 on_star_toggle=None, get_starred_names=None):
        super().__init__(
            tab_name="客户总金额统计",
            columns=["客户名称", "合同总金额"],
            on_double_click=on_double_click,
            has_star=True,
            on_star_toggle=on_star_toggle,
            get_starred_names=get_starred_names,
            search_column="最终客户名称",
        )

    def compute_data(self, raw_df):
        return compute_customer_total(raw_df)
