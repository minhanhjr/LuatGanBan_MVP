# -*- coding: utf-8 -*-
"""Trang Điều khoản sử dụng & Quy chế vận hành Luật Gần Bản.

Hỗ trợ cơ chế tải về – sửa thủ công – upload ghi đè tệp (.docx / .pdf)
ngay trên giao diện web (chỉ mở khung upload khi cán bộ/admin đăng nhập).
"""
from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path

import streamlit as st

from core import auth

try:
    from core.config import DATA as _DATA_DIR
except ImportError:
    _DATA_DIR = Path(__file__).resolve().parent.parent / "data"

THU_MUC_TAI_LIEU: Path = _DATA_DIR / "tai_lieu"

DANH_MUC_VAN_BAN: dict[str, dict[str, str]] = {
    "dieu_khoan": {
        "tieu_de": "📜 Điều khoản sử dụng công cụ Luật Gần Bản",
        "ten_file": "dieu_khoan_su_dung",
        "mac_dinh": """
Chào mừng bà con đến với **Luật Gần Bản**!

Luật Gần Bản là công cụ hỗ trợ tra cứu và tìm hiểu các thủ tục hành chính bằng giọng nói. Công cụ giúp người dân tiếp cận thông tin dễ hiểu hơn, giảm khó khăn khi tìm hiểu giấy tờ, trình tự và cách thực hiện thủ tục.

### 1. Giới thiệu chung
Công cụ hoạt động theo nguyên tắc **AI hỗ trợ, con người kiểm duyệt và người dùng chủ động xác nhận thông tin**. Luật Gần Bản không phải cơ quan nhà nước, tổ chức hành nghề luật sư hoặc tổ chức thực hiện trợ giúp pháp lý, và không thay thế cán bộ có thẩm quyền.

### 2. Phạm vi và chức năng dịch vụ
Hỗ trợ tiếp nhận câu hỏi bằng giọng nói hoặc văn bản, phân loại nhu cầu, tra cứu thông tin, giải thích quy định bằng ngôn ngữ đơn giản, phát âm thanh tiếng Việt và tiếng dân tộc (Mông, Tày), và kết nối hỗ trợ trực tiếp với cán bộ.

### 3. Điều kiện truy cập và sử dụng
Người dùng cần bảo đảm có khả năng nhận thức và thực hiện các thao tác cơ bản. Trường hợp người chưa đủ tuổi hoặc khó khăn trong nhận thức cần có sự hỗ trợ của cha mẹ hoặc người giám hộ.

### 4. Quy định về việc sử dụng trí tuệ nhân tạo (AI)
- **Vai trò của AI:** Câu trả lời do AI tạo ra là nội dung hỗ trợ tham khảo, không tự động trở thành văn bản tư vấn pháp lý chính thức hay quyết định hành chính.
- **Nguyên tắc "Máy soạn, người duyệt":** Công chức tư pháp – hộ tịch kiểm duyệt, đối chiếu nội dung AI soạn với tài liệu gốc trước khi gắn nhãn xác nhận.
- **Giới hạn độ chính xác:** Khi tài liệu gốc chưa rõ ràng, bà con nên bấm nút kết nối trực tiếp để hỏi cán bộ tư pháp – hộ tịch tại xã.

### 5. Quyền và trách nhiệm của người dùng
Người dùng được quyền biết rõ nội dung đang xem là do AI soạn hay đã được cán bộ kiểm duyệt, được xem căn cứ pháp lý gốc và yêu cầu hỗ trợ trực tiếp. Người dùng không cung cấp thông tin giả mạo hoặc sử dụng kết quả AI để giả mạo văn bản cơ quan nhà nước.

### 6. Bảo vệ dữ liệu và quyền riêng tư
Luật Gần Bản **không thu thập thông tin định danh cá nhân** và **không lưu trữ bản ghi âm** sau khi hoàn tất nhận dạng giọng nói. Bà con không nên nhập số căn cước, mật khẩu hoặc thông tin tài chính nhạy cảm.

### 7. Sử dụng công cụ AI bên thứ ba
Khi chuyển sang ChatGPT, Gemini hoặc công cụ AI bên ngoài, hệ thống sẽ hiển thị cảnh báo; nội dung từ công cụ bên ngoài chưa được Luật Gần Bản kiểm duyệt.

### 8. Xác nhận của người dùng
Khi lựa chọn nút **"Tôi đồng ý"** hoặc tiếp tục sử dụng Luật Gần Bản, bà con xác nhận đã đọc, hiểu và đồng ý tuân thủ các quy định sử dụng công cụ.
""".strip(),
    },
    "bo_nhan": {
        "tieu_de": "🏷️ Bộ nhãn Máy soạn – Người duyệt",
        "ten_file": "bo_nhan_kiem_duyet",
        "mac_dinh": """
### Quy chuẩn phân loại nhãn nội dung trên Luật Gần Bản

- **✅ Nhãn xanh (Cán bộ đã duyệt):** Nội dung hướng dẫn thủ tục đã được công chức tư pháp – hộ tịch đối chiếu trực tiếp với văn bản quy phạm pháp luật gốc và xác nhận phê duyệt.
- **🤖 Nhãn vàng (Máy soạn – Tham khảo):** Bản diễn giải do trí tuệ nhân tạo (AI) tổng hợp tự động từ tài liệu gốc, đang chờ cán bộ kiểm duyệt thủ công.
- **⚠️ Nhãn cảnh báo (Công cụ AI bên ngoài):** Nội dung sinh ra từ nền tảng bên thứ ba (ChatGPT, Gemini), chưa qua quy trình kiểm duyệt của Luật Gần Bản.
""".strip(),
    },
    "canh_bao_ai": {
        "tieu_de": "⚠️ Cảnh báo chuyển hướng sang công cụ AI khác (IS-20)",
        "ten_file": "canh_bao_chuyen_ai",
        "mac_dinh": """
**1. Bảo mật dữ liệu cá nhân:** Không chia sẻ họ tên, số căn cước, số điện thoại, địa chỉ, hình ảnh giấy tờ, hồ sơ vụ việc lên công cụ AI bên ngoài. Nếu cần trao đổi, hãy thay thế bằng *"Người A"*, *"Xã B"*.

**2. Độ chính xác của thông tin:** Nội dung do công cụ AI bên ngoài tạo ra **chưa được Luật Gần Bản kiểm duyệt**, có thể sai lệch hoặc thiếu sót so với quy định hiện hành.

**3. Quyền riêng tư và bảo mật:** Công cụ AI bên ngoài hoạt động theo chính sách riêng của nhà cung cấp; Luật Gần Bản không kiểm soát việc lưu trữ dữ liệu trên nền tảng đó.

**4. Trách nhiệm và phạm vi hỗ trợ:** Nội dung từ công cụ bên ngoài không mang nhãn xác nhận của Luật Gần Bản. Hãy tham khảo ý kiến cán bộ tư pháp – hộ tịch tại địa phương trước khi thực hiện.
""".strip(),
    },
}

