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
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM thu_tuc_hanh_chinh ORDER BY id DESC")
            ds_db = cur.fetchall()
            cur.close()
            conn.close()
        except Exception as e:
            st.error(f"Lỗi đọc DB: {e}")
            ds_db = []

        rows = []
        so_an, so_da_duyet = 0, 0
        for r in ds_db:
            trang_thai_hien_thi = ""
            if r["trang_thai"] == "da_duyet":
                trang_thai_hien_thi = "✅ Đã duyệt"
                so_da_duyet += 1
            elif r["trang_thai"] == "cho_duyet":
                trang_thai_hien_thi = "🟡 Chờ duyệt"
            elif r["trang_thai"] == "tu_choi":
                trang_thai_hien_thi = "❌ Từ chối"
                so_an += 1
                
            rows.append({
                "Mã": r["ma_thu_tuc"], 
                "Tên thủ tục": r["ten_thu_tuc"],
                "Cập nhật bởi": r.get("nguoi_tao", "System"),
                "Ký tự": len(r.get("noi_dung_tieng_viet", "") or ""), 
                "Trạng thái": trang_thai_hien_thi,
            })
            
        df = pd.DataFrame(rows)

        c = st.columns(4)
        c[0].metric("Tổng Thủ tục trong DB", len(df))
        c[1].metric("Đã duyệt (Hiện trên web)", so_da_duyet)
        c[2].metric("Chờ duyệt", len(df) - so_da_duyet - so_an)
        c[3].metric("Từ chối (Ẩn)", so_an)

        st.divider()
        st.subheader("Cán bộ: Sửa nội dung (Lưu nháp / Chờ duyệt)")
        st.caption("Chỉnh sửa nội dung tại đây. Lưu ý: Mọi sửa đổi sẽ bị chuyển thành trạng thái **'Chờ duyệt'** "
                   "và bài viết sẽ tạm ẩn khỏi người dân cho đến khi Admin duyệt.")

        df_sua = st.data_editor(
            df, use_container_width=True, hide_index=True, key="ed_kho",
            column_config={
                "Mã": st.column_config.TextColumn(disabled=True, width="small"),
                "Tên thủ tục": st.column_config.TextColumn(width="large"),
                "Cập nhật bởi": st.column_config.TextColumn(disabled=True),
                "Ký tự": st.column_config.NumberColumn(disabled=True),
                "Trạng thái": st.column_config.TextColumn(disabled=True),
            },
        )

        if st.button("💾 Lưu thay đổi (Gửi yêu cầu duyệt)", type="primary", use_container_width=True):
            goc = df.set_index("Mã").to_dict("index")
            n = 0
            for _, r in df_sua.iterrows():
                key = r["Mã"]
                cu = goc.get(key, {})
                if str(r["Tên thủ tục"]).strip() != str(cu.get("Tên thủ tục", "")):
                    if can_bo_cap_nhat_thu_tuc:
                        try:
                            can_bo_cap_nhat_thu_tuc(
                                ma_tt=key,
                                ten_tt=str(r["Tên thủ tục"]).strip(),
                                nd_vi="Cán bộ đã đổi tên thủ tục",
                                nd_hmong="",
                                sdt_can_bo="",
                                nguoi_thuc_hien=u.get('ten_dang_nhap', 'can_bo')
                            )
                            n += 1
                        except Exception as e:
                            st.error(f"Lỗi: {e}")
            if n > 0:
                st.success(f"Đã cập nhật {n} thủ tục và chuyển sang chế độ CHỜ DUYỆT.")
                st.cache_data.clear()
                st.rerun()


# =========================================================== 2 · CẬP NHẬT DỮ LIỆU
if "cap_nhat_du_lieu" in tabs:
    with tabs["cap_nhat_du_lieu"]:
        st.subheader("Cập nhật dữ liệu từ file Excel / PDF")
        st.caption("Đặt các file dịch vụ công mới vào thư mục `file_dichvucong/` trên VPS rồi bấm nút bên dưới.")
        if EXCEL_DIR.exists():
            files = list(EXCEL_DIR.glob("*.xlsx")) + list(EXCEL_DIR.glob("*.pdf"))
            st.write(f"Tìm thấy **{len(files)}** tệp nguồn trong `file_dichvucong/`.")
            for f in files:
                st.text(f" - {f.name} ({f.stat().st_size / 1024:.1f} KB)")
        else:
            st.warning("Thư mục `file_dichvucong/` chưa tồn tại.")

        if st.button("🚀 Chạy script trích xuất dữ liệu (extract_tthc.py)", type="primary"):
            with st.spinner("Đang trích xuất dữ liệu..."):
                try:
                    res = subprocess.run([sys.executable, "tools/extract_tthc.py"], capture_output=True, text=True, timeout=120)
                    if res.returncode == 0:
                        st.success("Trích xuất thành công!")
                        st.code(res.stdout)
                    else:
                        st.error("Có lỗi xảy ra khi trích xuất:")
                        st.code(res.stderr)
                except Exception as ex:
                    st.error(f"Lỗi thực thi: {ex}")


