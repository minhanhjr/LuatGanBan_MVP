# -*- coding: utf-8 -*-
"""Tra cứu bằng danh sách hoặc bàn phím, tách khỏi trang micro."""
from __future__ import annotations

import streamlit as st

from core.config import DANH_MUC_THU_TUC
from giao_dien.hoi_dap_ui import chon_giong_nghe, hien_ket_qua_da_luu, xu_ly_cau_noi

KHOA_KET_QUA = "is18_ket_qua_tra_cuu"


@st.fragment
def khung_tra_cuu() -> None:
    cach_tra_cuu = st.radio(
        "Cách tra cứu", ["Chọn từ danh sách", "Gõ câu hỏi"],
        index=int(st.query_params.get("cach") == "go"), horizontal=True,
    )
    cac_tieng = chon_giong_nghe(key="is18_tieng_tra_cuu")

    if cach_tra_cuu == "Gõ câu hỏi":
        with st.form("is18_go_cau_hoi"):
            cau_hoi = st.text_area("Bà con cần hỏi việc gì?",
                                   placeholder="Ví dụ: Tôi muốn làm giấy khai sinh", height=90)
            gui = st.form_submit_button("Gửi câu hỏi", type="primary", use_container_width=True)
        if gui and cau_hoi.strip():
            xu_ly_cau_noi(cau_hoi.strip(), khoa=KHOA_KET_QUA, cac_tieng=cac_tieng)
            st.rerun()
        return

    from core import kb

    tat_ca = [tt for tt in kb.load_kb() if not tt.an and tt.ten]
    if not tat_ca:
        st.info("Chưa có thủ tục để chọn. Bà con có thể gõ câu hỏi hoặc hỏi cán bộ.")
        return
    nhom = st.selectbox("Nhóm thủ tục", [""] + [ma for ma in DANH_MUC_THU_TUC
                                              if any(ma in tt.nhom for tt in tat_ca)],
                        format_func=lambda ma: DANH_MUC_THU_TUC.get(ma, "Tất cả"))
    tu_khoa = st.text_input("Tìm theo tên hoặc mã thủ tục", key="is18_tim_thu_tuc").strip().casefold()
    danh_sach = [tt for tt in tat_ca if (not nhom or nhom in tt.nhom)
                 and (tu_khoa in tt.ten.casefold() or tu_khoa in tt.ma_thu_tuc.casefold())]
    if not danh_sach:
        st.info("Không tìm thấy thủ tục phù hợp. Bà con thử từ khóa khác.")
        return
    lua_chon = st.selectbox("Thủ tục cụ thể", danh_sach,
                           format_func=lambda tt: f"{tt.ten} ({tt.ma_thu_tuc})" if tt.ma_thu_tuc else tt.ten)
    if st.button("Xem hướng dẫn", type="primary", use_container_width=True):
        xu_ly_cau_noi(lua_chon.ten, khoa=KHOA_KET_QUA, cac_tieng=cac_tieng,
                      thu_tuc=lua_chon if lua_chon.key else None)
        st.rerun()


st.title("Chọn thủ tục")
khung_tra_cuu()
hien_ket_qua_da_luu(KHOA_KET_QUA)
