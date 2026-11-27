# -*- coding: utf-8 -*-
"""Hướng dẫn ngắn cho lần đầu sử dụng."""
import streamlit as st

st.title("Hướng dẫn sử dụng")
st.markdown("""
1. **Hỏi bằng giọng nói.** Mở trang hỏi bằng giọng nói, bấm nút micro, nói
   thủ tục cần hỏi rồi bấm dừng. Trong mục **Chọn tiếng**, tiếng đầu tiên là tiếng bà con nói.
2. **Chọn thủ tục.** Nếu mạng yếu hoặc không dùng được micro, mở **Chọn thủ tục**
   để chọn từ danh sách hoặc gõ câu hỏi.
3. **Nghe hướng dẫn.** Khi có kết quả, bấm **Nghe bằng…** để tải giọng đọc.
   Nếu máy chưa phát tự động, bấm nút phát trên thanh âm thanh.
4. **Cần trợ giúp.** Bấm nút hỗ trợ cán bộ dưới kết quả nếu còn thắc mắc.
   Mục **Góp ý** dùng để báo chỗ khó dùng hoặc khó nghe trên trang.
""")
