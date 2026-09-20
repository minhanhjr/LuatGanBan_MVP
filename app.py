# -*- coding: utf-8 -*-
"""LUẬT GẦN BẢN — điểm vào duy nhất của ứng dụng.
"Chuyển đổi số: không để ai bị bỏ lại phía sau"

File này chỉ làm 3 việc: dựng header, xử lý đăng nhập, và quyết định
người đang dùng được vào những trang nào (st.navigation).

Chạy:  python -m streamlit run app.py
"""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import html as _html

from core import auth

ROOT = Path(__file__).resolve().parent

st.set_page_config(page_title="Luật Gần Bản", page_icon="⚖️",
                   layout="centered", initial_sidebar_state="collapsed")

# ==========================================================================
# GIAO DIỆN CHUNG & TỐI ƯU HIỆU NĂNG GIAO DIỆN (Render HTML gốc siêu tốc)
# ==========================================================================
# SỬ DỤNG st.html() thay vì st.markdown() để bỏ qua bộ phân tích Markdown, tăng tốc độ render UI
st.html("""
<style>
  /* ÉP THANH TIÊU ĐỀ LUÔN NẰM TRÊN MỘT HÀNG TRÊN MỌI THIẾT BỊ */
  @media (max-width: 768px) {
      div[data-testid="stHorizontalBlock"] { display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; align-items: center !important; width: 100% !important; }
      div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] { flex: 1 1 auto !important; min-width: 0 !important; width: auto !important; }
      div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:last-child { flex: 0 0 auto !important; width: auto !important; }
  }

  /* NÚT "GIỚI THIỆU DỰ ÁN": CĂN GIỮA TUYỆT ĐỐI, VIÊN THUỐC SANG TRỌNG */
  .element-container:has([data-testid="stPageLink"]) { display: flex !important; justify-content: center !important; width: 100% !important; margin: 5px 0 !important; }
  [data-testid="stPageLink"] { align-self: center !important; margin: 0 auto !important; display: flex !important; flex-direction: row !important; justify-content: center !important; align-items: center !important; width: max-content !important; min-width: 200px !important; max-width: 90vw !important; background-color: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 40px !important; padding: 8px 24px !important; box-shadow: 0 2px 8px rgba(0,0,0,0.03) !important; transition: all 0.2s ease !important; text-decoration: none !important; }
  [data-testid="stPageLink"]:hover { background-color: #f8fafc !important; border-color: #cbd5e1 !important; box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important; transform: translateY(-1px) !important; }
  [data-testid="stPageLink"] span { white-space: nowrap !important; overflow: visible !important; text-overflow: clip !important; font-family: 'Times New Roman', Times, serif !important; font-size: 15.5px !important; color: #003366 !important; font-weight: 600 !important; letter-spacing: 0.2px !important; }

  /* Phông chữ chung */
  .stApp, p, h1, h2, h3, h4, h5, h6, label, button, input, .stMarkdown, .stText, .stTextArea { font-family: 'Times New Roman', Times, serif !important; }
  [data-testid="stExpanderToggleIcon"], [data-testid="stIconMaterial"], [data-testid="stFileUploadDropzone"] span, .st-icon, .material-icons, .material-symbols-rounded { font-family: 'Material Symbols Rounded','Material Icons',sans-serif !important; }

  /* Ẩn UI mặc định của Streamlit */
  [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="manage-app-button"], .stAppDeployButton, #MainMenu, footer, [class*="viewerBadge"], [class*="profileContainer"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
  header[data-testid="stHeader"] { background: transparent !important; height: 0 !important; min-height: 0 !important; }
  .block-container { padding-top: 1.2rem !important; padding-bottom: 3rem !important; max-width: 900px !important; }
  iframe[title="streamlit.components.v1.html"] { border: 0 !important; }
  iframe[title="streamlit.components.v1.html"][height="0"] { height: 0 !important; display: block !important; }

  /* Header dự án gọn gàng */
  .lgb-header { display: inline-flex; align-items: center; gap: 8px; margin: 0 !important; padding: 0 !important; }
  .lgb-header img { width: 32px; height: 32px; object-fit: contain; flex-shrink: 0; }
  .lgb-ten { color: #003366; font-size: 17px; font-weight: bold; letter-spacing: .2px; white-space: nowrap; }
  .lgb-slogan { color: #666; font-size: 11.5px; font-style: italic; border-left: 1px solid #ccc; padding-left: 8px; margin-left: 4px; }
  @media (max-width: 640px) { .lgb-slogan { display: none; } .lgb-ten { font-size: 15px; } }

  /* Khu ghi âm - Nút micro */
  [data-testid="stAudioInput"] { display: flex !important; justify-content: center !important; height: auto !important; min-height: 240px !important; overflow: visible !important; max-width: 560px; margin: 0 auto !important; }
  [data-testid="stAudioInput"] > div { flex-direction: column !important; align-items: center !important; justify-content: flex-start !important; gap: 14px !important; width: 100% !important; height: auto !important; min-height: 230px !important; overflow: visible !important; border: none !important; background: transparent !important; box-shadow: none !important; padding-top: 10px !important; }
  [data-testid="stAudioInput"] > div > div { justify-content: center !important; }
  [data-testid="stAudioInput"] [data-testid="stElementToolbar"] { display: none !important; }
  [data-testid="stAudioInputActionButton"] { width: 96px !important; height: 96px !important; min-width: 96px !important; min-height: 96px !important; border-radius: 50% !important; background: #1B7F4B !important; border: 4px solid #d6efe0 !important; box-shadow: 0 6px 18px rgba(27,127,75,.30) !important; animation: lgb-tho 2.4s ease-in-out infinite; position: relative !important; }
  [data-testid="stAudioInputActionButton"]::before, [data-testid="stAudioInputActionButton"]::after { content: ""; position: absolute; left: 50%; top: 50%; width: 96px; height: 96px; margin: -48px 0 0 -48px; border-radius: 50%; border: 3px solid rgba(27,127,75,.40); pointer-events: none; animation: lgb-song 2.6s ease-out infinite; }
  [data-testid="stAudioInputActionButton"]::after { animation-delay: 1.3s; }
  @keyframes lgb-song { 0% { transform: scale(1); opacity: .65; } 100% { transform: scale(1.85); opacity: 0; } }
  [data-testid="stAudioInputActionButton"]:hover { background: #15653C !important; }
  [data-testid="stAudioInputActionButton"] svg, [data-testid="stAudioInputActionButton"] path { width: 44px !important; height: 44px !important; fill: #ffffff !important; color: #ffffff !important; }
  [data-testid="stAudioInputActionButton"][aria-label*="top" i], [data-testid="stAudioInputActionButton"][title*="top" i] { background: #C62828 !important; border-color: #f7d5d5 !important; animation: lgb-thu 1.1s ease-out infinite; }
  [data-testid="stAudioInputActionButton"][aria-label*="top" i]::before, [data-testid="stAudioInputActionButton"][aria-label*="top" i]::after { display: none !important; }
  @keyframes lgb-tho { 0%,100% { transform: scale(1); } 50% { transform: scale(1.05); } }
  @keyframes lgb-thu { 0% { box-shadow: 0 0 0 0 rgba(198,40,40,.55); } 70% { box-shadow: 0 0 0 28px rgba(198,40,40,0); } 100% { box-shadow: 0 0 0 0 rgba(198,40,40,0); } }
  [data-testid="stAudioInputWaveSurfer"] { width: 100% !important; min-height: 54px !important; }
  [data-testid="stAudioInputWaveformTimeCode"] { font-size: 15px !important; }

  /* Nút chọn ngôn ngữ & Văn bản */
  [data-testid="stSegmentedControl"] { display: flex; justify-content: center; }
  [data-testid="stSegmentedControl"] button { font-size: 17px !important; padding: 9px 26px !important; font-weight: 600 !important; }
  .the-tra-loi { font-size: 20px; line-height: 1.65; }
  .the-tra-loi b { color: #003366; }
  div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 10px; }
  .lgb-phu [data-testid="stExpander"] summary p { font-size: 13px !important; color: #777 !important; }
</style>
""")

