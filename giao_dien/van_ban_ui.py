# -*- coding: utf-8 -*-
"""Trình bày nội dung giới thiệu và điều khoản trên mọi cỡ màn hình."""
from __future__ import annotations

from html import escape
import json

import streamlit as st

from core import auth
from core.config import DATA


# Lưu trên volume Docker hiện có, ngoài các thư mục có nút xóa cache.
TEP_DIEU_KHOAN_AI_NGOAI = DATA / "cache" / "cau_hinh" / "dieu_khoan_ai_ngoai.json"


def tai_khoan_sua_dieu_khoan_ai() -> dict | None:
    dang_nhap = auth.nguoi_dang_nhap()
    if not dang_nhap:
        return None
    # Dùng vai trò hiện tại, kể cả khi tài khoản đã mở phiên trước khi đổi quyền.
    tai_khoan = auth.doc_users().get(dang_nhap.get("ten_dang_nhap"))
    if tai_khoan and tai_khoan.get("kich_hoat", True) and tai_khoan.get("vai_tro") in ("admin", "can_bo"):
        return tai_khoan
    return None


def co_quyen_dang_dieu_khoan_ai_ngoai() -> bool:
    return tai_khoan_sua_dieu_khoan_ai() is not None


def doc_dieu_khoan_ai_ngoai() -> dict:
    try:
        ban = json.loads(TEP_DIEU_KHOAN_AI_NGOAI.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {}
    if isinstance(ban, dict) and isinstance(ban.get("noi_dung"), str) and ban["noi_dung"].strip():
        return ban
    return {}


def hien_thi_dieu_khoan_ai_ngoai(noi_dung: str) -> None:
    with st.container(height=245, border=True):
        st.html(f'<div style="white-space: pre-wrap; overflow-wrap: anywhere;">{escape(noi_dung)}</div>')


def hien_thi_van_ban(noi_dung: str, *, key: str) -> None:
    """Hiển thị cả Markdown và HTML, đồng thời giới hạn kiểu trong khung văn bản."""
    if key not in {"lgb-van-ban-gioi-thieu", "lgb-van-ban-dieu-khoan"}:
        raise ValueError("Khóa khung văn bản không hợp lệ")

    st.html("""
    <style>
      .st-key-lgb-van-ban-gioi-thieu, .st-key-lgb-van-ban-dieu-khoan {
        background: #fff; color: #111; padding: clamp(15px, 3.5vw, 45px);
        margin: 5px auto; max-width: 900px; width: 100%; box-sizing: border-box;
        border-radius: 6px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        font-family: 'Times New Roman', Times, serif; line-height: 1.7;
        font-size: clamp(15px, 1.8vw, 17px); overflow-wrap: anywhere;
      }
      .st-key-lgb-van-ban-gioi-thieu img, .st-key-lgb-van-ban-dieu-khoan img {
        max-width: 100% !important; height: auto !important; display: block !important;
        margin: 20px auto !important; border-radius: 6px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12) !important;
      }
      .st-key-lgb-van-ban-gioi-thieu h2, .st-key-lgb-van-ban-gioi-thieu h3,
      .st-key-lgb-van-ban-gioi-thieu h4, .st-key-lgb-van-ban-dieu-khoan h2,
      .st-key-lgb-van-ban-dieu-khoan h3, .st-key-lgb-van-ban-dieu-khoan h4 {
        color: #003366 !important; font-family: 'Times New Roman', Times, serif !important;
        font-weight: bold !important; margin-top: 20px !important; margin-bottom: 10px !important;
        overflow-wrap: anywhere;
      }
      .st-key-lgb-van-ban-gioi-thieu p, .st-key-lgb-van-ban-gioi-thieu li,
      .st-key-lgb-van-ban-dieu-khoan p, .st-key-lgb-van-ban-dieu-khoan li {
        margin-bottom: 12px !important; overflow-wrap: anywhere;
      }
      .st-key-lgb-van-ban-gioi-thieu table, .st-key-lgb-van-ban-dieu-khoan table {
        border-collapse: collapse; width: 100%; margin: 15px 0; display: block;
        overflow-x: auto; white-space: nowrap;
      }
      .st-key-lgb-van-ban-gioi-thieu th, .st-key-lgb-van-ban-gioi-thieu td,
      .st-key-lgb-van-ban-dieu-khoan th, .st-key-lgb-van-ban-dieu-khoan td {
        border: 1px solid #ccc; padding: 8px 12px; text-align: left;
      }
    </style>
    """)
    with st.container(key=key):
        st.markdown(noi_dung, unsafe_allow_html=True)

