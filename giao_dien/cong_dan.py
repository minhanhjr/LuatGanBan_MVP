# -*- coding: utf-8 -*-
"""Cổng người dân — hỏi đáp thủ tục bằng giọng nói.

Nguyên tắc giao diện (voice-first):

  * MỘT nút. Bà con bấm micro, nói, bấm dừng — hệ thống tự chạy hết chuỗi,
    không có nút "xử lý" thứ hai.
  * Không hiện con số kỹ thuật. Bà con không cần biết "độ tin cậy 10%";
    họ chỉ cần biết máy nghe rõ hay chưa. Mọi chỉ số dời vào mục dành cho
    cán bộ ở cuối trang.
  * Chữ nào cũng có loa. Người không đọc được vẫn phải dùng được trọn vẹn,
    nên mọi nội dung trả lời đều kèm trình phát tiếng.
  * Gõ chữ là đường phụ, đặt cuối trang, cỡ nhỏ.
"""
from __future__ import annotations

import base64
import hashlib
import time
from datetime import datetime
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import html as _html

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

ss = st.session_state
ss.setdefault("danh_sach_yeu_cau", [])
ss.setdefault("ket_qua", None)
ss.setdefault("cau_noi", "")
ss.setdefault("audio_da_xu_ly", "")

if not kb.load_kb():
    st.error(
        "**Kho dữ liệu trống.** Hãy chạy một lần:  `python tools/extract_tthc.py`\n\n"
        "Lệnh này bóc 28 file PDF hướng dẫn đang bị nhúng bên trong 3 file Excel "
        "ở `file_dichvucong/` ra thành `data/tthc/` + `data/manifest.json`."
    )
    st.stop()


# ==========================================================================
# ĐIỀU HƯỚNG TRANG GIỚI THIỆU (Nút bấm tinh tế, gọn nhẹ)
# ==========================================================================
col_sp1, col_btn_gt, col_sp2 = st.columns([3, 1.4, 3])
with col_btn_gt:
    if st.button("📖 Giới thiệu dự án", use_container_width=True, help="Xem thông tin chi tiết và ý nghĩa dự án"):
        st.switch_page("giao_dien/gioi_thieu.py")

st.markdown("---")


# ==========================================================================
# HÀM CÓ CACHE (giảm độ trễ: lần 2 trở đi gần như tức thì)
# ==========================================================================
@st.cache_data(ttl=3600, show_spinner=False)
def _dinh_tuyen(cau_noi: str) -> dict:
    r = dinh_tuyen(cau_noi)
    r["_key"] = r["thu_tuc"].key if r["thu_tuc"] else ""    # ThuTuc không hash được
    r.pop("thu_tuc", None)
    return r


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _don_gian_hoa(key: str, cau_hoi: str) -> dict:
    return don_gian_hoa(kb.theo_key(key), cau_hoi)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _dich_mong(text: str) -> dict:
    return dich_sang_mong(text)


