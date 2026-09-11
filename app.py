# -*- coding: utf-8 -*-
"""LUẬT GẦN BẢN — điểm vào duy nhất của ứng dụng.
"Không để khoảng cách số trở thành khoảng cách công lý"

File này chỉ làm 3 việc: dựng header, xử lý đăng nhập, và quyết định
người đang dùng được vào những trang nào (st.navigation).

Chạy:  python -m streamlit run app.py
"""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from core import auth

ROOT = Path(__file__).resolve().parent

st.set_page_config(page_title="Luật Gần Bản", page_icon="⚖️",
                   layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
  .stApp, p, h1,h2,h3,h4,h5,h6, label, button, input, .stMarkdown, .stText, .stTextArea
      { font-family: 'Times New Roman', Times, serif !important; }
  [data-testid="stExpanderToggleIcon"], [data-testid="stIconMaterial"],
  [data-testid="stFileUploadDropzone"] span, .st-icon, .material-icons,
  .material-symbols-rounded
      { font-family: 'Material Symbols Rounded','Material Icons',sans-serif !important; }
  .the-tra-loi { font-size: 20px; line-height: 1.6; }
  .the-tra-loi b { color: #003366; }
  div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 10px; }
  /* nút micro to, dễ bấm cho người lớn tuổi */
  [data-testid="stAudioInput"] { transform: scale(1.15); transform-origin: left center; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _logo_b64() -> str:
    p = ROOT / "logo_hoc_vien.png"
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def header() -> None:
    b64 = _logo_b64()
    img = (f'<img src="data:image/png;base64,{b64}" style="width:75px;height:auto;'
           'object-fit:contain;">' if b64 else
           '<div style="width:75px;text-align:center;color:gray;">[Logo]</div>')
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:5px;">
      <div style="flex-shrink:0;">{img}</div>
      <div style="line-height:1.3;">
        <div style="color:#8B0000;font-size:13px;font-weight:bold;text-transform:uppercase;">
          Học viện Hành chính và Quản trị Công</div>
        <div style="color:#003366;font-size:18px;font-weight:bold;margin-top:2px;">
          DỰ ÁN LUẬT GẦN BẢN</div>
        <div style="font-style:italic;color:#444;font-size:12px;margin-top:2px;">
          "Không để khoảng cách số trở thành khoảng cách công lý"</div>
      </div>
    </div><hr style="margin:5px 0 18px 0;border:0.5px solid #ddd;">
    """, unsafe_allow_html=True)


header()

# ======================================================= ĐĂNG NHẬP (thanh bên)
auth.khoi_tao_mac_dinh()          # lần chạy đầu tiên: tạo 4 tài khoản mặc định

with st.sidebar:
    u = auth.nguoi_dang_nhap()
    if u:
        st.markdown(f"**{u.get('mo_ta') or u['ten_dang_nhap']}**")
        st.caption(f"`{u['ten_dang_nhap']}` · "
                   f"{'Quản trị viên' if u['vai_tro'] == 'admin' else 'Cán bộ'}")
        if u.get("phai_doi_mk"):
            st.warning("Bạn cần đổi mật khẩu.", icon="🔑")
        if st.button("Đăng xuất", use_container_width=True):
            del st.session_state["nguoi_dung"]
            st.rerun()
    else:
        st.markdown("### Đăng nhập cán bộ")
        st.caption("Bà con không cần đăng nhập — cứ dùng trang Hỏi đáp.")
        with st.form("dang_nhap", clear_on_submit=False):
            ten = st.text_input("Tên đăng nhập")
            mk = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("Đăng nhập", type="primary",
                                     use_container_width=True):
                nd = auth.kiem_tra_dang_nhap(ten, mk)
                if nd:
                    st.session_state["nguoi_dung"] = nd
                    st.rerun()
                else:
                    st.error("Sai tên đăng nhập hoặc mật khẩu.")

# ============================================================ ĐIỀU HƯỚNG
if not hasattr(st, "navigation") or not hasattr(st, "Page"):
    st.error(
        "Phiên bản Streamlit đang cài quá cũ (cần từ **1.36** trở lên).\n\n"
        "Mở terminal ở thư mục dự án và chạy:\n\n"
        "```\npip install -U streamlit\n```"
    )
    st.stop()

trang = [st.Page("giao_dien/cong_dan.py", title="Hỏi đáp thủ tục",
                 icon=":material/record_voice_over:", default=True)]

u = auth.nguoi_dang_nhap()
if u and (auth.la_admin() or auth.quyen_cua(u)):
    trang.append(st.Page("giao_dien/quan_tri.py", title="Quản trị kho",
                         icon=":material/settings:"))
if auth.la_admin():
    trang.append(st.Page("giao_dien/tai_khoan.py", title="Tài khoản & phân quyền",
                         icon=":material/manage_accounts:"))

st.navigation(trang, position="sidebar").run()
