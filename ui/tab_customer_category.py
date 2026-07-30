"""Tab 2：客户分类金额统计（维保 / 产品 / 服务）"""

from ui.base_tab import QtBaseTab
from data_processor import compute_customer_category


class CustomerCategoryTab(QtBaseTab):
    """客户分类金额统计页 —— 双击金额列可查看对应类型合同详情。"""

    CONTRACT_TYPE_MAP = {
        "维保合同总金额": "M",
        "产品合同总金额": "P",
        "服务合同总金额": "S",
    }
    TYPE_LABEL = {"M": "维保", "P": "产品", "S": "服务"}

    def __init__(self, on_double_click=None):
        super().__init__(
            tab_name="客户分类金额统计",
            columns=[
                "客户名称",
                "维保合同总金额",
                "产品合同总金额",
                "服务合同总金额",
                "合计总金额",
            ],
            on_double_click=on_double_click,
            search_column="最终客户名称",
        )

    def compute_data(self, raw_df):
        return compute_customer_category(raw_df)