# ==========================================================================
# DỌN TRANG BAO NGOÀI CỦA STREAMLIT CLOUD (Đã nén mã JS)
# ==========================================================================
_html("""<script>!function(){function e(){try{var e=window.top.document;if(e.getElementById("lgb-don-trang-bao"))return!0;var n=e.createElement("style");return n.id="lgb-don-trang-bao",n.textContent='[class*="viewerBadge"],[class*="profileContainer"],[data-testid="manage-app-button"],[class*="manageAppButton"]{display:none !important;}',e.head.appendChild(n),!0}catch(e){return!1}}if(!e()){var n=0,t=setInterval((function(){(e()||++n>20)&&clearInterval(t)}),500)}}();</script>""", height=0)


@st.cache_data(show_spinner=False)
def _logo_b64() -> str:
    p = ROOT / "logo_hoc_vien.png"
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def header() -> None:
    """Header một dòng — nhường toàn bộ màn hình cho nút micro."""
    b64 = _logo_b64()
    img = (f'<img src="data:image/png;base64,{b64}" alt="">' if b64 else "")
    st.html(
        f'<div class="lgb-header">{img}'
        f'<span class="lgb-ten">LUẬT GẦN BẢN</span>'
        f'<span class="lgb-slogan">Chuyển đổi số: không để ai bị bỏ lại phía sau</span></div>'
    )


