# -*- coding: utf-8 -*-
"""Cổng người dân — hỏi đáp thủ tục bằng giọng nói.

Nguyên tắc giao diện (voice-first):
- MỘT nút. Bà con bấm micro, nói, bấm dừng — hệ thống tự chạy hết chuỗi,
    không có nút "xử lý" thứ hai.
- Không hiện con số kỹ thuật. Bà con không cần biết "độ tin cậy 10%";
    họ chỉ cần biết máy nghe rõ hay chưa. Mọi chỉ số dời vào mục dành cho
    cán bộ ở cuối trang.
- Chữ nào cũng có loa. Người không đọc được vẫn phải dùng được trọn vẹn,
    nên mọi nội dung trả lời đều kèm trình phát tiếng.
- Gõ chữ là đường phụ, đặt cuối trang, cỡ nhỏ.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import html as _html

# Chống trình duyệt tự dịch tiếng Việt sang tiếng Anh làm mất chữ
st.markdown('<html lang="vi"></html>', unsafe_allow_html=True)

from core import auth, kb
from core.config import (DANH_MUC_THU_TUC, HMONG_ORTHOGRAPHY,
                         NGUONG_TU_TIN, TTS_HMONG_PROVIDER)
from core.llm import LoiQuota, chon_model
from core import ngon_ngu as NN
from core.router import dinh_tuyen
from core.simplify import CAU_HOI_MAC_DINH, don_gian_hoa, thanh_van_ban_doc
from core.stt import nghe
from core.translate import (dich_sang_mong, dich_sang_tay, dich_sang_viet,
                            dich_tay_sang_viet)
from core.tts import NHAN_TANG, phat_tieng_mong, phat_tieng_tay, tts_tieng_viet

try:
    from core.config import DATA as _DATA_DIR
except ImportError:
    _DATA_DIR = Path(__file__).resolve().parent.parent / "data"

LINK_MESSENGER = "https://m.me/1231078760088554"

# Tích hợp kết nối CSDL PostgreSQL an toàn để lọc bài đã duyệt
try:
    from core.database import get_db_connection
    import psycopg2.extras
    def lay_danh_sach_thu_tuc_cho_nguoi_dan(tu_khoa: str = ""):
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            if tu_khoa.strip():
                cur.execute(
                    "SELECT * FROM thu_tuc_hanh_chinh WHERE (trang_thai = 'da_duyet' OR an = FALSE) AND (ten_thu_tuc ILIKE %s OR ma_thu_tuc ILIKE %s) ORDER BY id ASC",
                    (f"%{tu_khoa.strip()}%", f"%{tu_khoa.strip()}%")
                )
            else:
                cur.execute("SELECT * FROM thu_tuc_hanh_chinh WHERE trang_thai = 'da_duyet' OR an = FALSE ORDER BY id ASC")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []
except ImportError:
    lay_danh_sach_thu_tuc_cho_nguoi_dan = None

ss = st.session_state
ss.setdefault("danh_sach_yeu_cau", [])
ss.setdefault("ket_qua", None)
ss.setdefault("cau_noi", "")
ss.setdefault("audio_da_xu_ly", "")

if not kb.load_kb():
    st.error(
        "**Kho dữ liệu trống.** Hãy kiểm tra lại kết nối Cơ sở dữ liệu PostgreSQL."
    )
    st.stop()


# ==========================================================================
# GHI NHẬT KÝ PHẢN HỒI KHÔNG ĐỊNH DANH (IS-02 / TUÂN THỦ R6)
# ==========================================================================
def _ghi_phan_hoi_khong_dinh_danh(loai: str, kq: dict) -> None:
    """Ghi yêu cầu hỗ trợ / đánh giá ra data/phan_hoi.jsonl.
    Tuyệt đối KHÔNG lưu giọng nói, KHÔNG lưu câu nói gốc hay thông tin định danh (R6).
    """
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tep_log = _DATA_DIR / "phan_hoi.jsonl"
        tt = kq.get("thu_tuc")
        tuyen = kq.get("tuyen") or {}
        now = datetime.now()
        ban_ghi = {
            "thoi_gian": now.strftime("%Y-%m-%d %H:%M:%S"),
            "ngay": now.strftime("%Y-%m-%d"),
            "loai": loai,
            "ma_thu_tuc": tt.ma_thu_tuc if tt else "",
            "ten_thu_tuc": tt.ten if tt else tuyen.get("ten_nhom", "VẤN ĐỀ KHÁC"),
            "ngon_ngu": kq.get("ma_ngon_ngu", "viet"),
            "tin_cay": round(float(tuyen.get("tin_cay_thu_tuc", 0)), 2),
        }
        with tep_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ban_ghi, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ==========================================================================
# ĐIỀU HƯỚNG TRANG GIỚI THIỆU & ĐIỀU KHOẢN SỬ DỤNG
# ==========================================================================
col_sp1, col_btn_gt, col_btn_dk, col_sp2 = st.columns([1.4, 2.1, 2.2, 1.4])
with col_btn_gt:
    st.page_link("giao_dien/gioi_thieu.py", label="Giới thiệu dự án", icon="📖")
with col_btn_dk:
    st.page_link("giao_dien/dieu_khoan.py", label="Điều khoản sử dụng", icon="📜")

st.markdown("---")


# ==========================================================================
# HÀM CÓ CACHE
# ==========================================================================
@st.cache_data(ttl=3600, show_spinner=False)
def _dinh_tuyen(cau_noi: str) -> dict:
    r = dinh_tuyen(cau_noi)
    r["_key"] = r["thu_tuc"].key if r["thu_tuc"] else ""
    r.pop("thu_tuc", None)
    return r


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _don_gian_hoa(key: str, cau_hoi: str) -> dict:
    return don_gian_hoa(kb.theo_key(key), cau_hoi)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _dich_mong(text: str) -> dict:
    return dich_sang_mong(text)


PHIEN_BAN_DICH_TAY = 2


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _dich_tay(text: str, phien_ban: int = PHIEN_BAN_DICH_TAY) -> str:
    return dich_sang_tay(text)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _tts_vi(text: str) -> str:
    try:
        p = tts_tieng_viet(text)
        return str(p) if p else ""
    except Exception:
        return ""


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _audio_b64(duong_dan: str) -> tuple[str, str]:
    p = Path(duong_dan)
    if not p.exists():
        return "", ""
    mime = "audio/mpeg" if p.suffix.lower() == ".mp3" else "audio/wav"
    return base64.b64encode(p.read_bytes()).decode(), mime


_SVG_LOA = ('<svg width="38" height="38" viewBox="0 0 24 24" fill="white">'
            '<path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05'
            'c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 '
            '5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>')
_SVG_DUNG = ('<svg width="34" height="34" viewBox="0 0 24 24" fill="white">'
             '<path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>')


def nut_loa(duong_dan, *, nhan: str, tu_phat: bool = False) -> bool:
    if not duong_dan:
        return False
    b64, mime = _audio_b64(str(duong_dan))
    if not b64:
        return False

    tu_phat_js = ("a.play().then(function(){}).catch(function(){"
                  "tt.textContent='Bấm vào loa để nghe';});") if tu_phat else ""
    _html(f"""
