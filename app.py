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

st.set_page_config(page_title="LUẬT GẦN BẢN - Chuyển đổi số: Không để ai bị bỏ lại phía sau", page_icon="⚖️",
                   layout="centered", initial_sidebar_state="collapsed")

# ==========================================================================
# GIAO DIỆN CHUNG 
# ==========================================================================
# SỬ DỤNG st.html() thay vì st.markdown() để bỏ qua bộ phân tích Markdown, tăng tốc độ render UI
st.html("""
<style>
  /* Chỉ giữ tiêu đề và nút đăng nhập trên cùng hàng. Các nhóm cột khác
     được Streamlit tự xếp lại khi màn hình nhỏ. */
  @media (max-width: 768px) {
      .st-key-lgb-tieu-de div[data-testid="stHorizontalBlock"] { display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; align-items: center !important; width: 100% !important; }
      .st-key-lgb-tieu-de div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] { flex: 1 1 auto !important; min-width: 0 !important; width: auto !important; }
      .st-key-lgb-tieu-de div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:last-child { flex: 0 0 auto !important; width: auto !important; }
  }

  /* NÚT "GIỚI THIỆU DỰ ÁN" & "ĐIỀU KHOẢN SỬ DỤNG": CĂN GIỮA TUYỆT ĐỐI, VIÊN THUỐC SANG TRỌNG */
  .element-container:has([data-testid="stPageLink"]) { display: flex !important; justify-content: center !important; width: 100% !important; margin: 5px 0 !important; }
  [data-testid="stPageLink"] { align-self: center !important; margin: 0 auto !important; display: flex !important; flex-direction: row !important; justify-content: center !important; align-items: center !important; width: max-content !important; min-width: 185px !important; max-width: 90vw !important; background-color: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 40px !important; padding: 8px 22px !important; box-shadow: 0 2px 8px rgba(0,0,0,0.03) !important; transition: all 0.2s ease !important; text-decoration: none !important; }
  [data-testid="stPageLink"]:hover { background-color: #f8fafc !important; border-color: #cbd5e1 !important; box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important; transform: translateY(-1px) !important; }
  [data-testid="stPageLink"] span { white-space: nowrap !important; overflow: visible !important; text-overflow: clip !important; font-family: 'Times New Roman', Times, serif !important; font-size: 15.5px !important; color: #003366 !important; font-weight: 600 !important; letter-spacing: 0.2px !important; }

  /* Phông chữ chung */
  .stApp, p, h1, h2, h3, h4, h5, h6, label, button, input, .stMarkdown, .stText, .stTextArea { font-family: 'Times New Roman', Times, serif !important; }
  /* Biểu tượng Material là chữ ghép (ligature): nếu bị ép sang Times New Roman sẽ hiện ra chữ "settings"... thay vì hình.
     Quy tắc cho nút chuyển trang ở trên nhắm vào mọi thẻ span, nên phải khai báo lại với độ ưu tiên cao hơn.
     LƯU Ý: không viết dấu "nhỏ hơn" liền chữ cái trong khối style này — bộ lọc HTML của Streamlit (DOMPurify)
     sẽ xoá CẢ khối style, làm mất toàn bộ giao diện. */
  [data-testid="stPageLink"] [data-testid="stIconMaterial"] { font-family: 'Material Symbols Rounded','Material Icons',sans-serif !important; font-weight: normal !important; letter-spacing: normal !important; }
  [data-testid="stExpanderToggleIcon"], [data-testid="stIconMaterial"], [data-testid="stFileUploadDropzone"] span, .st-icon, .material-icons, .material-symbols-rounded { font-family: 'Material Symbols Rounded','Material Icons',sans-serif !important; }

  /* Ẩn UI mặc định của Streamlit */
  [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="manage-app-button"], .stAppDeployButton, #MainMenu, footer, [class*="viewerBadge"], [class*="profileContainer"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
  header[data-testid="stHeader"] { background: transparent !important; height: 0 !important; min-height: 0 !important; }
  .block-container { padding-top: 1.2rem !important; padding-bottom: 3rem !important; max-width: 900px !important; }
  iframe[title="streamlit.components.v1.html"] { border: 0 !important; }
  iframe[title="streamlit.components.v1.html"][height="0"] { height: 0 !important; display: block !important; }

  /* Header dự án gọn gàng */
  .lgb-header { display: inline-flex; align-items: center; gap: 6px; margin: 0 !important; padding: 0 !important; line-height: 1.2; }
  .lgb-header img { width: 26px; height: 26px; object-fit: contain; flex-shrink: 0; }
  .lgb-ten { color: #003366; font-size: 15px; font-weight: bold; letter-spacing: .2px; white-space: nowrap; }
  .lgb-slogan { color: #777; font-size: 10.5px; font-style: italic; border-left: 1px solid #ccc; padding-left: 6px; margin-left: 2px; }
  @media (max-width: 640px) {
      /* Giữ logo và tên ở dòng đầu; slogan xuống dòng để không bị ẩn. */
      .lgb-header { display: flex; flex-wrap: wrap; row-gap: 2px; min-width: 0; }
      .lgb-ten { font-size: 14px; }
      .lgb-slogan {
          display: block;
          flex: 0 0 100%;
          border-left: 0;
          padding-left: 32px;
          margin-left: 0;
          font-size: 11px;
          line-height: 1.3;
          white-space: normal;
          overflow-wrap: anywhere;
      }
  }

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

  /* Căn giữa hai liên kết ở trang người dân; không ép các cột khác nằm ngang. */
  .st-key-lgb-lienket-nguoidan { max-width: 500px; margin: 0 auto !important; }
  .st-key-lgb-lienket-nguoidan [data-testid="stPageLink"] { width: 100% !important; }
  .st-key-lgb-lienket-nguoidan [data-testid="stPageLink-NavLink"] { justify-content: center !important; }
  .st-key-lgb-meo-bang { display: none; }

  @media (max-width: 640px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    .block-container h1 { font-size: 2rem !important; line-height: 1.2 !important; overflow-wrap: anywhere; }
    [data-testid="stPageLink"] { min-width: 0 !important; max-width: 100% !important; }
    [data-testid="stPageLink"] span { white-space: normal !important; overflow-wrap: anywhere; }
    .st-key-lgb-nut-can-bo [data-testid="stPageLink"] { width: 100% !important; min-height: 44px; }
    .st-key-lgb-meo-bang { display: block; }

    /* Chỉ số: hai ô mỗi hàng, nhãn được xuống dòng thay vì bị cắt. */
    .st-key-lgb-kho-metrics [data-testid="stHorizontalBlock"],
    .st-key-lgb-phan-hoi-metrics [data-testid="stHorizontalBlock"] {
      display: grid !important; grid-template-columns: repeat(2, minmax(0, 1fr)) !important; gap: 0.75rem !important;
    }
    .st-key-lgb-kho-metrics [data-testid="stColumn"],
    .st-key-lgb-phan-hoi-metrics [data-testid="stColumn"] { width: 100% !important; min-width: 0 !important; }
    .st-key-lgb-kho-metrics [data-testid="stMetricLabel"],
    .st-key-lgb-phan-hoi-metrics [data-testid="stMetricLabel"] { overflow: visible !important; }
    .st-key-lgb-kho-metrics [data-testid="stMetricLabel"] p,
    .st-key-lgb-phan-hoi-metrics [data-testid="stMetricLabel"] p { white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }

    /* Các thẻ quản trị, điều khoản và lựa chọn tiếng được phép xuống dòng. */
    [data-testid="stTabs"] [role="tablist"] { flex-wrap: wrap !important; overflow: visible !important; height: auto !important; }
    [data-testid="stTabs"] [role="tab"] { white-space: normal !important; height: auto !important; min-height: 44px; }
    .st-key-lgb-tieng-gioi-thieu [role="radiogroup"] { display: flex !important; flex-wrap: wrap !important; overflow: visible !important; gap: 0.35rem; }
    .st-key-lgb-tieng-gioi-thieu [role="radio"] { flex: 1 1 7rem; min-height: 44px; padding: 0.5rem 0.7rem !important; white-space: normal !important; }
  }
</style>
""")

