# -*- coding: utf-8 -*-
"""Xử lý và hiển thị kết quả dùng chung cho hỏi bằng giọng nói và tra cứu."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from html import escape

import streamlit as st

from core import auth, ngon_ngu as NN
from core.config import DANH_MUC_THU_TUC, DATA, HMONG_ORTHOGRAPHY
from giao_dien.am_thanh import phat_am_thanh
from giao_dien.van_ban_ui import doc_dieu_khoan_ai_ngoai, hien_thi_dieu_khoan_ai_ngoai

ss = st.session_state
LINK_MESSENGER = "https://m.me/1231078760088554"


def ghi_phan_hoi_khong_dinh_danh(loai: str, kq: dict) -> bool:
    """Ghi yêu cầu hỗ trợ / đánh giá ra data/phan_hoi.jsonl.
    Tuyệt đối KHÔNG lưu giọng nói, KHÔNG lưu câu nói gốc hay thông tin định danh (R6).
    """
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        tep_log = DATA / "phan_hoi.jsonl"
        tt = kq.get("thu_tuc")
        tuyen = kq.get("tuyen") or {}
        diem = tuyen.get("tin_cay_thu_tuc")
        now = datetime.now()
        ban_ghi = {
            "thoi_gian": now.strftime("%Y-%m-%d %H:%M:%S"),
            "ngay": now.strftime("%Y-%m-%d"),
            "loai": loai,
            "ma_thu_tuc": tt.ma_thu_tuc if tt else "",
            "ten_thu_tuc": tt.ten if tt else tuyen.get("ten_nhom", ""),
            "ngon_ngu": kq.get("ma_ngon_ngu", "viet"),
            "tin_cay": round(float(diem), 2) if diem is not None else None,
        }
        with tep_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ban_ghi, ensure_ascii=False) + "\n")
        return True
    except (OSError, TypeError, ValueError):
        return False


@st.cache_data(ttl=3600, show_spinner=False)
def _dinh_tuyen(cau_noi: str) -> dict:
    from core.router import dinh_tuyen

    r = dinh_tuyen(cau_noi)
    r["_key"] = r["thu_tuc"].key if r["thu_tuc"] else ""
    r.pop("thu_tuc", None)
    return r


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _don_gian_hoa(key: str, cau_hoi: str) -> dict:
    from core import kb
    from core.simplify import don_gian_hoa

    return don_gian_hoa(kb.theo_key(key), cau_hoi)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _dich_mong(text: str) -> dict:
    from core.translate import dich_sang_mong

    return dich_sang_mong(text)


PHIEN_BAN_DICH_TAY = 2


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _dich_tay(text: str, phien_ban: int = PHIEN_BAN_DICH_TAY) -> str:
    from core.translate import dich_sang_tay

    return dich_sang_tay(text)


def chon_giong_nghe(*, key: str) -> list[str]:
    """Lưu lựa chọn tiếng cho cả trang micro và trang tra cứu."""
    ngon_ngu = {n.ma: n.nhan for n in NN.dang_dung()}
    ss.setdefault(key, [ma for ma in ss.get("cac_ngon_ngu", NN.MAC_DINH) if ma in ngon_ngu])
    with st.expander("🔊 Chọn tiếng"):
        lua_chon = st.multiselect(
            "Bà con muốn nghe bằng tiếng gì?",
            options=list(ngon_ngu),
            key=key,
            format_func=ngon_ngu.__getitem__,
            help="Tiếng chọn đầu tiên là tiếng bà con nói. Có thể chọn thêm tiếng để nghe.",
        )
    ss.cac_ngon_ngu = lua_chon or [NN.MA_TIENG_VIET]
    return ss.cac_ngon_ngu


def xu_ly_cau_noi(cau_noi: str, *, khoa: str, cac_tieng: list[str], thu_tuc=None) -> None:
    ket_qua = chay_pipeline(cau_noi, thu_tuc=thu_tuc)
    ket_qua["ma_ngon_ngu"] = cac_tieng[0]
    ket_qua["cac_ngon_ngu"] = list(cac_tieng)
    ss[khoa] = ket_qua


def _phat_audio(duong_dan, *, key: str) -> bool:
    if not phat_am_thanh(duong_dan, key=key, tu_phat=True):
        return False
    st.caption("Nếu chưa nghe thấy, bà con bấm nút phát trên thanh âm thanh.")
    return True


@st.fragment
def loa(text: str, *, nhan: str, key: str) -> None:
    if text.strip() and st.button(f"🔊 {nhan}", key=key, use_container_width=True):
        from core.tts import tts_tieng_viet

        try:
            with st.spinner("Đang chuẩn bị giọng đọc…"):
                duong_dan = tts_tieng_viet(text)
            if _phat_audio(duong_dan, key=key):
                return
        except OSError:
            pass
        st.info("Chưa phát được âm thanh. Bà con có thể thử lại hoặc đọc phần chữ.")


def _lay_ban_dich(kq: dict, ma: str):
    if ma not in kq:
        luc_bat_dau = time.perf_counter()
        kq[ma] = _dich_mong(kq["kich_ban"]) if ma == "mong" else _dich_tay(kq["kich_ban"])
        kq["thoi_gian"][f"dich_{ma}"] = time.perf_counter() - luc_bat_dau
    return kq[ma]


@st.fragment
def khung_nghe_ket_qua(kq: dict) -> None:
    from core.tts import phat_tieng_mong, phat_tieng_tay, tts_tieng_viet

    cac_tieng = list(dict.fromkeys([*kq["cac_ngon_ngu"], NN.MA_TIENG_VIET]))
    for ma in cac_tieng:
        tieng = NN.theo_ma(ma)
        if tieng is None:
            continue
        if st.button(f"🔊 Nghe bằng {tieng.ten.lower()}", key=f"is18_nghe_{ma}", use_container_width=True):
            luc_bat_dau = time.perf_counter()
            try:
                with st.spinner("Đang chuẩn bị giọng đọc…"):
                    if ma == "mong":
                        ban_dich = _lay_ban_dich(kq, ma)
                        tep, tang = phat_tieng_mong(ban_dich["rpa"], key=kq["thu_tuc"].key)
                        kq["tang_tts"] = tang
                    elif ma == "tay":
                        tep, tang = phat_tieng_tay(_lay_ban_dich(kq, ma))
                        kq["tang_tts_tay"] = tang
                    else:
                        tep = tts_tieng_viet(kq["kich_ban"])
                kq["thoi_gian"][f"tts_{ma}"] = time.perf_counter() - luc_bat_dau
                if _phat_audio(tep, key=f"ket_qua_{ma}"):
                    if ma == "tay" or (ma == "mong" and kq.get("tang_tts") == "vi_phonetic"):
                        st.caption("Giọng máy đọc tiếng dân tộc thiểu số.")
                else:
                    st.info("Chưa có giọng đọc này. Bà con thử lại hoặc chọn tiếng Việt.")
            except Exception as exc:
                kq[f"_loi_{ma}"] = str(exc)
                st.info("Chưa phát được âm thanh. Bà con thử lại hoặc chọn tiếng Việt.")

        if ma in ("mong", "tay"):
            if st.button(f"📖 Xem chữ {tieng.ten.lower()}", key=f"is18_xem_chu_{ma}"):
                try:
                    with st.spinner("Đang chuẩn bị bản chữ…"):
                        _lay_ban_dich(kq, ma)
                except Exception:
                    st.info("Chưa mở được bản chữ. Bà con có thể đọc kết quả tiếng Việt.")
            if ma == "mong" and kq.get("mong"):
                with st.expander("Bản chữ tiếng Mông", expanded=True):
                    st.caption("Chữ Mông kiểu Việt Nam" if HMONG_ORTHOGRAPHY == "vn" else "Chữ Mông RPA")
                    st.markdown(kq["mong"]["hien_thi"])
                    st.text(f"RPA: {kq['mong']['rpa']}")
                    st.text(f"Phiên âm VN: {kq['mong']['vn']}")
            elif ma == "tay" and kq.get("tay"):
                with st.expander("Bản chữ tiếng Tày", expanded=True):
                    st.caption("Chữ Tày–Nùng hệ Latinh · bản dịch máy, chưa được duyệt")
                    st.markdown(kq["tay"])


def _thong_diep_loi(e: Exception) -> str:
    from core.llm import LoiQuota

    if isinstance(e, LoiQuota):
        return ("Máy đang bận, bà con chờ vài phút rồi hỏi lại nhé. "
                "Hoặc chọn thủ tục ở mục **Chọn thủ tục**.")
    s = str(e)
    if "GEMINI_API_KEY" in s:
        return "Máy chưa được cài đặt xong. Bà con báo cán bộ giúp nhé."
    if "model" in s.lower() and ("404" in s or "not_found" in s.lower()):
        return "Máy đang bảo trì. Bà con báo cán bộ giúp nhé."
    return "Máy đang bận. Bà con thử lại sau ít phút nhé."


def chay_pipeline(cau_noi: str, *, thu_tuc=None) -> dict:
    from core import kb
    from core.simplify import CAU_HOI_MAC_DINH, thanh_van_ban_doc

    t0 = time.perf_counter()
    kq: dict = {"cau_noi": cau_noi, "thoi_gian": {}}

    with st.status("Đang tìm hướng dẫn cho bà con…", expanded=False) as box:
        box.write("Đang xem bà con cần làm việc gì…")
        t = time.perf_counter()
        try:
            if thu_tuc is None:
                tuyen = _dinh_tuyen(cau_noi)
            else:
                nhom = thu_tuc.nhom[0] if thu_tuc.nhom else "KHAC"
                tuyen = {
                    "_key": thu_tuc.key, "nhom": nhom,
                    "ten_nhom": DANH_MUC_THU_TUC.get(nhom, nhom),
                    "can_can_bo": False, "chon_truc_tiep": True,
                }
        except Exception as e:
            kq["loi"] = _thong_diep_loi(e)
            box.update(label="Chưa xong", state="error", expanded=False)
            return kq
        kq["thoi_gian"]["dinh_tuyen"] = time.perf_counter() - t
        kq["tuyen"] = tuyen
        tt = thu_tuc if thu_tuc is not None else (kb.theo_key(tuyen["_key"]) if tuyen["_key"] else None)
        kq["thu_tuc"] = tt

        if tuyen["can_can_bo"] or tt is None:
            box.update(label="Cần cán bộ hỗ trợ", state="complete", expanded=False)
            return kq
        box.write(f"Đúng việc: {tt.ten}")

        box.write("Đang đọc hướng dẫn của Nhà nước…")
        t = time.perf_counter()
        try:
            kq["don_gian"] = _don_gian_hoa(tt.key, CAU_HOI_MAC_DINH)
        except Exception as e:
            kq["loi"] = _thong_diep_loi(e)
            box.update(label="Chưa xong", state="error", expanded=False)
            return kq
        kq["thoi_gian"]["don_gian_hoa"] = time.perf_counter() - t
        kq["kich_ban"] = thanh_van_ban_doc(kq["don_gian"])

        kq["thoi_gian"]["tong"] = time.perf_counter() - t0
        box.update(label="Đã có hướng dẫn cho bà con", state="complete", expanded=False)
    return kq


@st.fragment
def khung_danh_gia_cau_tra_loi(kq: dict) -> None:
    """Nút đánh giá Hiểu được / Chưa hiểu (IS-02) để đo KPI M2."""
    tt = kq.get("thu_tuc")
    ma_phien = hashlib.md5(
        f"{tt.key if tt else ''}_{kq.get('cau_noi', '')}".encode("utf-8")
    ).hexdigest()[:10]
    khoa_da_dg = f"da_danh_gia_{ma_phien}"

    st.markdown("---")
    st.markdown("**Bà con nghe có hiểu hướng dẫn này không?**")
    c_hieu, c_chua = st.columns(2)
    with c_hieu:
        if st.button("👍 Hiểu được", key=f"btn_hieu_{ma_phien}", use_container_width=True):
            if not ss.get(khoa_da_dg):
                ghi_phan_hoi_khong_dinh_danh("danh_gia_hieu", kq)
                ss[khoa_da_dg] = "hieu"
    with c_chua:
        if st.button("👎 Chưa hiểu", key=f"btn_chua_{ma_phien}", use_container_width=True):
            if not ss.get(khoa_da_dg):
                ghi_phan_hoi_khong_dinh_danh("danh_gia_chua_hieu", kq)
                ss[khoa_da_dg] = "chua_hieu"

    trang_thai_dg = ss.get(khoa_da_dg)
    if trang_thai_dg == "hieu":
        st.success("✅ Cảm ơn bà con! Rất vui vì hướng dẫn dễ hiểu.")
    elif trang_thai_dg == "chua_hieu":
        st.info("🙏 Cảm ơn bà con. Bà con có thể bấm nghe lại hoặc nhắn tin hỏi cán bộ bên dưới nhé.")


LINK_CHATGPT = "https://chatgpt.com/"
LINK_GEMINI = "https://gemini.google.com/"
KHOA_DONG_Y_AI_NGOAI = "is20_dong_y"


def nut_nghe_canh_bao(noi_dung: str, *, key: str) -> None:
    from core.tts import tts_tieng_viet

    """Chỉ tạo và tải âm thanh khi người dùng yêu cầu nghe."""
    if not st.button("🔊 Nghe điều khoản", key=key, use_container_width=True):
        return
    try:
        with st.spinner("Đang chuẩn bị lời nhắc…"):
            duong_dan = tts_tieng_viet(noi_dung, tag="canh_bao_ai_ngoai")
        if _phat_audio(duong_dan, key=key):
            return
    except Exception:
        pass
    st.info("Chưa phát được lời nhắc. Bà con vui lòng đọc nội dung bên trên hoặc nhờ cán bộ hỗ trợ.")


def _chap_nhan_dieu_khoan(noi_dung: str) -> None:
    # Gắn sự đồng ý với nội dung đã hiển thị trong lần mở này.
    st.session_state[KHOA_DONG_Y_AI_NGOAI] = noi_dung


@st.dialog("Điều khoản khi chuyển sang AI bên ngoài")
def hop_thoai_ai_ngoai() -> None:
    noi_dung = doc_dieu_khoan_ai_ngoai().get("noi_dung", "")
    nhan_quay_lai = "Quay lại Luật Gần Bản"
    if noi_dung:
        hien_thi_dieu_khoan_ai_ngoai(noi_dung)
        nut_nghe_canh_bao(noi_dung, key="is20_nghe_canh_bao")
        st.caption("Luật Gần Bản chỉ mở liên kết. Câu hỏi và bản ghi âm không tự động gửi sang công cụ bên ngoài.")

        if st.session_state.get(KHOA_DONG_Y_AI_NGOAI) == noi_dung:
            st.link_button("Mở ChatGPT (OpenAI)", LINK_CHATGPT, use_container_width=True)
            st.link_button("Mở Gemini (Google)", LINK_GEMINI, use_container_width=True)
        else:
            st.caption("Tôi đã đọc và hiểu các nội dung cảnh báo trên và tự nguyện tiếp tục truy cập công cụ AI bên ngoài.")
            st.button(
                "Đồng ý",
                key="is20_chap_nhan",
                type="primary",
                use_container_width=True,
                on_click=_chap_nhan_dieu_khoan,
                args=(noi_dung,),
            )
            nhan_quay_lai = "Không đồng ý"
    else:
        st.warning("Hiện chưa mở được điều khoản. Bà con có thể quay lại và nhờ cán bộ hỗ trợ.")

    if st.button(nhan_quay_lai, key="is20_quay_lai", use_container_width=True):
        st.session_state.pop(KHOA_DONG_Y_AI_NGOAI, None)
        st.rerun()


def hien_thi_lua_chon_ai_ngoai() -> None:
    if st.button("🤖 Chuyển sang AI bên ngoài", key="is20_mo_canh_bao",
                 use_container_width=True):
        st.session_state.pop(KHOA_DONG_Y_AI_NGOAI, None)
        hop_thoai_ai_ngoai()


@st.fragment
def nut_goi_can_bo(kq: dict) -> None:
    st.markdown("<br>", unsafe_allow_html=True)
    tt = kq.get("thu_tuc")
    ma_phien = hashlib.md5(
        f"{tt.key if tt else ''}_{kq.get('cau_noi', '')}".encode("utf-8")
    ).hexdigest()[:10]
    khoa_cb = f"da_goi_cb_{ma_phien}"

    if st.button("🙋 CẦN CÁN BỘ HỖ TRỢ TRỰC TIẾP", key=f"btn_cb_{ma_phien}", use_container_width=True):
        if not ss.get(khoa_cb):
            ghi_phan_hoi_khong_dinh_danh("can_can_bo", kq)
            ss[khoa_cb] = True
            ss.setdefault("danh_sach_yeu_cau", []).append({
                "thoi_gian": datetime.now().strftime("%d/%m %H:%M:%S"),
                "van_de": tt.ten if tt else kq["tuyen"]["ten_nhom"],
                "ma": tt.ma_thu_tuc if tt else "",
                "chi_tiet": kq["cau_noi"],
                "tin_cay": kq["tuyen"].get("tin_cay_thu_tuc", 0),
                "trang_thai": "Mới",
            })

    if ss.get(khoa_cb):
        st.success("✅ Đã ghi nhận yêu cầu hỗ trợ. Bấm nút xanh bên dưới để nhắn tin hoặc gửi ghi âm trực tiếp cho cán bộ:")

    st.link_button(
        "💬 Nhắn tin trực tiếp với cán bộ qua Messenger",
        LINK_MESSENGER,
        type="primary",
        use_container_width=True,
    )


@st.fragment
def khung_tai_lieu_goc(kq: dict, giay_to_tuy_chon: list[dict]) -> None:
    tt, dg, tuyen = kq["thu_tuc"], kq["don_gian"], kq["tuyen"]
    if not st.toggle("⚖️ Xem căn cứ pháp lý và tài liệu gốc", key=f"is18_tai_lieu_{tt.key}"):
        return

    la_can_bo = bool(auth.nguoi_dang_nhap())

    with st.container(border=True):
        st.caption(f"Mã thủ tục {tt.ma_thu_tuc} · cấp {tt.cap_thuc_hien}")
        if la_can_bo:
            from core.tts import NHAN_TANG

            cot1, cot2 = st.columns(2)
            cot1.metric("Độ tin cậy bản tóm tắt", f"{dg.get('do_tin_cay', 0):.0%}")
            if tuyen.get("chon_truc_tiep"):
                cot2.metric("Cách xác định", "Chọn trực tiếp")
            else:
                cot2.metric("Độ tin cậy phân loại", f"{tuyen.get('tin_cay_thu_tuc', 0):.0%}")
            st.caption(f"Giọng Mông đã dùng: {NHAN_TANG.get(kq.get('tang_tts',''), '—')}")
            if kq.get("_loi_mong"):
                st.caption(f"Lỗi tiếng Mông: {kq['_loi_mong'][:200]}")
            if kq.get("tang_tts_tay"):
                st.caption(f"Giọng Tày đã dùng: {NHAN_TANG.get(kq['tang_tts_tay'], '—')}"
                           + (f" · dịch bằng {kq['model_dich_tay']}"
                              if kq.get("model_dich_tay") else ""))
            if kq.get("_loi_tay"):
                st.caption(f"Lỗi tiếng Tày: {kq['_loi_tay'][:200]}")
        if dg.get("chua_ro"):
            st.warning("Tài liệu **không nêu rõ**: " + "; ".join(dg["chua_ro"]))
        for l in dg.get("luu_y", []):
            st.markdown(f"- {l}")
        if dg.get("cac_buoc"):
            st.markdown("**Các bước:**")
            for i, b in enumerate(dg["cac_buoc"], 1):
                st.markdown(f"{i}. {b}")
        if dg.get("trich_dan"):
            st.markdown("**Trích nguyên văn tài liệu gốc:**")
            for q in dg["trich_dan"]:
                st.markdown(f"> {q}")
        if giay_to_tuy_chon:
            st.markdown("**Giấy tờ không bắt buộc:** "
                        + ", ".join(m["ten_don_gian"] for m in giay_to_tuy_chon))
        if tt.pdf_path.is_file():
            st.download_button("⬇️ Tải file hướng dẫn gốc (PDF)",
                               tt.pdf_path.read_bytes(),
                               file_name=f"{tt.ma_thu_tuc}.pdf", mime="application/pdf")
        if la_can_bo:
            tg = kq.get("thoi_gian", {})
            st.caption("Thời gian xử lý: "
                       + "  ·  ".join(f"{k} {v:.1f}s" for k, v in tg.items()))


def hien_ket_qua(kq: dict) -> None:
    if kq.get("loi"):
        st.error(kq["loi"])
        loa(kq["loi"], nhan="Nghe lời nhắc", key="is18_nghe_loi")
        kq.setdefault("tuyen", {"ten_nhom": "VẤN ĐỀ KHÁC", "tin_cay_thu_tuc": 0})
        nut_goi_can_bo(kq)
        return
    if kq.get("canh_bao"):
        st.info(kq["canh_bao"])

    tuyen, tt = kq["tuyen"], kq.get("thu_tuc")

    if tuyen["can_can_bo"] or tt is None:
        cau_hoi = (tuyen.get("cau_hoi_lam_ro")
                   or "Bà con muốn hỏi về việc gì ạ? Bà con nói rõ hơn giúp máy nhé.")
        st.markdown(
            f'<div style="font-size:22px;line-height:1.6;padding:14px 16px;'
            f'background:#FFF8E1;border-left:5px solid #F0A500;border-radius:8px;">'
            f'❓ {escape(cau_hoi)}</div>',
            unsafe_allow_html=True,
        )
        loa(cau_hoi, nhan="Nghe câu hỏi", key="is18_nghe_hoi_lai")
        st.caption("Bà con có thể hỏi lại hoặc bấm nút dưới để gặp cán bộ.")
        nut_goi_can_bo(kq)
        return

    dg = kq["don_gian"]
    st.success(f"🏷️ **{tt.ten}**")
    if dg.get("_da_duyet"):
        st.caption(f"✅ Nội dung đã được **{dg.get('_nguoi_duyet','cán bộ')}** duyệt.")

    with st.container(border=True):
        st.markdown('<div class="the-tra-loi">', unsafe_allow_html=True)
        st.markdown(f"**{dg.get('tom_tat_1_cau','')}**")
        di = dg.get("di_dau", {})
        st.markdown(f"📍 **Đi đâu:** {di.get('noi_don_gian','—')}")
        bb = [m for m in dg.get("mang_gi", []) if m.get("bat_buoc")]
        kbb = [m for m in dg.get("mang_gi", []) if not m.get("bat_buoc")]
        if bb:
            st.markdown("🎒 **Mang theo:**")
            for m in bb:
                sl = f" — {m['so_luong']}" if m.get("so_luong") else ""
                st.markdown(f"  • {m['ten_don_gian']}{sl}")
        c1, c2 = st.columns(2)
        c1.markdown(f"⏱️ **Chờ:** {dg.get('bao_lau','—')}")
        c2.markdown(f"💰 **Tiền:** {dg.get('bao_nhieu_tien','—')}")
        st.markdown("</div>", unsafe_allow_html=True)

    khung_nghe_ket_qua(kq)

    khung_tai_lieu_goc(kq, kbb)

    khung_danh_gia_cau_tra_loi(kq)
    nut_goi_can_bo(kq)


def hien_ket_qua_da_luu(khoa: str) -> None:
    if kq := ss.get(khoa):
        st.divider()
        hien_ket_qua(kq)
        hien_thi_lua_chon_ai_ngoai()