<div style="display:flex;align-items:center;gap:16px;
            font-family:'Times New Roman',Times,serif;padding:4px 0;">
  <button id="b" aria-label="Nghe" style="
      width:76px;height:76px;min-width:76px;border-radius:50%;border:4px solid #cfe0f7;
      background:#0B4F9E;cursor:pointer;display:flex;align-items:center;
      justify-content:center;box-shadow:0 4px 14px rgba(11,79,158,.35);
      transition:transform .15s;"></button>
  <div>
    <div style="font-size:19px;font-weight:bold;color:#0B4F9E;">{nhan}</div>
    <div id="tt" style="font-size:14px;color:#666;margin-top:2px;">Bấm để nghe</div>
  </div>
  <audio id="a" src="data:{mime};base64,{b64}" preload="auto"></audio>
</div>
<script>
(function(){{
  var a=document.getElementById('a'), b=document.getElementById('b'),
      tt=document.getElementById('tt');
  var LOA=`{_SVG_LOA}`, DUNG=`{_SVG_DUNG}`;
  function ve(dangPhat){{ b.innerHTML = dangPhat ? DUNG : LOA; }}

  var ID = Math.random().toString(36).slice(2);
  var kenh = null;
  try {{ kenh = new BroadcastChannel('lgb-loa'); }} catch(e) {{}}
  if (kenh) {{
    kenh.onmessage = function(ev){{ if (ev.data !== ID && !a.paused) {{ a.pause(); }} }};
  }}
  function imCacLoaKhac(){{
    if (kenh) {{ try {{ kenh.postMessage(ID); }} catch(e) {{}} }}
    try {{
      var ds = [];
      var khung = window.parent.document.querySelectorAll('iframe');
      for (var i = 0; i < khung.length; i++) {{
        try {{
          var d = khung[i].contentDocument;
          if (d && d !== document) {{ ds = ds.concat([].slice.call(d.querySelectorAll('audio'))); }}
        }} catch(e) {{}}
      }}
      ds = ds.concat([].slice.call(window.parent.document.querySelectorAll('audio')));
      ds.forEach(function(x){{ if (x !== a && !x.paused) {{ x.pause(); }} }});
    }} catch(e) {{}}
  }}
  ve(false);
  b.onclick=function(){{ if(a.paused){{a.play();}} else {{a.pause();}} }};
  b.onmousedown=function(){{ b.style.transform='scale(.94)'; }};
  b.onmouseup=function(){{ b.style.transform='scale(1)'; }};
  a.onplay =function(){{ imCacLoaKhac(); ve(true);  tt.textContent='Đang đọc…'; }};
  a.onpause=function(){{ ve(false); tt.textContent='Bấm để nghe lại'; }};
  a.onended=function(){{ ve(false); tt.textContent='Bấm để nghe lại'; }};
  {tu_phat_js}
}})();
</script>
""", height=100)
    return True


def loa(text: str, *, nhan: str = "Nghe", tu_phat: bool = False) -> None:
    if not (text or "").strip():
        return
    p = _tts_vi(text)
    if p:
        nut_loa(p, nhan=nhan, tu_phat=tu_phat)


# ==========================================================================
# PIPELINE
# ==========================================================================
def _thong_diep_loi(e: Exception) -> str:
    if isinstance(e, LoiQuota):
        return ("Máy đang bận, bà con chờ vài phút rồi hỏi lại nhé. "
                "Hoặc chọn thủ tục ở mục **Cách khác** cuối trang.")
    s = str(e)
    if "GEMINI_API_KEY" in s:
        return "Máy chưa được cài đặt xong. Bà con báo cán bộ giúp nhé."
    if "model" in s.lower() and ("404" in s or "not_found" in s.lower()):
        return "Máy đang bảo trì. Bà con báo cán bộ giúp nhé."
    return "Máy đang bận. Bà con thử lại sau ít phút nhé."


def _them_tieng_mong(box, kq: dict, tt, *, la_tieng_chon: bool) -> None:
    box.write("Đang dịch sang tiếng Mông…")
    t = time.perf_counter()
    try:
        kq["mong"] = _dich_mong(kq["kich_ban"])
        kq["thoi_gian"]["dich_mong"] = time.perf_counter() - t

        t = time.perf_counter()
        audio, tang = phat_tieng_mong(kq["mong"]["rpa"], key=tt.key)
        kq["thoi_gian"]["tts_mong"] = time.perf_counter() - t
        kq["audio_mong"] = str(audio) if audio else ""
        kq["tang_tts"] = tang
    except Exception as e:
        if la_tieng_chon:
            kq["canh_bao"] = "Phần tiếng Mông chưa sẵn sàng, bà con nghe tạm tiếng Việt nhé."
        kq["_loi_mong"] = str(e)


def _them_tieng_tay(box, kq: dict, tt=None, *, la_tieng_chon: bool) -> None:
    box.write("Đang dịch sang tiếng Tày…")
    t = time.perf_counter()
    try:
        kq["tay"] = _dich_tay(kq["kich_ban"])
        kq["thoi_gian"]["dich_tay"] = time.perf_counter() - t
        try:
            kq["model_dich_tay"] = chon_model("quality")
        except Exception:
            pass

        t = time.perf_counter()
        audio, tang = phat_tieng_tay(kq["tay"])
        kq["thoi_gian"]["tts_tay"] = time.perf_counter() - t
        kq["audio_tay"] = str(audio) if audio else ""
        kq["tang_tts_tay"] = tang
    except Exception as e:
        if la_tieng_chon:
            kq["canh_bao"] = "Phần tiếng Tày chưa sẵn sàng, bà con nghe tạm tiếng Việt nhé."
        kq["_loi_tay"] = str(e)


_XU_LY_TIENG = {
    "mong": _them_tieng_mong,
    "tay": _them_tieng_tay,
}


def chay_pipeline(cau_noi: str, *, phat_giong_mong: bool = True,
                  ngon_ngu_chon: str = "mong",
                  cac_tieng: list[str] | None = None) -> dict:
    if cac_tieng is None:
        cac_tieng = [ngon_ngu_chon]
    t0 = time.perf_counter()
    kq: dict = {"cau_noi": cau_noi, "thoi_gian": {}}

    with st.status("Đang tìm hướng dẫn cho bà con…", expanded=False) as box:
        box.write("Đang xem bà con cần làm việc gì…")
        t = time.perf_counter()
        try:
            tuyen = _dinh_tuyen(cau_noi)
        except Exception as e:
            kq["loi"] = _thong_diep_loi(e)
            box.update(label="Chưa xong", state="error", expanded=False)
            return kq
        kq["thoi_gian"]["dinh_tuyen"] = time.perf_counter() - t
        kq["tuyen"] = tuyen
        tt = kb.theo_key(tuyen["_key"]) if tuyen["_key"] else None
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

        box.write("Đang chuẩn bị giọng đọc…")
        kq["audio_viet"] = _tts_vi(kq["kich_ban"])

        if phat_giong_mong:
            for ma in cac_tieng:
                xu_ly = _XU_LY_TIENG.get(ma)
                if xu_ly:
                    xu_ly(box, kq, tt, la_tieng_chon=(ma == ngon_ngu_chon))

        kq["thoi_gian"]["tong"] = time.perf_counter() - t0
        box.update(label="Đã có hướng dẫn cho bà con", state="complete", expanded=False)
    return kq


def xu_ly_cau_noi(van_ban: str) -> None:
    ss.cau_noi = van_ban
    ma = ss.get("ma_ngon_ngu", "mong")
    cac = list(ss.get("cac_ngon_ngu") or [ma])
    kq = chay_pipeline(van_ban, ngon_ngu_chon=ma, cac_tieng=cac)
    kq["la_tieng_mong"] = ma == "mong"
    kq["ma_ngon_ngu"] = ma
    kq["cac_ngon_ngu"] = cac
    ss.ket_qua = kq


# ==========================================================================
# 1. CHỌN TIẾNG
# ==========================================================================
_DS_TIENG = NN.dang_dung()
_MA_THEO_NHAN = {n.nhan: n.ma for n in _DS_TIENG}
_MAC_DINH = [n.nhan for n in _DS_TIENG if n.ma in NN.MAC_DINH] or [_DS_TIENG[0].nhan]

st.html("""<style>
  .st-key-lgb-chon-tieng { max-width: 560px; margin: 0 auto; }
  .st-key-lgb-chon-tieng label p { font-size: 18px !important; font-weight: bold !important;
                                   color: #003366 !important; text-align: center; }
  .st-key-lgb-chon-tieng [data-baseweb="select"] > div { min-height: 52px; font-size: 18px; }
  .st-key-lgb-chon-tieng [data-baseweb="tag"] { font-size: 17px !important; height: auto !important;
                                               padding: 6px 10px !important; }
</style>""")
try:
    _khung_chon = st.container(key="lgb-chon-tieng")
except TypeError:
