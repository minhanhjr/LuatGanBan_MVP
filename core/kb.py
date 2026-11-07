# -*- coding: utf-8 -*-
"""Kho tri thức (Knowledge Base) đọc trực tiếp từ Cơ sở dữ liệu PostgreSQL.

Tách hẳn khỏi Streamlit để có thể unit-test và chạy bằng script.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from core.config import DATA, MANIFEST, ROOT
from core.database import get_db_connection
import psycopg2.extras

# Vẫn giữ file ghi đè cũ làm vùng đệm tương thích ngược nếu cần
GHI_DE_FILE = DATA / "kho_ghi_de.json"


@dataclass
class ThuTuc:
    key: str
    ma_thu_tuc: str
    ten: str
    nhom: list[str] = field(default_factory=list)
    linh_vuc: str = ""
    cap_thuc_hien: str = ""
    doi_tuong: str = ""
    co_quan_thuc_hien: str = ""
    pdf: str = ""
    raw_txt: str = ""
    sections: list[str] = field(default_factory=list)
    so_ky_tu: int = 0
    an: bool = False               # ẩn khỏi danh sách cho bà con chọn
    ghi_chu: str = ""

    @property
    def pdf_path(self) -> Path:
        return ROOT / self.pdf

    def text(self) -> str:
        p = ROOT / self.raw_txt
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def section(self, *names: str) -> str:
        """Lấy 1 hoặc nhiều mục lớn trong PDF (đã cắt sẵn ở bước extract)."""
        p = self.pdf_path.parent / "sections.json"
        if not p.exists():
            return self.text()
        data = json.loads(p.read_text(encoding="utf-8"))
        if not names:
            return "\n\n".join(f"## {k}\n{v}" for k, v in data.items())
        out = []
        for n in names:
            for k, v in data.items():
                if n.upper() in k.upper():
                    out.append(f"## {k}\n{v}")
        return "\n\n".join(out)


def doc_ghi_de() -> dict:
    if GHI_DE_FILE.exists():
        try:
            return json.loads(GHI_DE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def luu_ghi_de(key: str, **truong) -> None:
    """Ghi đè một vài trường của 1 thủ tục (ten / nhom / cap_thuc_hien / an / ghi_chu)."""
    g = doc_ghi_de()
    g.setdefault(key, {}).update({k: v for k, v in truong.items() if v is not None})
    GHI_DE_FILE.parent.mkdir(parents=True, exist_ok=True)
    GHI_DE_FILE.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
    reload_kb()


def xoa_ghi_de(key: str | None = None) -> None:
    """Bỏ phần sửa tay, quay về đúng dữ liệu gốc trong manifest."""
    if key is None:
        GHI_DE_FILE.write_text("{}", encoding="utf-8")
    else:
        g = doc_ghi_de()
        g.pop(key, None)
        GHI_DE_FILE.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
    reload_kb()


@lru_cache(maxsize=1)
def load_kb() -> list[ThuTuc]:
    """Tải toàn bộ kho tri thức trực tiếp từ PostgreSQL (Đồng bộ vĩnh viễn)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM thu_tuc_hanh_chinh ORDER BY id ASC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        rows = []

    if not rows:
        # Fallback đọc từ manifest nếu DB trống
        if not MANIFEST.exists():
            return []
        raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        merged: dict[str, ThuTuc] = {}
        for r in raw.get("thu_tuc", []):
            key = r["key"]
            if key in merged:
                if r.get("nhom") and r["nhom"] not in merged[key].nhom:
                    merged[key].nhom.append(r["nhom"])
                continue
            merged[key] = ThuTuc(
                key=key,
                ma_thu_tuc=r.get("ma_thu_tuc", ""),
                ten=r.get("ten", ""),
                nhom=[r["nhom"]] if r.get("nhom") else [],
                linh_vuc=r.get("linh_vuc", ""),
                cap_thuc_hien=r.get("cap_thuc_hien", ""),
                doi_tuong=r.get("doi_tuong", ""),
                co_quan_thuc_hien=r.get("co_quan_thuc_hien", ""),
                pdf=r.get("pdf", ""),
                raw_txt=r.get("raw_txt", ""),
                sections=r.get("sections", []),
                so_ky_tu=r.get("so_ky_tu", 0),
            )
        return list(merged.values())

    danh_sach: list[ThuTuc] = []
    for r in rows:
        # Xử lý nhóm từ JSON text trong DB
        nhom_val = r.get("nhom", [])
        if isinstance(nhom_val, str):
            try:
                nhom_val = json.loads(nhom_val)
            except Exception:
                nhom_val = [nhom_val] if nhom_val else []
        elif not isinstance(nhom_val, list):
            nhom_val = []

        # Xử lý sections từ JSON text trong DB
        sec_val = r.get("sections", [])
        if isinstance(sec_val, str):
            try:
                sec_val = json.loads(sec_val)
            except Exception:
                sec_val = []

        # Xác định trạng thái ẩn dựa vào cột trang_thai hoặc an
        trang_thai = r.get("trang_thai", "da_duyet")
        is_an = bool(r.get("an", False)) or (trang_thai == "tu_choi")

        t = ThuTuc(
            key=r.get("key", ""),
            ma_thu_tuc=r.get("ma_thu_tuc", ""),
            ten=r.get("ten_thu_tuc") or r.get("ten", ""),
            nhom=nhom_val,
            linh_vuc=r.get("linh_vuc", ""),
            cap_thuc_hien=r.get("cap_thuc_hien", ""),
            doi_tuong=r.get("doi_tuong", ""),
            co_quan_thuc_hien=r.get("co_quan_thuc_hien", ""),
            pdf=r.get("pdf", ""),
            raw_txt=r.get("raw_txt", ""),
            sections=sec_val,
            so_ky_tu=r.get("so_ky_tu", 0),
            an=is_an,
            ghi_chu=r.get("ghi_chu", "")
        )
        danh_sach.append(t)
    return danh_sach


def reload_kb() -> None:
    load_kb.cache_clear()


def theo_nhom(nhom: str, gom_ca_an: bool = False) -> list[ThuTuc]:
    return [t for t in load_kb() if nhom in t.nhom and (gom_ca_an or not t.an)]


def theo_key(key: str) -> ThuTuc | None:
    return next((t for t in load_kb() if t.key == key), None)


def danh_sach_rut_gon(nhom: str | None = None) -> list[dict]:
    """Danh sách tối giản để nhồi vào prompt Gemini (tiết kiệm token)."""
    src = theo_nhom(nhom) if nhom else [t for t in load_kb() if not t.an]
    return [
        {"key": t.key, "ten": t.ten, "cap": t.cap_thuc_hien, "doi_tuong": t.doi_tuong}
        for t in src
    ]


def thong_ke() -> dict:
    kho = load_kb()
    return {
        "so_thu_tuc": len(kho),
        "so_nhom": len({n for t in kho for n in t.nhom}),
        "thieu_pdf": [t.key for t in kho if not t.pdf_path.exists()],
        "tong_ky_tu": sum(t.so_ky_tu for t in kho),
        "so_an": sum(1 for t in kho if t.an),
        "so_sua_tay": len(doc_ghi_de()),
    }