_RE_MUC_LON = re.compile(r"^\d+\.\s+\S+")
_RE_MUC_CON = re.compile(r"^\d+\.\d+\.\s+\S+")


def _chuyen_trang_an_toan(duong_dan_trang: str) -> None:
    """Chuyển trang tương thích mọi cấu hình Streamlit (st.navigation hoặc pages/)."""
    try:
        st.switch_page(duong_dan_trang)
    except Exception:
        st.session_state["trang_hien_tai"] = duong_dan_trang
        st.rerun()


def tim_file_van_ban(ma_muc: str) -> Path | None:
    """Tìm tệp .docx hoặc .pdf hiện có của mục tương ứng trong data/tai_lieu/."""
    if ma_muc not in DANH_MUC_VAN_BAN:
        return None
    THU_MUC_TAI_LIEU.mkdir(parents=True, exist_ok=True)
    goc = DANH_MUC_VAN_BAN[ma_muc]["ten_file"]
    for ext in (".docx", ".pdf"):
        p = THU_MUC_TAI_LIEU / f"{goc}{ext}"
        if p.is_file():
            return p
    return None


def luu_file_thu_cong(ma_muc: str, uploaded_file) -> Path:
    """Ghi đè bản mới lên data/tai_lieu/ một cách nguyên tử (atomic replace)."""
    if ma_muc not in DANH_MUC_VAN_BAN:
        raise ValueError(f"Mã mục không hợp lệ: {ma_muc}")
    THU_MUC_TAI_LIEU.mkdir(parents=True, exist_ok=True)
    goc = DANH_MUC_VAN_BAN[ma_muc]["ten_file"]
    ext_moi = Path(uploaded_file.name).suffix.lower()
    if ext_moi not in (".docx", ".pdf"):
        raise ValueError("Chỉ chấp nhận tệp định dạng .docx hoặc .pdf")

    dich = THU_MUC_TAI_LIEU / f"{goc}{ext_moi}"
    tam = THU_MUC_TAI_LIEU / f".{goc}.tmp{ext_moi}"
    tam.write_bytes(uploaded_file.getvalue())
    tam.replace(dich)

    for ext in (".docx", ".pdf"):
        if ext != ext_moi:
            cu = THU_MUC_TAI_LIEU / f"{goc}{ext}"
            if cu.is_file():
                cu.unlink(missing_ok=True)
    return dich


