"""Streamlit entry point."""

import streamlit as st

from app.services.container import Services, build_services
from app.ui.pages import export_page, import_page, review, search
from config.settings import Settings

st.set_page_config(page_title="工业级产量数据采集 Demo", layout="wide")
st.title("工业级产量数据采集 Demo")


@st.cache_resource
def services() -> Services:
    return build_services(Settings())


import_tab, review_tab, search_tab, export_tab = st.tabs(
    ["批量导入", "人工复核", "查询追溯", "XLSX 导出"]
)
with import_tab:
    import_page.render(services().imports)
with review_tab:
    review.render(services().reviews)
with search_tab:
    search.render(services().queries)
with export_tab:
    export_page.render(services().exports, services().settings.exports_root)
