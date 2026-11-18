# -*- coding: utf-8 -*-
"""Phân loại ý định 2 tầng: nhóm thủ tục -> thủ tục cụ thể.

Tầng 2 là điểm khác biệt so với bản MVP cũ: trong "khai sinh" có tới 14 thủ tục
khác nhau (đăng ký mới, đăng ký lại, có yếu tố nước ngoài, lưu động...).
Chỉ đường sai thủ tục = bà con đi sai cửa, mất một ngày đường.
"""
from __future__ import annotations

import json
import re
import unicodedata

from core.config import DANH_MUC_THU_TUC, NGUONG_TU_TIN
from core.kb import ThuTuc, danh_sach_rut_gon, theo_key, theo_nhom
from core.llm import goi_gemini_json

SCHEMA_NHOM = {
    "type": "object",
    "properties": {
        "nhom": {"type": "string", "enum": list(DANH_MUC_THU_TUC.keys())},
        "do_tin_cay": {"type": "number"},
        "ly_do": {"type": "string"},
        "cau_hoi_lam_ro": {"type": "string"},
    },
    "required": ["nhom", "do_tin_cay"],
}

SCHEMA_CHI_TIET = {
    "type": "object",
    "properties": {
        "key": {"type": "string"},
        "do_tin_cay": {"type": "number"},
        "ly_do": {"type": "string"},
        "cau_hoi_lam_ro": {"type": "string"},
    },
    "required": ["key", "do_tin_cay"],
}

SYSTEM_PHAN_LOAI = """\
Bạn là công chức tiếp nhận hồ sơ ở bộ phận một cửa cấp xã. Nghe bà con trình bày
và xác định họ cần thủ tục nào.

NGUYÊN TẮC
- Bà con thường nói bằng việc-đời-thường, không nói tên thủ tục.
  "vợ tôi mới sinh" -> khai sinh. "bố tôi mất" -> khai tử.
  "tôi muốn lấy vợ" -> kết hôn. "xin giấy chưa có vợ" -> xác nhận độc thân.
- KHÔNG đoán khi câu nói mơ hồ. Đặt do_tin_cay thấp và nêu 1 câu hỏi ngắn
  ở cau_hoi_lam_ro để hỏi lại bà con.
- Thà chuyển cho cán bộ còn hơn chỉ sai thủ tục.
"""

_TU_DUNG = {
    "thu", "tuc", "dang", "ky", "cap", "ban", "sao", "viec", "ho", "tich",
    "cua", "cong", "dan", "viet", "nam", "tai", "co", "quan", "nha", "nuoc",
    "tham", "quyen", "cho", "nguoi", "da", "duoc", "giai", "quyet",
    "toi", "muon", "lam", "xin", "giay", "hoi", "ve",
}