@st.cache_data(show_spinner=False, ttl=3600)
def _trich_xuat_docx_cached(duong_dan_str: str, mtime_ns: int) -> str:
    """Đọc nội dung .docx có cache theo (đường dẫn, mtime) để phản hồi tức thì."""
    import docx

    doc = docx.Document(duong_dan_str)
    doan: list[str] = []
    for p in doc.paragraphs:
        raw = (p.text or "").strip()
        if not raw:
            continue
        safe_text = html.escape(raw)
        style_name = (p.style.name or "").lower() if p.style else ""
        if "heading" in style_name or (_RE_MUC_LON.match(raw) and len(raw) <= 120):
            doan.append(f"### {safe_text}")
        elif _RE_MUC_CON.match(raw) and len(raw) <= 130:
            doan.append(f"#### {safe_text}")
        else:
            doan.append(safe_text)
    return "\n\n".join(doan)


def doc_noi_dung_van_ban(ma_muc: str) -> str:
    """Trả về nội dung Markdown sạch để hiển thị lên giao diện."""
    if ma_muc not in DANH_MUC_VAN_BAN:
        return ""
    fp = tim_file_van_ban(ma_muc)
    if fp is None:
        return DANH_MUC_VAN_BAN[ma_muc]["mac_dinh"]
    if fp.suffix.lower() == ".pdf":
        return (
            "📎 Văn bản hiện đang lưu dưới định dạng **PDF**. "
            "Bà con vui lòng bấm nút **⬇️ Tải bản gốc (.pdf)** ở phía trên để xem đầy đủ."
        )
    try:
        noi_dung = _trich_xuat_docx_cached(str(fp), fp.stat().st_mtime_ns)
        return noi_dung if noi_dung else DANH_MUC_VAN_BAN[ma_muc]["mac_dinh"]
    except ImportError:
        return (
            "⚠️ Máy chủ chưa cài thư viện đọc trực tiếp file Word (`python-docx`). "
            "Bà con vui lòng bấm nút **⬇️ Tải bản gốc (.docx)** ở phía trên để xem."
        )
    except Exception as exc:
        return f"⚠️ Không đọc được bản xem trước ({html.escape(str(exc))}). Vui lòng tải tệp về máy để xem."


