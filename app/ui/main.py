"""Streamlit entry point."""

import streamlit as st

from app.services.container import Services, build_services
from app.ui.pages import import_page, review
from config.settings import Settings

st.set_page_config(page_title="工业级产量数据采集 Demo", layout="wide")
st.title("工业级产量数据采集 Demo")


@st.cache_resource
def services() -> Services:
    return build_services(Settings())


import_tab, review_tab = st.tabs(["批量导入", "人工复核"])
with import_tab:
    import_page.render(services().imports)
with review_tab:
    review.render(services().reviews)
