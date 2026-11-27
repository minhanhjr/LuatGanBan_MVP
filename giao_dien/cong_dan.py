# -*- coding: utf-8 -*-
"""Trang hỏi bằng giọng nói. Chỉ xử lý giọng nói sau khi người dân thu âm."""
from __future__ import annotations

import hashlib

import streamlit as st

from giao_dien.hoi_dap_ui import chon_giong_nghe, hien_ket_qua_da_luu, loa, xu_ly_cau_noi


KHOA_KET_QUA = "is18_ket_qua_giong_noi"


@st.fragment
def khung_micro() -> None:
    st.markdown(
        '<div style="text-align:center;font-size:26px;font-weight:bold;'
        'color:#003366;margin:10px 0 2px 0;">Bấm vào đây để nói</div>',
        unsafe_allow_html=True,
    )
    ban_ghi = st.audio_input("Bấm micro để nói", label_visibility="collapsed", key="is18_micro")
    cac_tieng = chon_giong_nghe(key="is18_tieng_micro")
    if ban_ghi is None:
        return

    raw = ban_ghi.getvalue()
    if len(raw) <= 50:
        if raw:
            st.warning("Bà con bấm micro rồi nói rõ hơn một chút nhé.")
        return
    van_tay = hashlib.sha256(raw).hexdigest()
    if st.session_state.get("is18_audio_da_xu_ly") == van_tay:
        return
    st.session_state["is18_audio_da_xu_ly"] = van_tay

    from core.stt import nghe

    ma = cac_tieng[0]
    try:
        with st.spinner("Đang nghe bà con nói…"):
            van_ban, _ = nghe(ban_ghi, tieng_mong=ma == "mong", ngon_ngu=ma)
            if van_ban and ma in ("mong", "tay"):
                dong_vi = next((dong[3:].strip() for dong in van_ban.splitlines()
                                if dong.startswith("VI:") and dong[3:].strip()), "")
                if dong_vi:
                    van_ban = dong_vi
                else:
                    from core.translate import dich_sang_viet, dich_tay_sang_viet

                    dich = dich_tay_sang_viet if ma == "tay" else dich_sang_viet
                    van_ban = dich(van_ban)
    except Exception:
        van_ban = ""
    if not (van_ban or "").strip():
        st.session_state[KHOA_KET_QUA] = None
        st.session_state["is18_micro_khong_ro"] = True
    else:
        st.session_state.pop("is18_micro_khong_ro", None)
        xu_ly_cau_noi(van_ban.strip(), khoa=KHOA_KET_QUA, cac_tieng=cac_tieng)
    st.rerun()


khung_micro()
if st.session_state.get("is18_micro_khong_ro"):
    nhac = "Máy chưa nghe rõ, bà con bấm nói lại nhé."
    st.error(nhac)
    loa(nhac, nhan="Nghe lại lời nhắc", key="is18_micro_nghe_nhac")
elif kq := st.session_state.get(KHOA_KET_QUA):
    st.success(f"Bà con nói: *{kq['cau_noi']}*")
    hien_ket_qua_da_luu(KHOA_KET_QUA)
