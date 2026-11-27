"""Phát âm thanh qua URL, ưu tiên Opus và giữ định dạng dự phòng."""
from __future__ import annotations

import hashlib
import os
import subprocess
from html import escape
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import BoundedSemaphore

import streamlit as st
from streamlit import runtime

from core.config import CACHE_AUDIO

_KHOA_NEN = BoundedSemaphore()
_GIOI_HAN_NEN_GIAY = 15
_MIME = {
    ".ogg": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".webm": "audio/webm",
}
_LENH_NEN = {
    ".ogg": ("-c:a", "libopus", "-b:a", "24k", "-vbr", "constrained", "-application", "voip"),
    ".mp3": ("-c:a", "libmp3lame", "-b:a", "40k"),
}


def _tep_co_du_lieu(tep: Path) -> bool:
    return tep.is_file() and tep.stat().st_size > 0


def _ban_nen(goc: Path, duoi: str) -> Path | None:
    """Tái sử dụng bản thu đã nén hoặc nén một lần và lưu vào cache."""
    if goc.suffix.lower() == duoi:
        return goc
    thong_tin = goc.stat()
    ma = hashlib.sha256(
        f"{goc.resolve()}:{thong_tin.st_mtime_ns}:{thong_tin.st_size}:{_LENH_NEN[duoi]}".encode()
    ).hexdigest()[:24]
    dich = CACHE_AUDIO / f"web_{ma}{duoi}"
    if _tep_co_du_lieu(dich):
        return dich
    # Giới hạn một tiến trình nén trong mỗi worker. Khi bận vẫn phát bản gốc.
    if not _KHOA_NEN.acquire(blocking=False):
        return None
    tam = None
    try:
        if _tep_co_du_lieu(dich):
            return dich
        from imageio_ffmpeg import get_ffmpeg_exe

        with NamedTemporaryFile(dir=dich.parent, suffix=duoi, delete=False) as f:
            tam = Path(f.name)
        subprocess.run(
            [get_ffmpeg_exe(), "-nostdin", "-loglevel", "error", "-y",
             "-i", str(goc), "-map", "0:a:0", "-ac", "1", "-ar", "48000",
             *_LENH_NEN[duoi], str(tam)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=_GIOI_HAN_NEN_GIAY, check=True,
        )
        if _tep_co_du_lieu(tam):
            os.replace(tam, dich)
            return dich
    except (ImportError, OSError, RuntimeError, subprocess.SubprocessError):
        return None
    finally:
        _KHOA_NEN.release()
        if tam:
            tam.unlink(missing_ok=True)
    return None


def phat_am_thanh(
    duong_dan: str | Path | None,
    *,
    key: str,
    tu_phat: bool = False,
    opus: Path | None = None,
    mp3: Path | None = None,
) -> bool:
    """Đăng ký tệp với Streamlit rồi đưa các nguồn âm thanh cho trình duyệt."""
    if not duong_dan:
        return False
    goc = Path(duong_dan)
    if not _tep_co_du_lieu(goc):
        return False

    ban_nhe = opus if opus and _tep_co_du_lieu(opus) else _ban_nen(goc, ".ogg")
    du_phong = mp3 if mp3 and _tep_co_du_lieu(mp3) else _ban_nen(goc, ".mp3")
    cac_tep = list(dict.fromkeys(tep for tep in (ban_nhe, du_phong or goc) if tep))

    if not runtime.exists():
        return False
    kho = runtime.get_instance().media_file_mgr
    cac_nguon = []
    for tep in cac_tep:
        mime = _MIME.get(tep.suffix.lower(), "audio/mpeg")
        url = kho.add(str(tep), mime, f"audio:{key}:{mime}")
        # Streamlit lấy đường dẫn media tương đối theo baseUrlPath.
        base = st.get_option("server.baseUrlPath").strip("/")
        if base and url.startswith("/media/"):
            url = f"/{base}{url}"
        loai = f'{mime}; codecs="opus"' if mime == "audio/ogg" else mime
        cac_nguon.append(f'<source src="{escape(url)}" type="{escape(loai)}">')

    autoplay = " autoplay" if tu_phat else ""
    st.html(
        f'<audio controls preload="none"{autoplay} style="width:100%">'
        f'{"".join(cac_nguon)}'
        "Trình duyệt chưa phát được âm thanh này."
        "</audio>"
    )
    return True
