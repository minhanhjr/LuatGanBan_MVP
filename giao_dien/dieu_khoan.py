# -*- coding: utf-8 -*-
import streamlit as st
import base64
import html
from pathlib import Path
from core import auth
from giao_dien.van_ban_ui import hien_thi_van_ban

ROOT = Path(__file__).resolve().parent.parent

# ==============================================================================
# TỐI ƯU HÓA KHOẢNG TRẮNG & RESPONSIVE (ĐỒNG BỘ VỚI TRANG GIỚI THIỆU)
# ==============================================================================
st.markdown("""
<style>
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 900px !important;
    }

    @media screen and (max-width: 640px) {
        .block-container {
            padding-top: 0.3rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
    }

    [data-testid="stPageLink"] {
        background-color: #fcfcfc !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        padding: 6px 14px !important;
        transition: all 0.25s ease-in-out !important;
        width: fit-content !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
    }
    [data-testid="stPageLink"]:hover {
        background-color: #f1f5f9 !important;
        border-color: #cbd5e1 !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important;
        transform: translateY(-1px);
    }
    [data-testid="stPageLink"] span {
        font-family: 'Times New Roman', Times, serif !important;
        font-size: 15px !important;
        color: #003366 !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

st.page_link("giao_dien/cong_dan.py", label="Quay lại trang Hỏi đáp chính", icon="⬅️")
st.markdown("<hr style='margin: 8px 0 15px 0;'>", unsafe_allow_html=True)

# ==============================================================================
# CƠ CHẾ LƯU TRỮ FILE CỨNG (.md, .txt, .docx)
# ==============================================================================
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "dieu_khoan.md"


def load_terms_content() -> str:
    """Đọc nội dung điều khoản từ file cứng đã lưu."""
    try:
        if DATA_FILE.exists():
            content = DATA_FILE.read_text(encoding="utf-8")
            if content.strip():
                return content
    except Exception as e:
        st.error(f"Lỗi đọc file: {e}")
    return ""


def save_terms_content(content: str) -> bool:
    """Lưu vĩnh viễn nội dung điều khoản vào file cứng."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        st.error(f"Lỗi khi lưu tệp hệ thống: {e}")
        return False


def docx_to_exact_html(docx_file) -> str:
    """Chuyển đổi file Word (.docx) thành HTML giữ nguyên định dạng gốc."""
    try:
        import docx
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = docx.Document(docx_file)
        html_parts = []

        for p in doc.paragraphs:
            align_style = "text-align: left;"
            if p.alignment == WD_ALIGN_PARAGRAPH.CENTER:
                align_style = "text-align: center;"
            elif p.alignment == WD_ALIGN_PARAGRAPH.RIGHT:
                align_style = "text-align: right;"
            elif p.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY:
                align_style = "text-align: justify;"

            p_content = []
            for run in p.runs:
                text = run.text
                if not text:
                    try:
                        drawings = run._r.xpath('.//a:blip')
                        for blip in drawings:
                            embed = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                            if embed and embed in doc.part.related_parts:
                                image_part = doc.part.related_parts[embed]
                                image_bytes = image_part.blob
                                b64_img = base64.b64encode(image_bytes).decode('utf-8')
                                p_content.append(
                                    f'<div style="text-align: center;"><img src="data:image/png;base64,{b64_img}" '
                                    f'style="max-width: 100%; height: auto; margin: 20px auto; border-radius: 6px; '
                                    f'box-shadow: 0 4px 12px rgba(0,0,0,0.15);" /></div>'
                                )
                    except Exception:
                        pass
                    continue

                safe_text = html.escape(text)
                style_runs = []
                if run.bold:
                    safe_text = f"<b>{safe_text}</b>"
                if run.italic:
                    safe_text = f"<i>{safe_text}</i>"
                if run.font.color and run.font.color.rgb:
                    rgb = run.font.color.rgb
                    hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
                    style_runs.append(f"color: {hex_color};")

                if style_runs:
                    style_str = " ".join(style_runs)
                    safe_text = f'<span style="{style_str}">{safe_text}</span>'

                p_content.append(safe_text)

            full_p_text = "".join(p_content)
            if full_p_text.strip() or '<img' in full_p_text:
                tag = "p"
                style_name = p.style.name.lower()
                if "heading 1" in style_name or "title" in style_name:
                    tag = "h2"
                elif "heading 2" in style_name:
                    tag = "h3"

                html_parts.append(f'<{tag} style="{align_style} margin-bottom: 10px;">{full_p_text}</{tag}>')

        for table in doc.tables:
            table_html = ['<div style="overflow-x: auto; margin: 15px 0;"><table style="border-collapse: collapse; width: 100%;">']
            for row in table.rows:
                table_html.append('<tr>')
                for cell in row.cells:
                    table_html.append(f'<td style="border: 1px solid #cccccc; padding: 8px 12px; text-align: left;">{html.escape(cell.text)}</td>')
                table_html.append('</tr>')
            table_html.append('</table></div>')
            html_parts.append("".join(table_html))

        return "\n".join(html_parts)
    except Exception as e:
        st.error(f"Không thể đọc file Word: {e}")
        return ""


if "terms_content" not in st.session_state:
    st.session_state["terms_content"] = load_terms_content()

# ==============================================================================
# PHÂN QUYỀN CÁN BỘ & ADMIN: TẢI FILE LÊN HOẶC SỬA THỦ CÔNG
# ==============================================================================
u = auth.nguoi_dang_nhap()
co_quyen_quan_tri = bool(u and u.get("vai_tro") in ("admin", "can_bo"))

if co_quyen_quan_tri:
    vai_tro_hien_thi = "Quản trị viên (Admin)" if u.get("vai_tro") == "admin" else "Cán bộ chuyên môn"
    with st.expander(
        "⚙️ QUẢN LÝ ĐIỀU KHOẢN SỬ DỤNG (Tải file lên / Sửa thủ công)",
        expanded=not bool(st.session_state["terms_content"]),
    ):
        st.info(f"Đang đăng nhập với quyền **{vai_tro_hien_thi}**. Mọi cập nhật sẽ được lưu vĩnh viễn và hiển thị ngay cho công dân.")

        tab_file, tab_soan = st.tabs(["📁 Tải file lên (.md, .txt, .docx)", "✍️ Sửa thủ công"])

        with tab_file:
            st.caption("Tải lên file Markdown, Text hoặc Word (.docx). Hệ thống tự động bóc tách giữ nguyên định dạng gốc.")
            uploaded_file = st.file_uploader(
                "Chọn file điều khoản tải lên",
                type=["md", "txt", "docx"],
                key="upload_terms_file",
            )

            if uploaded_file is not None:
                file_content = ""
                if uploaded_file.name.endswith(".docx"):
                    file_content = docx_to_exact_html(uploaded_file)
                else:
                    try:
                        file_content = uploaded_file.read().decode("utf-8")
                    except Exception:
                        try:
                            file_content = uploaded_file.read().decode("latin-1")
                        except Exception as e:
                            st.error(f"Lỗi giải mã file: {e}")

                if file_content:
                    st.caption("Xem trước bố cục tài liệu:")
                    preview_html = f"""
                    <div style="background: #ffffff; color: #000000; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); font-family: 'Times New Roman', Times, serif; line-height: 1.7; max-height: 350px; overflow-y: auto; margin-bottom: 15px; box-sizing: border-box;">
                        {file_content}
                    </div>
                    """
                    st.markdown(preview_html, unsafe_allow_html=True)

                    if st.button("🚀 Xác nhận cập nhật Điều khoản từ file", type="primary", use_container_width=True):
                        if save_terms_content(file_content):
                            st.session_state["terms_content"] = file_content
                            st.success("Đã cập nhật Điều khoản sử dụng từ file thành công!")
                            st.rerun()

        with tab_soan:
            st.caption("Chỉnh sửa trực tiếp nội dung Điều khoản sử dụng (hỗ trợ HTML hoặc Markdown).")
            updated_content = st.text_area(
                "Nội dung Điều khoản sử dụng:",
                value=st.session_state["terms_content"],
                height=320,
                key="manual_edit_terms",
            )
            if st.button("💾 Lưu nội dung sửa thủ công", type="primary", use_container_width=True):
                if save_terms_content(updated_content):
                    st.session_state["terms_content"] = updated_content
                    st.success("Đã lưu thay đổi thủ công thành công!")
                    st.rerun()

    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

# ==============================================================================
# HIỂN THỊ NỘI DUNG ĐIỀU KHOẢN (CÔNG DÂN CHỈ XEM, KHÔNG CÓ QUYỀN CHỈNH SỬA)
# ==============================================================================
display_content = st.session_state["terms_content"]

if not display_content.strip():
    st.info("📄 Chưa có nội dung Điều khoản sử dụng. Cán bộ hoặc Quản trị viên vui lòng đăng nhập để tải file lên hoặc nhập nội dung.")
else:
    hien_thi_van_ban(display_content, key="lgb-van-ban-dieu-khoan")
