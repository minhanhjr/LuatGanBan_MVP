# -*- coding: utf-8 -*-
import streamlit as st
import os
import base64
import html
from pathlib import Path
from core import auth

ROOT = Path(__file__).resolve().parent.parent

# ==============================================================================
# TỐI ƯU HÓA KHOẢNG TRẮNG & RESPONSIVE CHO TRANG GIỚI THIỆU
# ==============================================================================
st.markdown("""
<style>
    /* Thu hẹp lề trên để nội dung nối tiếp mượt mà ngay bên dưới header chung của app.py */
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 900px !important;
    }
    
    /* Tối ưu riêng cho màn hình điện thoại di động */
    @media screen and (max-width: 640px) {
        .block-container {
            padding-top: 0.3rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
    }

    /* Thiết kế lại nút st.page_link thành dạng minimalist sang trọng, gọn gàng */
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

# Nút quay lại trang Hỏi đáp chính được tinh chỉnh gọn gàng, cao cấp
st.page_link("giao_dien/cong_dan.py", label="Quay lại trang Hỏi đáp chính", icon="⬅️")
st.markdown("<hr style='margin: 8px 0 15px 0;'>", unsafe_allow_html=True)

# ==============================================================================
# CƠ CHẾ LƯU TRỮ FILE CỨNG & QUẢN TRỊ NỘI DUNG GIỚI THIỆU
# ==============================================================================
# Xác định đường dẫn tuyệt đối đến file lưu trữ
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "gioi_thieu.md"

def load_intro_content():
    """Đọc nội dung từ file cứng, nếu chưa có thì trả về nội dung mặc định."""
    try:
        if DATA_FILE.exists():
            content = DATA_FILE.read_text(encoding="utf-8")
            if content.strip():
                return content
    except Exception as e:
        st.error(f"Lỗi đọc file: {e}")
        pass
    
    # Nội dung mặc định nếu chưa có file
    return """<h2 style="text-align: center; color: #003366;">GIỚI THIỆU DỰ ÁN</h2>
<h2 style="text-align: center; color: #003366;">LUẬT GẦN BẢN</h2>
<p style="text-align: center;"><b>Trợ lý thủ tục hành chính bằng giọng nói tiếng mẹ đẻ cho đồng bào dân tộc thiểu số</b></p>
<p style="text-align: center;"><i>“Chuyển đổi số: Không để ai bị bỏ lại phía sau”</i></p>
<hr>
<h3>I. Bối cảnh và bài toán xã hội</h3>
<p>Trong tiến trình chuyển đổi số quốc gia, hạ tầng công nghệ và điện lưới đã cơ bản phủ sóng đến các bản làng vùng cao. Tuy nhiên, rào cản về ngôn ngữ và chữ viết vẫn là thách thức lớn đối với đồng bào khi thực hiện các thủ tục hành chính thiết yếu.</p>
"""

def save_intro_content(content):
    """Lưu vĩnh viễn nội dung vào file cứng."""
    try:
        # Đảm bảo thư mục 'data' tồn tại trước khi lưu file
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Ghi đè nội dung mới vào file
        DATA_FILE.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        st.error(f"Lỗi khi lưu tệp hệ thống: {e}")
        return False

def docx_to_exact_html(docx_file) -> str:
    """Chuyển đổi file Docx thành mã HTML."""
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
                                p_content.append(f'<div style="text-align: center;"><img src="data:image/png;base64,{b64_img}" style="max-width: 100%; height: auto; margin: 20px auto; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);" /></div>')
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

# Tải nội dung vào Session State (Chỉ load 1 lần khi mở app)
if "intro_content" not in st.session_state:
    st.session_state["intro_content"] = load_intro_content()

# Phân quyền Admin chỉnh sửa nội dung
u = auth.nguoi_dang_nhap()
if u and u.get("vai_tro") == "admin":
    with st.expander("⚙️ BẢNG ĐIỀU KHIỂN ADMIN - CHỈNH SỬA NỘI DUNG", expanded=False):
        st.warning("Bạn đang đăng nhập bằng tài khoản Quản trị viên. Mọi thay đổi sẽ được lưu vĩnh viễn vào hệ thống.")
        
        tab_soan, tab_file = st.tabs(["✍️ Soạn thảo trực tiếp", "📁 Tải file lên (.md, .txt, .docx)"])
        
        with tab_soan:
            updated_content = st.text_area(
                "Soạn thảo nội dung giới thiệu (hỗ trợ HTML/Markdown):", 
                value=st.session_state["intro_content"], 
                height=300
            )
            if st.button("💾 Lưu nội dung soạn thảo", type="primary"):
                if save_intro_content(updated_content):
                    st.session_state["intro_content"] = updated_content
                    st.success("Đã lưu và cập nhật hệ thống thành công!")
                    st.rerun()
                
        with tab_file:
            st.caption("Tải lên file Markdown, Text hoặc Word (.docx). Hệ thống tự động bóc tách giữ nguyên định dạng gốc.")
            uploaded_file = st.file_uploader("Chọn file tài liệu tải lên", type=["md", "txt", "docx"])
            
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
                    
                    if st.button("🚀 Xác nhận cập nhật từ file", type="primary", use_container_width=True):
                        if save_intro_content(file_content):
                            st.session_state["intro_content"] = file_content
                            st.success("Đã cập nhật nội dung chuẩn định dạng từ file thành công!")
                            st.rerun()
                
    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

# ==============================================================================
# HIỂN THỊ NỘI DUNG CHÍNH (Responsive mượt mà trên cả PC và Mobile)
# ==============================================================================
document_html = f"""
<div style="
    background: #ffffff;
    color: #111111;
    padding: clamp(15px, 3.5vw, 45px);
    margin: 5px auto;
    max-width: 900px;
    width: 100%;
    border-radius: 6px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    font-family: 'Times New Roman', Times, serif;
    line-height: 1.7;
    font-size: clamp(15px, 1.8vw, 17px);
    box-sizing: border-box;
">
    <style>
        img {{
            max-width: 100% !important;
            height: auto !important;
            display: block !important;
            margin: 20px auto !important;
            border-radius: 6px !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important;
        }}
        h2, h3, h4 {{
            color: #003366 !important;
            font-family: 'Times New Roman', Times, serif !important;
            font-weight: bold !important;
            margin-top: 20px !important;
            margin-bottom: 10px !important;
            word-wrap: break-word;
        }}
        p {{
            margin-bottom: 12px !important;
            word-wrap: break-word;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
            display: block;
            overflow-x: auto;
            white-space: nowrap;
        }}
        th, td {{
            border: 1px solid #cccccc;
            padding: 8px 12px;
            text-align: left;
        }}
    </style>
    {st.session_state["intro_content"]}
</div>
"""

st.markdown(document_html, unsafe_allow_html=True)