def render_trang_dieu_khoan() -> None:
    """Hàm render chính của trang Điều khoản sử dụng & Quy chế vận hành."""
    st.markdown(
        """
        <style>
        .lgb-dk-title {
            text-align: center;
            color: #0B4F9E;
            font-family: 'Times New Roman', Times, serif;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .lgb-dk-sub {
            text-align: center;
            color: #4A5568;
            font-family: 'Times New Roman', Times, serif;
            font-style: italic;
            margin-bottom: 18px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col_back, _ = st.columns([1.8, 5.2])
    with col_back:
        if st.button("⬅️ Quay lại tra cứu", key="dk_btn_quay_lai", use_container_width=True):
            _chuyen_trang_an_toan("giao_dien/cong_dan.py")

    st.markdown(
        '<h1 class="lgb-dk-title">📜 ĐIỀU KHOẢN SỬ DỤNG & QUY CHẾ VẬN HÀNH</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="lgb-dk-sub">Luật Gần Bản · Nguyên tắc Máy soạn – Người duyệt · Bảo vệ quyền riêng tư người dân</p>',
        unsafe_allow_html=True,
    )

    muc_chon = st.selectbox(
        "📑 Chọn văn bản cần xem hoặc tải về:",
        options=list(DANH_MUC_VAN_BAN.keys()),
        format_func=lambda k: DANH_MUC_VAN_BAN[k]["tieu_de"],
        key="dk_select_van_ban",
    )

    fp_hien_tai = tim_file_van_ban(muc_chon)
    c_info, c_dl = st.columns([4.2, 2.0])
    with c_info:
        if fp_hien_tai:
            tg = datetime.fromtimestamp(fp_hien_tai.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
            st.caption(f"📅 Cập nhật lần cuối: **{tg}** · Tệp gốc: `{fp_hien_tai.name}`")
        else:
            st.caption("ℹ️ Đang hiển thị bản chuẩn mặc định (cán bộ có thể tải tệp `.docx` / `.pdf` lên máy chủ).")

    with c_dl:
        if fp_hien_tai:
            ext = fp_hien_tai.suffix.lower()
            mime = (
                "application/pdf"
                if ext == ".pdf"
                else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            st.download_button(
                f"⬇️ Tải bản gốc ({ext})",
                data=fp_hien_tai.read_bytes(),
                file_name=fp_hien_tai.name,
                mime=mime,
                key=f"dk_dl_{muc_chon}",
                use_container_width=True,
            )

    # Khung upload ghi đè thủ công (chỉ hiển thị khi cán bộ / admin đã đăng nhập)
    la_can_bo = False
    try:
        la_can_bo = bool(auth.nguoi_dang_nhap())
    except Exception:
        la_can_bo = False

    if la_can_bo:
        with st.container(border=True):
            st.markdown(f"**🛠️ Cán bộ cập nhật thủ công: {DANH_MUC_VAN_BAN[muc_chon]['tieu_de']}**")
            st.caption("Tải bản hiện tại về sửa trên máy tính, sau đó chọn tệp mới tại đây để ghi đè:")
            f_moi = st.file_uploader(
                "Chọn tệp Word (.docx) hoặc PDF (.pdf) mới",
                type=["docx", "pdf"],
                key=f"dk_up_{muc_chon}",
            )
            if f_moi is not None:
                if st.button("💾 Ghi đè bản mới lên hệ thống", type="primary", key=f"dk_save_{muc_chon}"):
                    try:
                        luu_file_thu_cong(muc_chon, f_moi)
                        _trich_xuat_docx_cached.clear()
                        st.success("✅ Đã cập nhật tệp mới thành công!")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"❌ Lỗi khi lưu tệp: {exc}")

    with st.container(border=True):
        st.markdown(doc_noi_dung_van_ban(muc_chon))

    st.markdown("<br>", unsafe_allow_html=True)
    _, col_ok, _ = st.columns([2, 2.6, 2])
    with col_ok:
        if st.button("✅ Tôi đã đọc và đồng ý", type="primary", key="dk_btn_dong_y", use_container_width=True):
            _chuyen_trang_an_toan("giao_dien/cong_dan.py")


# Thực thi trực tiếp khi chạy như một trang độc lập của Streamlit
render_trang_dieu_khoan()
