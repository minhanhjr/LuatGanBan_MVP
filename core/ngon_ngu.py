# -*- coding: utf-8 -*-
"""Danh mục ngôn ngữ của ứng dụng — MỘT chỗ duy nhất liệt kê các tiếng.

Giao diện chọn tiếng, danh sách nút loa và thứ tự dịch đều đọc từ đây, nên
thêm một tiếng mới chỉ cần:

  1. Thêm một dòng NgonNgu(...) vào DANH_SACH bên dưới.
  2. Viết hàm dịch Việt -> tiếng đó trong core/translate.py
     và hàm đọc thành tiếng trong core/tts.py.
  3. Thêm câu lệnh nhận giọng nói của tiếng đó vào core/stt.py
     (từ điển _PROMPT_THEO_TIENG).
  4. Đăng ký hàm xử lý trong giao_dien/cong_dan.py (từ điển _XU_LY_TIENG).
"""
from __future__ import annotations

from dataclasses import dataclass

from core.config import BAT_TIENG_TAY

MA_TIENG_VIET = "viet"          # tiếng gốc: mọi câu trả lời đều soạn bằng tiếng Việt trước


@dataclass(frozen=True)
class NgonNgu:
    ma: str                     # mã nội bộ: 'mong', 'tay', 'viet'...
    ten: str                    # tên hiện trên màn hình
    bat: bool = True            # False = tạm ẩn, không xoá code

    @property
    def nhan(self) -> str:
        return f"🔊 {self.ten}"


DANH_SACH: list[NgonNgu] = [
    NgonNgu("mong", "Tiếng Mông"),
    NgonNgu("tay", "Tiếng Tày", bat=BAT_TIENG_TAY),
    NgonNgu(MA_TIENG_VIET, "Tiếng Việt"),
]

MAC_DINH = ["mong"]             # tiếng được chọn sẵn khi mở trang


def dang_dung() -> list[NgonNgu]:
    return [n for n in DANH_SACH if n.bat]


def theo_ma(ma: str) -> NgonNgu | None:
    return next((n for n in DANH_SACH if n.ma == ma), None)
