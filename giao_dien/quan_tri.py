# -*- coding: utf-8 -*-
"""Dashboard quản trị kho hướng dẫn - Cập nhật dùng PostgreSQL đầy đủ mọi tab.

Mỗi tab tương ứng một quyền trong core/auth.QUYEN. Cán bộ chỉ thấy tab mình
được cấp; quản trị viên thấy tất cả.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from psycopg2.extras import RealDictCursor

from core import auth, kb
from core.config import (AUDIO_BANK, CACHE_AUDIO, CACHE_SIMPLIFIED,
                         DANH_MUC_THU_TUC, ROOT)
from core.llm import (LoiQuota, danh_sach_model, ly_do_chan, model_dang_dung,
                        so_den, xoa_so_den)
from core.simplify import CAU_HOI_MAC_DINH, _cache_file, don_gian_hoa
from core.translate import GLOSSARY_FILE

# Nhập các hàm DB từ core.database an toàn
try:
    from core.database import (can_bo_cap_nhat_thu_tuc, 
                               admin_lay_danh_sach_theo_trang_thai, 
                               admin_duyet_hoac_tu_choi,
                               get_db_connection)
except ImportError:
    can_bo_cap_nhat_thu_tuc = None
    admin_lay_danh_sach_theo_trang_thai = None
    admin_duyet_hoac_tu_choi = None
    get_db_connection = None

EXCEL_DIR = ROOT / "file_dichvucong"

u = auth.nguoi_dang_nhap()
if not u:
    st.error("Bạn cần đăng nhập ở thanh bên trái.")
    st.stop()

st.title("🛠️ Quản trị kho hướng dẫn")
st.caption(f"Đang đăng nhập: **{u.get('mo_ta') or u['ten_dang_nhap']}** · "
           f"{'Quản trị viên (toàn quyền)' if auth.la_admin() else 'Cán bộ'}")
st.caption("Dữ liệu được lưu đồng bộ vĩnh viễn vào Cơ sở dữ liệu PostgreSQL.")

TAB_DEF = [
    ("kho_thu_tuc",      "📊 Kho thủ tục (DB)"),
    ("cap_nhat_du_lieu", "📥 Cập nhật dữ liệu"),
    ("cau_tra_loi",      "✅ Kiểm duyệt câu trả lời (DB)"),
    ("tu_vung_giong",    "🗣️ Từ vựng & giọng đọc"),
    ("bo_nho_tam",       "🧹 Bộ nhớ tạm"),
]
duoc_phep = [(q, nhan) for q, nhan in TAB_DEF if auth.co_quyen(q)]
if not duoc_phep:
    st.warning("Tài khoản của bạn chưa được cấp quyền nào trên trang này.")
    st.stop()

tabs = dict(zip([q for q, _ in duoc_phep], st.tabs([n for _, n in duoc_phep])))


# =========================================================== 1 · KHO THỦ TỤC
if "kho_thu_tuc" in tabs:
    with tabs["kho_thu_tuc"]:
        try:
            conn = get_db_connection()