# ==========================================================================
# CHẶN GOOGLE TRANSLATE LÀM MẤT CHỮ & DỌN TRANG BAO NGOÀI CỦA STREAMLIT
# ==========================================================================
_html("""
<script>
(function() {
    function cauHinhTrangBao() {
        try {
            var docs = [window.parent.document];
            if (window.top && window.top.document !== window.parent.document) {
                docs.push(window.top.document);
            }
            docs.forEach(function(doc) {
                if (!doc) return;
                // 1. Khóa ngôn ngữ tiếng Việt & gắn cờ notranslate chống Google Translate
                doc.documentElement.setAttribute('lang', 'vi');
                doc.documentElement.setAttribute('translate', 'no');
                doc.documentElement.classList.add('notranslate');
                if (doc.body) {
                    doc.body.setAttribute('translate', 'no');
                    doc.body.classList.add('notranslate');
                }
                if (!doc.querySelector('meta[name="google"]')) {
                    var meta = doc.createElement('meta');
                    meta.name = 'google';
                    meta.content = 'notranslate';
                    doc.head.appendChild(meta);
                }
                // 2. Ẩn badge thừa của Streamlit
                if (!doc.getElementById('lgb-don-trang-bao')) {
                    var st = doc.createElement('style');
                    st.id = 'lgb-don-trang-bao';
                    st.textContent = '[class*="viewerBadge"],[class*="profileContainer"],[data-testid="manage-app-button"],[class*="manageAppButton"]{display:none !important;}';
                    doc.head.appendChild(st);
                }
            });
            return true;
        } catch (e) {
            return false;
        }
    }
    if (!cauHinhTrangBao()) {
        var lanThu = 0;
        var boDem = setInterval(function() {
            if (cauHinhTrangBao() || ++lanThu > 20) clearInterval(boDem);
        }, 300);
    }
})();
</script>
""", height=0)


