# -*- coding: utf-8 -*-
"""Dashboard quản trị kho hướng dẫn - Cập nhật dùng PostgreSQL đầy đủ mọi tab.

Mỗi tab tương ứng một quyền trong core/auth.QUYEN. Cán bộ chỉ thấy tab mình
được cấp; quản trị viên thấy tất cả.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

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
from giao_dien.van_ban_ui import (
    TEP_DIEU_KHOAN_AI_NGOAI,
    co_quyen_dang_dieu_khoan_ai_ngoai,
    doc_dieu_khoan_ai_ngoai,
    hien_thi_dieu_khoan_ai_ngoai,
    tai_khoan_sua_dieu_khoan_ai,
)

try:
    from core.config import DATA as _DATA_DIR
except ImportError:
    _DATA_DIR = ROOT / "data"

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
EXCEL_DIR.mkdir(parents=True, exist_ok=True)

u = auth.nguoi_dang_nhap()
if not u:
    st.error("Bạn cần đăng nhập ở thanh bên trái.")
    st.stop()

st.title("🛠️ Quản trị kho hướng dẫn")
st.caption(f"Đang đăng nhập: **{u.get('mo_ta') or u['ten_dang_nhap']}** · "
           f"{'Quản trị viên (toàn quyền)' if auth.la_admin() else 'Cán bộ / Giảng viên / CTV ngôn ngữ'}")
st.caption("Kho hướng dẫn thủ tục được lưu trong cơ sở dữ liệu PostgreSQL.")

TAB_DEF = [
    ("kho_thu_tuc",      "📊 Kho thủ tục (DB)"),
    ("cap_nhat_du_lieu", "📥 Cập nhật dữ liệu"),
    ("cau_tra_loi",      "✅ Kiểm duyệt câu trả lời (DB)"),
    ("tu_vung_giong",    "🗣️ Từ vựng & giọng đọc"),
    ("bo_nho_tam",       "🧹 Bộ nhớ tạm"),
    ("phan_hoi",         "💬 Phản hồi & Nhật ký (IS-02)"),
]
duoc_phep = [
    (q, nhan) for q, nhan in TAB_DEF
    if (q == "phan_hoi" and auth.quyen_cua(u)) or (q != "phan_hoi" and auth.co_quyen(q))
]
if co_quyen_dang_dieu_khoan_ai_ngoai():
    duoc_phep.append(("dieu_khoan_ai_ngoai", "📄 Điều khoản AI ngoài"))
if not duoc_phep:
    st.warning("Tài khoản của bạn chưa được cấp quyền nào trên trang này.")
    st.stop()

tabs = dict(zip([q for q, _ in duoc_phep], st.tabs([n for _, n in duoc_phep])))

GIOI_HAN_TEP = 2 * 1024 * 1024
GIOI_HAN_NOI_DUNG = 15_000


def _kiem_tra_noi_dung(van_ban: str) -> str:
    van_ban = van_ban.strip()
    if "\x00" in van_ban or not any(ky_tu.isalnum() for ky_tu in van_ban):
        raise ValueError("Điều khoản phải có nội dung bằng chữ. Nếu tệp PDF là ảnh scan, hãy dùng bản Word hoặc TXT.")
    if len(van_ban) > GIOI_HAN_NOI_DUNG:
        raise ValueError("Nội dung quá dài. Hãy chỉ tải phần điều khoản AI bên ngoài (tối đa 15.000 ký tự).")
    return van_ban


def trich_xuat_dieu_khoan(ten_tep: str, du_lieu: bytes) -> str:
    if not du_lieu or len(du_lieu) > GIOI_HAN_TEP:
        raise ValueError("Hãy chọn tệp có nội dung và dung lượng tối đa 2 MB.")
    duoi_tep = Path(ten_tep).suffix.lower()
    if duoi_tep == ".txt":
        try:
            return _kiem_tra_noi_dung(du_lieu.decode("utf-8-sig"))
        except UnicodeError as exc:
            raise ValueError("Tệp TXT cần được lưu dưới dạng UTF-8.") from exc

    if duoi_tep == ".docx":
        from docx import Document
        from docx.text.paragraph import Paragraph

        tep = io.BytesIO(du_lieu)
        try:
            with ZipFile(tep) as goi:
                if sum(tep_nen.file_size for tep_nen in goi.infolist()) > 10 * 1024 * 1024:
                    raise ValueError("Tệp Word quá lớn sau khi giải nén.")
            tep.seek(0)
            doc = Document(tep)
            cac_doan = []
            for khoi in doc.iter_inner_content():
                if isinstance(khoi, Paragraph):
                    cac_doan.append(khoi.text)
                else:
                    for hang in khoi.rows:
                        cac_doan.append(" | ".join(o.text for o in hang.cells))
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Không đọc được tệp Word. Hãy chọn một tệp .docx hợp lệ.") from exc
        return _kiem_tra_noi_dung("\n\n".join(doan for doan in cac_doan if doan.strip()))

    if duoi_tep == ".pdf":
        import pdfplumber

        try:
            with pdfplumber.open(io.BytesIO(du_lieu)) as pdf:
                if len(pdf.pages) > 15:
                    raise ValueError("Tệp PDF được giới hạn 15 trang. Hãy chỉ tải phần điều khoản AI bên ngoài.")
                cac_trang = [trang.extract_text() or "" for trang in pdf.pages]
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Không đọc được tệp PDF. Hãy chọn bản PDF có chữ hoặc dùng Word.") from exc
        if any(not trang.strip() for trang in cac_trang):
            raise ValueError("Có trang PDF không trích được chữ. Hãy dùng bản Word hoặc tệp văn bản để tránh thiếu nội dung.")
        return _kiem_tra_noi_dung("\n\n".join(cac_trang))

    raise ValueError("Hãy chọn tệp Word (.docx), PDF có chữ hoặc TXT.")


def luu_dieu_khoan_ai_ngoai(ten_tep: str, noi_dung: str) -> None:
    tai_khoan = tai_khoan_sua_dieu_khoan_ai()
    if tai_khoan is None:
        raise PermissionError("Chỉ quản trị viên và cán bộ đang hoạt động được cập nhật điều khoản.")
    ban = {
        "noi_dung": _kiem_tra_noi_dung(noi_dung),
        "ten_tep": Path(ten_tep.replace("\\", "/")).name,
        "nguoi_cap_nhat": tai_khoan["ten_dang_nhap"],
        "cap_nhat_luc": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    thu_muc = TEP_DIEU_KHOAN_AI_NGOAI.parent
    thu_muc.mkdir(parents=True, exist_ok=True)
    tep_tam = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=thu_muc, delete=False) as tep:
            tep_tam = Path(tep.name)
            json.dump(ban, tep, ensure_ascii=False)
            tep.flush()
            os.fsync(tep.fileno())
        os.replace(tep_tam, TEP_DIEU_KHOAN_AI_NGOAI)
    finally:
        if tep_tam is not None:
            tep_tam.unlink(missing_ok=True)


def hien_thi_quan_ly_dieu_khoan_ai_ngoai() -> None:
    if not co_quyen_dang_dieu_khoan_ai_ngoai():
        return

    ban = doc_dieu_khoan_ai_ngoai()
    khoa_noi_dung = "is20_noi_dung_soan"
    khoa_tep = "is20_ten_tep_soan"
    st.session_state.setdefault(khoa_noi_dung, ban.get("noi_dung", ""))
    st.session_state.setdefault(khoa_tep, ban.get("ten_tep", ""))

    st.subheader("Điều khoản khi chuyển sang AI bên ngoài")
    st.caption("Soạn trực tiếp hoặc lấy nội dung từ tệp. Chọn Lưu và hiển thị để công bố.")
    tep = st.file_uploader(
        "Chọn Word (.docx), PDF có chữ hoặc TXT (tối đa 2 MB)",
        type=["docx", "pdf", "txt"],
        key="is20_tep_dieu_khoan",
    )
    if tep is not None and st.button("Đưa nội dung tệp vào ô soạn thảo", key="is20_nhap_tep"):
        try:
            noi_dung = trich_xuat_dieu_khoan(tep.name, tep.getvalue())
        except ValueError as exc:
            st.warning(str(exc))
        else:
            st.session_state[khoa_noi_dung] = noi_dung
            st.session_state[khoa_tep] = tep.name

    noi_dung = st.text_area("Nội dung điều khoản", key=khoa_noi_dung, height=270,
                           max_chars=GIOI_HAN_NOI_DUNG)
    if st.button("Lưu và hiển thị", key="is20_luu_dieu_khoan", type="primary"):
        try:
            luu_dieu_khoan_ai_ngoai(st.session_state[khoa_tep], noi_dung)
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
        except OSError:
            st.error("Chưa lưu được bản mới. Vui lòng thử lại hoặc báo quản trị viên.")
        else:
            st.success("Đã lưu. Hộp thoại sẽ hiện điều khoản mới.")
            ban = doc_dieu_khoan_ai_ngoai()

    if ban:
        with st.expander("Xem điều khoản đang công bố"):
            if ban.get("ten_tep"):
                st.text(f"Tệp nguồn: {ban['ten_tep']}")
            st.text(f"Cập nhật: {ban.get('nguoi_cap_nhat', '')} · {ban.get('cap_nhat_luc', '')}")
            hien_thi_dieu_khoan_ai_ngoai(ban["noi_dung"])
    else:
        st.info("Chưa có điều khoản được công bố.")


if "dieu_khoan_ai_ngoai" in tabs:
    with tabs["dieu_khoan_ai_ngoai"]:
        hien_thi_quan_ly_dieu_khoan_ai_ngoai()


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

        with st.container(key="lgb-kho-metrics"):
            c = st.columns(4)
            c[0].metric("Tổng Thủ tục trong DB", len(df))
            c[1].metric("Đã duyệt (Hiện trên web)", so_da_duyet)
            c[2].metric("Chờ duyệt", len(df) - so_da_duyet - so_an)
            c[3].metric("Từ chối (Ẩn)", so_an)

        st.divider()
        st.subheader("Cán bộ: Sửa nội dung (Lưu nháp / Chờ duyệt)")
        st.caption("Chỉnh sửa nội dung tại đây. Lưu ý: Mọi sửa đổi sẽ bị chuyển thành trạng thái **'Chờ duyệt'** "
                   "và bài viết sẽ tạm ẩn khỏi người dân cho đến khi Admin duyệt.")

        with st.container(key="lgb-meo-bang"):
            st.caption("Trên điện thoại, vuốt bảng sang ngang để xem các cột còn lại.")
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
        st.subheader("📥 Cập nhật dữ liệu từ file Excel / PDF")
        st.caption("Tải tệp dịch vụ công mới lên hệ thống để thực hiện bóc tách tự động vào Cơ sở dữ liệu PostgreSQL.")

        # Khối tải tệp trực tiếp từ trình duyệt
        uploaded_files = st.file_uploader(
            "📤 Chọn hoặc kéo thả tệp mới (Excel .xlsx hoặc PDF .pdf)",
            type=["xlsx", "pdf"],
            accept_multiple_files=True,
            key="uploader_tthc"
        )

        if uploaded_files:
            saved_count = 0
            for uploaded_file in uploaded_files:
                target_path = EXCEL_DIR / uploaded_file.name
                with open(target_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                saved_count += 1
            st.success(f"✅ Đã tải lên thành công {saved_count} tệp vào thư mục `file_dichvucong/`!")

        st.divider()
        st.markdown("### 📂 Danh sách tệp nguồn hiện có trên máy chủ")
        
        files = list(EXCEL_DIR.glob("*.xlsx")) + list(EXCEL_DIR.glob("*.pdf"))
        if files:
            st.write(f"Tìm thấy **{len(files)}** tệp tài liệu:")
            for f in files:
                col_f1, col_f2 = st.columns([4, 1])
                col_f1.markdown(f"📄 **{f.name}** (`{f.stat().st_size / 1024:.1f} KB`)")
                if col_f2.button("🗑️ Xóa tệp", key=f"del_{f.name}"):
                    f.unlink()
                    st.toast(f"Đã xóa tệp {f.name}")
                    st.rerun()
        else:
            st.info("Chưa có tệp tài liệu nào trong thư mục `file_dichvucong/`.")

        st.divider()
        st.markdown("### ⚙️ Bóc tách & Đồng bộ vào CSDL")
        if st.button("🚀 Chạy bóc tách dữ liệu thủ tục (extract_tthc.py)", type="primary", use_container_width=True):
            with st.spinner("Đang bóc tách và trích xuất dữ liệu thủ tục vào PostgreSQL..."):
                try:
                    res = subprocess.run([sys.executable, "tools/extract_tthc.py"], capture_output=True, text=True, timeout=180)
                    if res.returncode == 0:
                        st.success("🎉 Trích xuất và bóc tách dữ liệu thành công!")
                        if res.stdout.strip():
                            st.code(res.stdout)
                        st.cache_data.clear()
                    else:
                        st.error("Có lỗi xảy ra trong quá trình bóc tách:")
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


# =========================================================== 6 · PHẢN HỒI & NHẬT KÝ (IS-02)
if "phan_hoi" in tabs:
    with tabs["phan_hoi"]:
        st.subheader("💬 Nhật ký phản hồi & Đánh giá câu trả lời (IS-02)")
        st.caption(
            "Tuân thủ R6: Hệ thống chỉ ghi nhận số liệu không định danh (thời gian, thủ tục, ngôn ngữ, "
            "đánh giá mức độ hiểu và lượt kết nối cán bộ/Messenger) phục vụ đo KPI M2 và nhật ký tuần HĐ3.4; "
            "tuyệt đối không lưu giọng nói hay thông tin cá nhân."
        )

        tep_log = _DATA_DIR / "phan_hoi.jsonl"
        ban_ghi_list = []
        if tep_log.exists():
            for dong in tep_log.read_text(encoding="utf-8").splitlines():
                dong = dong.strip()
                if not dong:
                    continue
                try:
                    ban_ghi_list.append(json.loads(dong))
                except Exception:
                    continue

        if not ban_ghi_list:
            st.info("Chưa có dữ liệu phản hồi nào được ghi nhận. Khi người dân bấm đánh giá (Hiểu được / Chưa hiểu) hoặc yêu cầu cán bộ hỗ trợ, dữ liệu sẽ hiển thị tại đây.")
        else:
            df_log = pd.DataFrame(ban_ghi_list)
            for cot in ["thoi_gian", "ngay", "loai", "ma_thu_tuc", "ten_thu_tuc", "ngon_ngu", "tin_cay"]:
                if cot not in df_log.columns:
                    df_log[cot] = ""

            df_log = df_log.sort_values(by="thoi_gian", ascending=False).reset_index(drop=True)

            # Chỉ số tổng hợp & KPI M2
            so_hieu = int((df_log["loai"] == "danh_gia_hieu").sum())
            so_chua_hieu = int((df_log["loai"] == "danh_gia_chua_hieu").sum())
            so_can_cb = int((df_log["loai"] == "can_can_bo").sum())
            tong_dg = so_hieu + so_chua_hieu
            ty_le_chua_hieu = f"{(so_chua_hieu / tong_dg * 100):.1f}%" if tong_dg > 0 else "—"

            with st.container(key="lgb-phan-hoi-metrics"):
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Tổng lượt ghi nhận", len(df_log))
                m2.metric("👍 Hiểu được", so_hieu)
                m3.metric("👎 Chưa hiểu", so_chua_hieu)
                m4.metric("Tỷ lệ chưa hiểu (M2)", ty_le_chua_hieu)
                m5.metric("🙋 Cần cán bộ / Messenger", so_can_cb)

            st.divider()

            # Bộ lọc theo thủ tục / ngày / loại phản hồi
            NHAN_LOAI = {
                "danh_gia_hieu": "👍 Hiểu được",
                "danh_gia_chua_hieu": "👎 Chưa hiểu",
                "can_can_bo": "🙋 Cần cán bộ / Messenger",
                "gop_y_thao_tac": "Góp ý: Khó thao tác",
                "gop_y_am_thanh": "Góp ý: Khó nghe âm thanh",
                "gop_y_mang": "Góp ý: Trang tải chậm",
                "gop_y_noi_dung": "Góp ý: Hướng dẫn chưa rõ",
            }
            NHAN_NGON_NGU = {
                "mong": "Tiếng Mông",
                "tay": "Tiếng Tày",
                "viet": "Tiếng Việt",
            }

            f1, f2, f3 = st.columns([2, 1.2, 1.3])
            ds_thu_tuc = ["Tất cả thủ tục"] + sorted([x for x in df_log["ten_thu_tuc"].dropna().unique() if str(x).strip()])
            ds_ngay = ["Tất cả các ngày"] + sorted([x for x in df_log["ngay"].dropna().unique() if str(x).strip()], reverse=True)
            ds_loai = ["Tất cả loại", *NHAN_LOAI.values()]

            chon_tt = f1.selectbox("Lọc theo thủ tục", ds_thu_tuc, key="loc_ph_thu_tuc")
            chon_ngay = f2.selectbox("Lọc theo ngày", ds_ngay, key="loc_ph_ngay")
            chon_loai = f3.selectbox("Lọc theo loại", ds_loai, key="loc_ph_loai")

            df_loc = df_log.copy()
            df_loc["Loại phản hồi"] = df_loc["loai"].map(lambda x: NHAN_LOAI.get(x, x))
            df_loc["Ngôn ngữ"] = df_loc["ngon_ngu"].map(lambda x: NHAN_NGON_NGU.get(x, x))

            if chon_tt != "Tất cả thủ tục":
                df_loc = df_loc[df_loc["ten_thu_tuc"] == chon_tt]
            if chon_ngay != "Tất cả các ngày":
                df_loc = df_loc[df_loc["ngay"] == chon_ngay]
            if chon_loai != "Tất cả loại":
                df_loc = df_loc[df_loc["Loại phản hồi"] == chon_loai]

            df_hien_thi = df_loc[[
                "thoi_gian", "ngay", "Loại phản hồi", "ma_thu_tuc", "ten_thu_tuc", "Ngôn ngữ", "tin_cay"
            ]].rename(columns={
                "thoi_gian": "Thời gian",
                "ngay": "Ngày",
                "ma_thu_tuc": "Mã thủ tục",
                "ten_thu_tuc": "Tên thủ tục",
                "tin_cay": "Độ tin cậy AI",
            })

            st.dataframe(df_hien_thi, use_container_width=True, hide_index=True)

            csv_bytes = df_hien_thi.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="⬇️ Xuất nhật ký phản hồi ra tệp CSV (HĐ3.4)",
                data=csv_bytes,
                file_name=f"nhat_ky_phan_hoi_LGB_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True,
            )