PHIEN_BAN_DICH_TAY = 2          # tăng số này khi đổi cách dịch -> bỏ cache cũ


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _dich_tay(text: str, phien_ban: int = PHIEN_BAN_DICH_TAY) -> str:
    return dich_sang_tay(text)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _tts_vi(text: str) -> str:
    """Đọc một đoạn chữ bằng giọng Việt. Trả về đường dẫn file, "" nếu hỏng."""
    try:
        p = tts_tieng_viet(text)
        return str(p) if p else ""
    except Exception:
        return ""


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _audio_b64(duong_dan: str) -> tuple[str, str]:
    """Đọc file âm thanh thành base64 để nhúng thẳng vào nút loa."""
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
    """Nút loa tròn, màu xanh dương, bấm một cái là nghe."""
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

  // Chỉ một loa được phát tại một thời điểm: loa này bắt đầu đọc thì
  // các loa khác (Việt / Mông / Tày) phải im.
  var ID = Math.random().toString(36).slice(2);
  var kenh = null;
  try {{ kenh = new BroadcastChannel('lgb-loa'); }} catch(e) {{}}
  if (kenh) {{
    kenh.onmessage = function(ev){{ if (ev.data !== ID && !a.paused) {{ a.pause(); }} }};
  }}
  function imCacLoaKhac(){{
    if (kenh) {{ try {{ kenh.postMessage(ID); }} catch(e) {{}} }}
    // Dự phòng khi trình duyệt không có BroadcastChannel: dừng trực tiếp
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
    """Đọc một đoạn chữ bằng giọng Việt rồi hiện nút loa."""
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


# Mỗi tiếng dân tộc một hàm: dịch bản tiếng Việt rồi tạo file đọc.
# Thêm tiếng mới: viết hàm _them_tieng_xxx cùng kiểu rồi đăng ký ở đây
# (và thêm vào core/ngon_ngu.py).
_XU_LY_TIENG = {
    "mong": _them_tieng_mong,
    "tay": _them_tieng_tay,
}


def chay_pipeline(cau_noi: str, *, phat_giong_mong: bool = True,
                  ngon_ngu_chon: str = "mong",
                  cac_tieng: list[str] | None = None) -> dict:
    """cac_tieng: các tiếng bà con muốn nghe, theo thứ tự đã chọn.
    ngon_ngu_chon: tiếng bà con nói (tiếng đầu tiên) — được báo lỗi nếu hỏng.
    Tiếng Việt luôn có vì là bản gốc, không tốn thêm lượt dịch."""
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
            for ma in cac_tieng:                  # chỉ dịch những tiếng đã chọn
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
except TypeError:                          # Streamlit cũ chưa có tham số key
    _khung_chon = st.container()

chon = _khung_chon.multiselect(
    "Bà con nghe bằng tiếng gì? (chọn được nhiều tiếng)",
    options=list(_MA_THEO_NHAN),
    default=_MAC_DINH,
    key="chon_ngon_ngu",
    placeholder="Bấm vào đây để chọn tiếng",
    help="Tiếng chọn đầu tiên là tiếng bà con nói. Các tiếng sau để nghe thêm.",
)
if not chon:
    _khung_chon.caption("Chưa chọn tiếng nào, máy sẽ dùng tiếng Việt.")

cac_ngon_ngu = [_MA_THEO_NHAN[x] for x in chon] or [NN.MA_TIENG_VIET]
ma_ngon_ngu = cac_ngon_ngu[0]              # tiếng đầu tiên = tiếng bà con nói
la_tieng_mong = ma_ngon_ngu == "mong"
ss.la_tieng_mong = la_tieng_mong
ss.ma_ngon_ngu = ma_ngon_ngu
ss.cac_ngon_ngu = cac_ngon_ngu

# ==========================================================================
# 2. MỘT NÚT DUY NHẤT (ĐÃ SỬA NGƯỠNG ĐỂ NHẬN DIỆN MƯỢT MÀ CÂU NÓI NGẮN)
# ==========================================================================
st.markdown(
    '<div style="text-align:center;font-size:26px;font-weight:bold;'
    'color:#003366;margin:10px 0 2px 0;">Bấm vào đây để nói</div>',
    unsafe_allow_html=True,
)

audio_in = st.audio_input("Bấm micro để nói", label_visibility="collapsed")

if audio_in is not None:
    raw = audio_in.getvalue()
    van_tay = hashlib.sha256(raw).hexdigest()[:16]
    # Hạ ngưỡng từ 2000 xuống 50 bytes để xử lý ngay cả câu nói ngắn gọn nhất
    if van_tay != ss.audio_da_xu_ly and len(raw) > 50:
        ss.audio_da_xu_ly = van_tay
        with st.spinner("Đang nghe bà con nói…"):
            van_ban, _nguon = nghe(audio_in, tieng_mong=la_tieng_mong,
                                   ngon_ngu=ma_ngon_ngu)
        if not van_ban:
            st.error("Máy chưa nghe rõ, bà con bấm nói lại nhé.")
            loa("Máy chưa nghe rõ, bà con bấm nói lại nhé.",
                nhan="Nghe lại lời nhắc", tu_phat=True)
        else:
            if ma_ngon_ngu in ("mong", "tay"):
                dong_vi = [l for l in van_ban.splitlines() if l.startswith("VI:")]
                if dong_vi:
                    van_ban = dong_vi[0][3:].strip()
                elif ma_ngon_ngu == "tay":
                    van_ban = dich_tay_sang_viet(van_ban)
                else:
                    van_ban = dich_sang_viet(van_ban)
            st.success(f"Bà con nói: *{van_ban}*")
            xu_ly_cau_noi(van_ban)
    elif 0 < len(raw) <= 50:
        st.warning("Bà con bấm micro rồi nói rõ hơn một chút nhé.")


# ==========================================================================
# 3. KẾT QUẢ
# ==========================================================================
def nut_goi_can_bo(kq: dict) -> None:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🙋 CẦN CÁN BỘ HỖ TRỢ TRỰC TIẾP", use_container_width=True):
        tt = kq.get("thu_tuc")
        ss.danh_sach_yeu_cau.append({
            "thoi_gian": datetime.now().strftime("%d/%m %H:%M:%S"),
            "van_de": tt.ten if tt else kq["tuyen"]["ten_nhom"],
            "ma": tt.ma_thu_tuc if tt else "",
            "chi_tiet": kq["cau_noi"],
            "tin_cay": kq["tuyen"].get("tin_cay_thu_tuc", 0),
            "trang_thai": "Mới",
        })
        st.success("✅ Đã gửi. Cán bộ sẽ liên hệ với bà con.")


def hien_ket_qua(kq: dict) -> None:
    if kq.get("loi"):
        st.error(kq["loi"])
        loa(kq["loi"], nhan="Nghe lời nhắc", tu_phat=True)
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
            f'❓ {cau_hoi}</div>',
            unsafe_allow_html=True,
        )
        loa(cau_hoi, nhan="Nghe câu hỏi", tu_phat=True)
        st.caption("Bà con bấm micro ở trên để nói lại, hoặc bấm nút dưới để gặp cán bộ.")
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

    # Mỗi tiếng đã chọn một nút loa, theo đúng thứ tự bà con chọn.
    # Tiếng đầu tiên tự phát; tiếng Việt luôn có ở cuối làm bản gốc.
    ma_chon = kq.get("ma_ngon_ngu") or ("mong" if kq.get("la_tieng_mong", True) else "viet")
    cac_ma = list(kq.get("cac_ngon_ngu") or [ma_chon])
    if NN.MA_TIENG_VIET not in cac_ma:
        cac_ma.append(NN.MA_TIENG_VIET)

    def _ghi_chu(ma: str) -> str:
        if ma == "mong" and kq.get("tang_tts") == "vi_phonetic":
            return "Giọng máy đọc tiếng dân tộc thiểu số."
        if ma == "tay":
            return "Giọng máy đọc tiếng dân tộc thiểu số."
        return ""

    cac_loa = []
    for ma in cac_ma:
        nn = NN.theo_ma(ma)
        duong_dan = kq.get(f"audio_{ma}", "")
        if ma != NN.MA_TIENG_VIET and not duong_dan:
            continue                     # tiếng này dịch/đọc hỏng -> không hiện nút
        ten = nn.ten if nn else ma
        cac_loa.append((ma, duong_dan, f"Nghe bằng {ten[:1].lower()}{ten[1:]}",
                        _ghi_chu(ma)))

    co_tieng_chon = any(ma == ma_chon for ma, *_ in cac_loa)
    tieng_tu_phat = ma_chon if co_tieng_chon else "viet"  # tiếng chọn hỏng -> phát tiếng Việt

    for ma, duong_dan, nhan, ghi_chu in cac_loa:
        if ma == "viet" and not duong_dan:
            loa(kq.get("kich_ban", ""), nhan=nhan, tu_phat=(ma == tieng_tu_phat))
        else:
            nut_loa(duong_dan, nhan=nhan, tu_phat=(ma == tieng_tu_phat))
        if ghi_chu:
            st.caption(ghi_chu)

    if kq.get("tay"):
        with st.expander("📖 Xem chữ tiếng Tày"):
            st.caption("chữ Tày–Nùng hệ Latinh · bản dịch máy, chưa được duyệt")
            st.markdown(f"### {kq['tay']}")

    if kq.get("mong"):
        with st.expander("📖 Xem chữ tiếng Mông"):
            nhan_ortho = ("chữ Mông kiểu Việt Nam" if HMONG_ORTHOGRAPHY == "vn"
                          else "chữ Mông RPA")
            st.caption(nhan_ortho)
            st.markdown(f"### {kq['mong']['hien_thi']}")
            st.text(f"RPA        : {kq['mong']['rpa']}")
            st.text(f"Phiên âm VN: {kq['mong']['vn']}")

    la_can_bo = bool(auth.nguoi_dang_nhap())

    with st.expander("⚖️ Căn cứ pháp lý & đối chiếu tài liệu gốc"):
        st.caption(f"Mã thủ tục {tt.ma_thu_tuc} · cấp {tt.cap_thuc_hien}")
        if la_can_bo:
            cot1, cot2 = st.columns(2)
            cot1.metric("Độ tin cậy bản tóm tắt", f"{dg.get('do_tin_cay', 0):.0%}")
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
        if kbb:
            st.markdown("**Giấy tờ không bắt buộc:** "
                        + ", ".join(m["ten_don_gian"] for m in kbb))
        if tt.pdf_path.exists():
            st.download_button("⬇️ Tải file hướng dẫn gốc (PDF)",
                               tt.pdf_path.read_bytes(),
                               file_name=f"{tt.ma_thu_tuc}.pdf", mime="application/pdf")
        if la_can_bo:
            tg = kq.get("thoi_gian", {})
            st.caption("Thời gian xử lý: "
                       + "  ·  ".join(f"{k} {v:.1f}s" for k, v in tg.items()))

    nut_goi_can_bo(kq)


if ss.ket_qua:
    st.write("---")
    hien_ket_qua(ss.ket_qua)


# ==========================================================================
# 4. ĐƯỜNG PHỤ — gõ chữ / chọn danh sách
# ==========================================================================
st.markdown('<div class="lgb-phu">', unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

with st.expander("⌨️ Không nói được? Gõ chữ hoặc chọn từ danh sách"):
    t_go, t_chon = st.tabs(["Gõ câu hỏi", "Chọn thủ tục"])

    with t_go:
        with st.form("form_go", clear_on_submit=False):
            txt = st.text_area(
                "Bà con cần hỏi việc gì?",
                placeholder="Ví dụ: Vợ tôi mới sinh con, tôi muốn làm giấy khai sinh",
                height=90)
            if st.form_submit_button("Gửi câu hỏi", type="primary",
                                       use_container_width=True) and txt.strip():
                xu_ly_cau_noi(txt.strip())
                st.rerun()

    with t_chon:
        st.caption("Chọn trực tiếp — trả lời ngay, dùng khi phòng ồn hoặc mạng yếu.")
        nhom_chon = st.selectbox("Việc gì?", list(DANH_MUC_THU_TUC.keys()),
                                 format_func=lambda k: DANH_MUC_THU_TUC[k])
        ds = kb.theo_nhom(nhom_chon)
        if not ds:
            st.warning("Chưa có dữ liệu cho nhóm này.")
        else:
            tt_chon = st.selectbox("Thủ tục cụ thể", ds, format_func=lambda t: t.ten)
            if st.button("Xem hướng dẫn", type="primary", use_container_width=True):
                xu_ly_cau_noi(tt_chon.ten)
                st.rerun()

st.markdown('</div>', unsafe_allow_html=True)


# ==========================================================================
# 5. THANH BÊN — chỉ dành cho cán bộ
# ==========================================================================
if auth.nguoi_dang_nhap():
    with st.sidebar:
        st.divider()
        st.markdown("### Trạng thái hệ thống")
        tk = kb.thong_ke()
        st.metric("Thủ tục trong kho", tk["so_thu_tuc"])
        st.caption(f"Nhóm có dữ liệu: {tk['so_nhom']}  ·  "
                   f"{tk['tong_ky_tu']:,} ký tự văn bản gốc")
        st.caption(f"Giọng Mông: `{TTS_HMONG_PROVIDER}`  ·  "
                   f"Ngưỡng tin cậy: {NGUONG_TU_TIN:.0%}")
        if tk["thieu_pdf"]:
            st.error(f"Thiếu PDF: {', '.join(tk['thieu_pdf'][:5])}")
        if ss.danh_sach_yeu_cau:
            st.markdown("### Phiếu chờ cán bộ")
            for p in reversed(ss.danh_sach_yeu_cau[-5:]):
                st.caption(f"{p['thoi_gian']} — {p['van_de']}")