@st.cache_data(show_spinner=False)
def _logo_b64() -> str:
    p = ROOT / "logo_hoc_vien.png"
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


def header() -> None:
    """Header một dòng — nhường toàn bộ màn hình cho nút micro."""
    b64 = _logo_b64()
    img = (f'<img src="data:image/png;base64,{b64}" alt="" width="26" height="26" '
           f'style="width:26px;height:26px;object-fit:contain;">' if b64 else "")
    st.html(
        f'<div class="lgb-header notranslate" translate="no">{img}'
        f'<span class="lgb-ten">LUẬT GẦN BẢN</span>'
        f'<span class="lgb-slogan">Chuyển đổi số: không để ai bị bỏ lại phía sau</span></div>'
    )


# ==========================================================================
# DANH SÁCH TRANG (tạo một lần, dùng chung cho điều hướng và nút chuyển trang)
# ==========================================================================
if not hasattr(st, "navigation") or not hasattr(st, "Page"):
    st.error(
        "Phiên bản Streamlit đang cài quá cũ (cần từ **1.36** trở lên).\n\n"
        "Mở terminal ở thư mục dự án và chạy:\n\n"
        "```\npip install -U streamlit\n```"
    )
    st.stop()

TRANG_HOI_DAP = st.Page("giao_dien/cong_dan.py", title="Hỏi đáp thủ tục",
                        icon="🏠", default=True)
TRANG_GIOI_THIEU = st.Page("giao_dien/gioi_thieu.py", title="Giới thiệu dự án",
                           icon="📖")
TRANG_DIEU_KHOAN = st.Page("giao_dien/dieu_khoan.py", title="Điều khoản sử dụng",
                           icon="📜")
TRANG_QUAN_TRI = st.Page("giao_dien/quan_tri.py", title="Quản trị kho",
                         icon="⚙️")