# ==========================================================================
# GIAO DIỆN HEADER & POPOVER ĐĂNG NHẬP TỐI GIẢN (GÓC TRÊN BÊN PHẢI)
# ==========================================================================
auth.khoi_tao_mac_dinh()  # Khởi tạo tài khoản mặc định lần đầu

# Tỷ lệ cột: Dồn diện tích cho tiêu đề, nút đăng nhập thu gọn bên phải
col_tieu_de, col_dang_nhap = st.columns([7, 1], vertical_alignment="center")

with col_tieu_de:
    header()

with col_dang_nhap:
    u = auth.nguoi_dang_nhap()
    if u:
        # Đã đăng nhập: Hiển thị icon user gọn nhẹ
        with st.popover("👤", use_container_width=True, help=f"Đang đăng nhập: {u.get('ten_dang_nhap')}"):
            st.markdown(f"**{u.get('mo_ta') or u['ten_dang_nhap']}**")
            st.caption(f"{'Quản trị viên' if u['vai_tro'] == 'admin' else 'Cán bộ'}")
            if u.get("phai_doi_mk"):
                st.warning("Cần đổi mật khẩu.", icon="🔑")
            if st.button("Đăng xuất", use_container_width=True, key="btn_dx_popover"):
                del st.session_state["nguoi_dung"]
                st.rerun()
    else:
        # Chưa đăng nhập: Nút chìa khóa tối giản
        with st.popover("🔑", use_container_width=True, help="Đăng nhập dành cho cán bộ"):
            st.markdown("##### 🔐 Đăng nhập cán bộ")
            with st.form("form_dn_popover", clear_on_submit=False):
                ten = st.text_input("Tên đăng nhập", placeholder="Nhập tài khoản...")
                mk = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu...")
                if st.form_submit_button("Đăng nhập", type="primary", use_container_width=True):
                    nd = auth.kiem_tra_dang_nhap(ten, mk)
                    if nd:
                        st.session_state["nguoi_dung"] = nd
                        st.success("Thành công!")
                        st.rerun()
                    else:
                        st.error("Sai tài khoản/mật khẩu.")

st.html("<hr style='margin: 8px 0 15px 0;'>")


# ============================================================ ĐIỀU HƯỚNG
if not hasattr(st, "navigation") or not hasattr(st, "Page"):
    st.error(
        "Phiên bản Streamlit đang cài quá cũ (cần từ **1.36** trở lên).\n\n"
        "Mở terminal ở thư mục dự án và chạy:\n\n"
        "```\npip install -U streamlit\n```"
    )
    st.stop()

# Khai báo danh sách trang trong hệ thống
trang = [
    st.Page("giao_dien/cong_dan.py", title="Hỏi đáp thủ tục",
             icon=":material/record_voice_over:", default=True),
    st.Page("giao_dien/gioi_thieu.py", title="Giới thiệu dự án",
             icon=":material/info:")
]

u = auth.nguoi_dang_nhap()
if u and (auth.la_admin() or auth.quyen_cua(u)):
    trang.append(st.Page("giao_dien/quan_tri.py", title="Quản trị kho",
                         icon=":material/settings:"))
if auth.la_admin():
    trang.append(st.Page("giao_dien/tai_khoan.py", title="Tài khoản & phân quyền",
                         icon=":material/manage_accounts:"))

# Chạy điều hướng ẩn sidebar, quản lý các trang thông qua nút điều hướng trong giao diện
st.navigation(trang, position="hidden").run()