# =========================================================== 3 · KIỂM DUYỆT CÂU TRẢ LỜI
if "cau_tra_loi" in tabs:
    with tabs["cau_tra_loi"]:
        st.subheader("Admin: Phê duyệt Thủ tục (PostgreSQL)")
        st.caption("Chỉ những thủ tục có trạng thái **'Đã duyệt'** mới hiển thị bên phía Người dân.")

        if admin_lay_danh_sach_theo_trang_thai:
            ds_cho_duyet = admin_lay_danh_sach_theo_trang_thai('cho_duyet')
            ds_da_duyet = admin_lay_danh_sach_theo_trang_thai('da_duyet')
            
            c = st.columns(2)
            c[0].metric("Bài đang chờ duyệt", len(ds_cho_duyet))
            c[1].metric("Bài đã duyệt (Live)", len(ds_da_duyet))
            
            if ds_cho_duyet:
                st.markdown("### Danh sách bài chờ duyệt")
                for r in ds_cho_duyet:
                    with st.expander(f"🟡 {r['ma_thu_tuc']} - {r['ten_thu_tuc']}"):
                        st.caption(f"Cập nhật lần cuối bởi: {r.get('nguoi_tao', 'N/A')}")
                        st.text_area("Nội dung", r.get("noi_dung_tieng_viet", ""), height=100, disabled=True, key=f"txt_{r['ma_thu_tuc']}")
                        
                        col1, col2 = st.columns(2)
                        if col1.button("✅ Phê duyệt (Hiển thị ngay)", key=f"duyet_{r['ma_thu_tuc']}", type="primary"):
                            admin_duyet_hoac_tu_choi(r['ma_thu_tuc'], "da_duyet", u.get("ten_dang_nhap", "admin"))
                            st.success("Đã phê duyệt.")
                            st.rerun()
                        if col2.button("❌ Từ chối", key=f"tu_choi_{r['ma_thu_tuc']}"):
                            admin_duyet_hoac_tu_choi(r['ma_thu_tuc'], "tu_choi", u.get("ten_dang_nhap", "admin"))
                            st.warning("Đã từ chối.")
                            st.rerun()
            else:
                st.info("Hiện không có bài viết nào cần duyệt.")

            if ds_da_duyet:
                st.markdown("---")
                st.markdown("### Danh sách bài ĐÃ duyệt (Có thể gỡ xuống)")
                for r in ds_da_duyet[:10]:
                    with st.expander(f"✅ {r['ma_thu_tuc']} - {r['ten_thu_tuc']}"):
                        if st.button("Hủy phê duyệt (Gỡ khỏi Web)", key=f"huy_{r['ma_thu_tuc']}"):
                            admin_duyet_hoac_tu_choi(r['ma_thu_tuc'], "tu_choi", u.get("ten_dang_nhap", "admin"))
                            st.rerun()
        else:
            st.error("Chưa kết nối được Database.")


# =========================================================== 4 · TỪ VỰNG & GIỌNG ĐỌC
if "tu_vung_giong" in tabs:
    with tabs["tu_vung_giong"]:
        st.subheader("Quản lý từ vựng và cấu hình giọng đọc")
        st.markdown("Kiểm tra từ điển dịch thuật và trạng thái các mô hình âm thanh.")
        if GLOSSARY_FILE.exists():
            st.text(f"Đường dẫn từ điển: {GLOSSARY_FILE}")
            try:
                glossary_data = json.loads(GLOSSARY_FILE.read_text(encoding="utf-8"))
                st.write(f"Số lượng thuật ngữ dịch: **{len(glossary_data)}**")
            except Exception:
                st.info("Định dạng từ điển trống hoặc lỗi.")
        else:
            st.info("Chưa có tệp từ điển tùy chỉnh.")

        st.markdown("### Trạng thái Mô hình LLM & Giọng đọc")
        try:
            current_model = model_dang_dung()
            st.info(f"Model Gemini đang sử dụng: **{current_model}**")
        except Exception:
            st.info("Không lấy được tên model hiện tại.")


# =========================================================== 5 · BỘ NHỚ TẠM
if "bo_nho_tam" in tabs:
    with tabs["bo_nho_tam"]:
        st.subheader("Dọn dẹp bộ nhớ tạm & Cache")
        st.caption("Xóa các tệp cache phân tích, cache âm thanh tạm thời để giải phóng dung lượng VPS.")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🧹 Xóa cache âm thanh (CACHE_AUDIO)"):
                if CACHE_AUDIO.exists():
                    shutil.rmtree(CACHE_AUDIO)
                    CACHE_AUDIO.mkdir(parents=True, exist_ok=True)
                    st.success("Đã xóa cache âm thanh thành công!")
                else:
                    st.info("Thư mục cache âm thanh trống.")
        with c2:
            if st.button("🧹 Xóa cache rút gọn (CACHE_SIMPLIFIED)"):
                if CACHE_SIMPLIFIED.exists():
                    shutil.rmtree(CACHE_SIMPLIFIED)
                    CACHE_SIMPLIFIED.mkdir(parents=True, exist_ok=True)
                    st.success("Đã xóa cache rút gọn thành công!")
                else:
                    st.info("Thư mục cache rút gọn trống.")
