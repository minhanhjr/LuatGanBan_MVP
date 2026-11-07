# -*- coding: utf-8 -*-
"""Cộng tác viên ngôn ngữ — Quản lý từ vựng, thuật ngữ và giọng đọc dân tộc."""
from __future__ import annotations

import json
from pathlib import Path
import streamlit as st

from core import auth
from core.llm import model_dang_dung
from core.translate import GLOSSARY_FILE

u = auth.nguoi_dang_nhap()
if not u:
    st.error("Bạn cần đăng nhập ở thanh bên trái.")
    st.stop()

st.title("🗣️ Cổng Quản Lý Của Cộng Tác Viên Ngôn Ngữ")
st.caption(f"Đang đăng nhập: **{u.get('mo_ta') or u['ten_dang_nhap']}** (Vai trò: CTV Ngôn ngữ)")

st.markdown("---")

tab1, tab2 = st.tabs(["📖 Quản lý Từ điển & Thuật ngữ", "🎙️ Trạng thái Giọng đọc"])

with tab1:
    st.subheader("Quản lý từ điển dịch thuật (Tiếng Mông / Tày)")
    st.caption(f"Đường dẫn file từ điển: `{GLOSSARY_FILE}`")
    
    if GLOSSARY_FILE.exists():
        try:
            glossary_data = json.loads(GLOSSARY_FILE.read_text(encoding="utf-8"))
            st.write(f"Tổng số thuật ngữ đang có trong từ điển: **{len(glossary_data)}** thuật ngữ.")
            
            # Hiển thị bảng tra cứu nhanh
            if glossary_data:
                st.dataframe(pd.DataFrame(list(glossary_data.items()), columns=["Thuật ngữ gốc", "Bản dịch"]), use_container_width=True)
        except Exception as e:
            st.error(f"Lỗi đọc file từ điển: {e}")
    else:
        st.info("Chưa có tệp từ điển tùy chỉnh nào được tạo.")

with tab2:
    st.subheader("Trạng thái Mô hình & Âm thanh")
    try:
        current_model = model_dang_dung()
        st.info(f"Mô hình AI hỗ trợ ngôn ngữ đang dùng: **{current_model}**")
    except Exception:
        st.info("Không lấy được thông tin mô hình.")
    
    st.markdown("Cộng tác viên có thể kiểm tra các bản ghi âm mẫu tại đây để đảm bảo phát âm chuẩn xác cho bà con đồng bào.")