TRANG_TAI_KHOAN = st.Page("giao_dien/tai_khoan.py", title="Phân quyền",
                          icon="👥")


def duoc_vao_quan_tri() -> bool:
    u = auth.nguoi_dang_nhap()
    return bool(u) and (auth.la_admin() or bool(auth.quyen_cua(u)))


def nut_chuyen_trang_can_bo() -> None:
    """Các nút đi tới trang dành cho cán bộ. Thanh bên đã bị ẩn nên đây là
    đường duy nhất để vào trang quản trị sau khi đăng nhập."""
    st.page_link(TRANG_HOI_DAP, label="Trang hỏi đáp")
    st.page_link(TRANG_DIEU_KHOAN, label="Điều khoản & Quy chế")
    if duoc_vao_quan_tri():
        st.page_link(TRANG_QUAN_TRI, label="Quản trị kho")
    if auth.la_admin():
        st.page_link(TRANG_TAI_KHOAN, label="Phân quyền")


# ==========================================================================
# GIAO DIỆN HEADER & POPOVER ĐĂNG NHẬP TỐI GIẢN (GÓC TRÊN BÊN PHẢI)
# ==========================================================================
auth.khoi_tao_mac_dinh()  # Khởi tạo tài khoản mặc định lần đầu

# Tỷ lệ cột: Dồn diện tích cho tiêu đề, nút đăng nhập thu gọn bên phải
khung_tieu_de = st.container(key="lgb-tieu-de")
col_tieu_de, col_dang_nhap = khung_tieu_de.columns([7, 1], vertical_alignment="center")

with col_tieu_de:
    header()

with col_dang_nhap:
    u = auth.nguoi_dang_nhap()
    if u:
        # Đã đăng nhập: Hiển thị icon user gọn nhẹ
        with st.popover("👤", use_container_width=True, help=f"Đang đăng nhập: {u.get('ten_dang_nhap')}"):
            st.markdown(f"**{u.get('mo_ta') or u['ten_dang_nhap']}**")
            st.caption(f"{'Quản trị viên' if u['vai_tro'] == 'admin' else 'Cán bộ / CTV ngôn ngữ'}")
            if u.get("phai_doi_mk"):
                st.warning("Cần đổi mật khẩu.", icon="🔑")
            nut_chuyen_trang_can_bo()
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

# Cán bộ đã đăng nhập: hiện hàng nút chuyển trang ngay dưới header
if auth.nguoi_dang_nhap():
    st.html("""<style>
      .st-key-lgb-nut-can-bo [data-testid="stPageLink"] { min-width: 0 !important; padding: 5px 14px !important; }
      .st-key-lgb-nut-can-bo [data-testid="stPageLink"] span { font-size: 14px !important; }
    </style>""")
    try:
        khung_nut = st.container(key="lgb-nut-can-bo")
    except TypeError:                      # Streamlit cũ chưa có tham số key
        khung_nut = st.container()
    cot_nut = khung_nut.columns(4)
    with cot_nut[0]:
        st.page_link(TRANG_HOI_DAP, label="Trang hỏi đáp")
    with cot_nut[1]:
        st.page_link(TRANG_DIEU_KHOAN, label="Điều khoản & Quy chế")
    if duoc_vao_quan_tri():
        with cot_nut[2]:
            st.page_link(TRANG_QUAN_TRI, label="Quản trị kho")
    if auth.la_admin():
        with cot_nut[3]:
            st.page_link(TRANG_TAI_KHOAN, label="Phân quyền")

st.html("<hr style='margin: 8px 0 15px 0;'>")


# ==========ĐIỀU HƯỚNG============================
trang = [TRANG_HOI_DAP, TRANG_GIOI_THIEU, TRANG_DIEU_KHOAN]
if duoc_vao_quan_tri():
    trang.append(TRANG_QUAN_TRI)
if auth.la_admin():
    trang.append(TRANG_TAI_KHOAN)

# Chạy điều hướng ẩn sidebar, quản lý các trang thông qua nút điều hướng trong giao diện
st.navigation(trang, position="hidden").run()