def _chuan_hoa(van_ban: str) -> str:
    s = (van_ban or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = s.replace("đ", "d")
    s = re.sub(r"[^a-z0-9\s\.]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("thu tuc "):
        s = s[8:].strip()
    return s


def _tat_ca_thu_tuc() -> list[tuple[str, ThuTuc]]:
    ket_qua: list[tuple[str, ThuTuc]] = []
    da_co: set[str] = set()
    for ma_nhom in DANH_MUC_THU_TUC:
        for tt in theo_nhom(ma_nhom):
            if tt.key not in da_co:
                da_co.add(tt.key)
                ket_qua.append((ma_nhom, tt))
    return ket_qua


def _khop_truc_tiep_hoac_tu_khoa(cau_noi: str, *, chi_khop_chinh_xac: bool = False) -> tuple[str, ThuTuc, float] | None:
    """Khớp trực tiếp theo mã thủ tục, tên thủ tục chuẩn hóa hoặc từ khóa đặc trưng."""
    ds = _tat_ca_thu_tuc()
    if not ds:
        return None

    cau_raw = (cau_noi or "").strip()
    cau_ch = _chuan_hoa(cau_raw)
    if not cau_ch:
        return None

    # 1. Khớp theo mã thủ tục (VD: 2.000522) hoặc tên thủ tục đầy đủ
    for ma_nhom, tt in ds:
        if tt.ma_thu_tuc and tt.ma_thu_tuc in cau_raw:
            return ma_nhom, tt, 1.0
        ten_ch = _chuan_hoa(tt.ten)
        if ten_ch and (cau_ch == ten_ch or ten_ch in cau_ch or (len(cau_ch) >= 18 and cau_ch in ten_ch)):
            return ma_nhom, tt, 1.0

    if chi_khop_chinh_xac:
        return None

    # 2. Lưới dự phòng theo độ trùng từ khóa đặc trưng (bỏ từ dừng)
    tu_cau = {w for w in cau_ch.split() if len(w) >= 2 and w not in _TU_DUNG}
    if not tu_cau:
        return None

    best_score = 0.0
    best_item: tuple[str, ThuTuc] | None = None
    for ma_nhom, tt in ds:
        ten_ch = _chuan_hoa(tt.ten)
        tu_ten = {w for w in ten_ch.split() if len(w) >= 2 and w not in _TU_DUNG}
        if not tu_ten:
            continue
        giao = tu_cau & tu_ten
        if not giao:
            continue
        diem = 0.65 * (len(giao) / len(tu_cau)) + 0.35 * (len(giao) / len(tu_ten))
        if diem > best_score:
            best_score = diem
            best_item = (ma_nhom, tt)

    if best_item and best_score >= max(0.55, NGUONG_TU_TIN):
        return best_item[0], best_item[1], round(min(best_score, 0.95), 2)
    return None


def phan_loai_nhom(cau_noi: str) -> dict:
    prompt = (
        "Các nhóm thủ tục:\n"
        + "\n".join(f"- {k}: {v}" for k, v in DANH_MUC_THU_TUC.items())
        + f'\n\nBà con nói: "{cau_noi}"'
    )
    return goi_gemini_json(prompt, schema=SCHEMA_NHOM, system=SYSTEM_PHAN_LOAI,
                           vai_tro="fast", temperature=0.0, cache_tag="nhom")


def chon_thu_tuc(cau_noi: str, nhom: str) -> dict:
    ds = danh_sach_rut_gon(nhom)
    if not ds:
        return {"key": "", "do_tin_cay": 0.0, "ly_do": f"Chưa có dữ liệu cho nhóm {nhom}"}
    if len(ds) == 1:
        return {"key": ds[0]["key"], "do_tin_cay": 0.9, "ly_do": "Nhóm chỉ có 1 thủ tục"}

    prompt = (
        f'Bà con nói: "{cau_noi}"\n\n'
        "Chọn ĐÚNG MỘT thủ tục trong danh sách dưới đây (trả về trường key).\n"
        "Mặc định chọn thủ tục PHỔ THÔNG nhất (người Việt Nam, trong nước, "
        "không có yếu tố nước ngoài, không phải đăng ký lại) trừ khi bà con nói rõ khác.\n\n"
        + json.dumps(ds, ensure_ascii=False, indent=1)
    )
    return goi_gemini_json(prompt, schema=SCHEMA_CHI_TIET, system=SYSTEM_PHAN_LOAI,
                           vai_tro="fast", temperature=0.0, cache_tag="chitiet")


def dinh_tuyen(cau_noi: str) -> dict:
    """Kết quả điều hướng đầy đủ cho 1 câu nói."""
    # Tầng 0: Khớp trực tiếp tên hoặc mã thủ tục trong kho -> trả về ngay
    khop_chuan = _khop_truc_tiep_hoac_tu_khoa(cau_noi, chi_khop_chinh_xac=True)
    if khop_chuan:
        nhom_k, tt_k, diem_k = khop_chuan
        return {
            "nhom": nhom_k,
            "ten_nhom": DANH_MUC_THU_TUC.get(nhom_k, "THỦ TỤC HÀNH CHÍNH"),
            "tin_cay_nhom": diem_k,
            "cau_hoi_lam_ro": "",
            "thu_tuc": tt_k,
            "tin_cay_thu_tuc": diem_k,
            "can_can_bo": False,
        }

    # Tầng 1 & 2: Phân loại bằng Gemini AI (có lưới an toàn từ khóa nếu lỗi/vào nhóm KHAC)
    try:
        r1 = phan_loai_nhom(cau_noi)
    except Exception:
        khop_du_phong = _khop_truc_tiep_hoac_tu_khoa(cau_noi, chi_khop_chinh_xac=False)
        if khop_du_phong:
            nhom_k, tt_k, diem_k = khop_du_phong
            return {
                "nhom": nhom_k,
                "ten_nhom": DANH_MUC_THU_TUC.get(nhom_k, "THỦ TỤC HÀNH CHÍNH"),
                "tin_cay_nhom": diem_k,
                "cau_hoi_lam_ro": "",
                "thu_tuc": tt_k,
                "tin_cay_thu_tuc": diem_k,
                "can_can_bo": False,
            }
        raise

    nhom = r1.get("nhom", "KHAC")
    out = {
        "nhom": nhom,
        "ten_nhom": DANH_MUC_THU_TUC.get(nhom, "VẤN ĐỀ KHÁC"),
        "tin_cay_nhom": float(r1.get("do_tin_cay", 0)),
        "cau_hoi_lam_ro": r1.get("cau_hoi_lam_ro", ""),
        "thu_tuc": None,
        "tin_cay_thu_tuc": 0.0,
        "can_can_bo": False,
    }

    # Nếu AI phân vào KHAC hoặc tin cậy nhóm thấp, tìm tiếp trong nhóm KHAC hoặc từ khóa trước khi đẩy cho cán bộ
    if nhom == "KHAC" or out["tin_cay_nhom"] < NGUONG_TU_TIN:
        ds_khac = danh_sach_rut_gon("KHAC") if nhom == "KHAC" else []
        if ds_khac:
            r2 = chon_thu_tuc(cau_noi, "KHAC")
            tt_khac = theo_key(r2.get("key", ""))
            if tt_khac is not None and float(r2.get("do_tin_cay", 0)) >= NGUONG_TU_TIN:
                out["thu_tuc"] = tt_khac
                out["tin_cay_thu_tuc"] = float(r2.get("do_tin_cay", 0))
                return out

        khop_du_phong = _khop_truc_tiep_hoac_tu_khoa(cau_noi, chi_khop_chinh_xac=False)
        if khop_du_phong:
            nhom_k, tt_k, diem_k = khop_du_phong
            out["nhom"] = nhom_k
            out["ten_nhom"] = DANH_MUC_THU_TUC.get(nhom_k, out["ten_nhom"])
            out["thu_tuc"] = tt_k
            out["tin_cay_thu_tuc"] = diem_k
            return out

        out["can_can_bo"] = True
        return out

    r2 = chon_thu_tuc(cau_noi, nhom)
    tt: ThuTuc | None = theo_key(r2.get("key", ""))
    out["thu_tuc"] = tt
    out["tin_cay_thu_tuc"] = float(r2.get("do_tin_cay", 0))
    out["cau_hoi_lam_ro"] = out["cau_hoi_lam_ro"] or r2.get("cau_hoi_lam_ro", "")
    if tt is None or out["tin_cay_thu_tuc"] < NGUONG_TU_TIN:
        khop_du_phong = _khop_truc_tiep_hoac_tu_khoa(cau_noi, chi_khop_chinh_xac=False)
        if khop_du_phong:
            nhom_k, tt_k, diem_k = khop_du_phong
            out["nhom"] = nhom_k
            out["ten_nhom"] = DANH_MUC_THU_TUC.get(nhom_k, out["ten_nhom"])
            out["thu_tuc"] = tt_k
            out["tin_cay_thu_tuc"] = diem_k
            return out
        out["can_can_bo"] = True
    return out
