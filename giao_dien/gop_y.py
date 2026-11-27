# -*- coding: utf-8 -*-
"""Ghi góp ý theo chủ đề mà không hỏi thông tin cá nhân."""
import streamlit as st

from giao_dien.hoi_dap_ui import ghi_phan_hoi_khong_dinh_danh


@st.fragment
def khung_gop_y() -> None:
    chu_de = {
        "gop_y_thao_tac": "Khó tìm thủ tục hoặc thao tác",
        "gop_y_am_thanh": "Khó nghe hoặc không phát được âm thanh",
        "gop_y_mang": "Trang tải chậm hoặc hay mất kết nối",
        "gop_y_noi_dung": "Hướng dẫn chưa rõ hoặc cần kiểm tra lại",
    }
    with st.form("is18_gop_y", clear_on_submit=True):
        lua_chon = st.radio("Bà con gặp khó khăn gì?", list(chu_de), format_func=chu_de.__getitem__)
        gui = st.form_submit_button("Gửi góp ý", type="primary", use_container_width=True)
    if gui:
        if ghi_phan_hoi_khong_dinh_danh(lua_chon, {"ma_ngon_ngu": (st.session_state.get("cac_ngon_ngu") or ["viet"])[0]}):
            st.success("Cảm ơn bà con đã gửi góp ý.")
        else:
            st.error("Chưa lưu được góp ý. Bà con thử lại sau nhé.")


st.title("Góp ý")
st.caption("Chọn một chủ đề để gửi góp ý ẩn danh về website.")
khung_gop_y()
