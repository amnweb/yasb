"""Windows PE icon extractor."""

import ctypes
import io
import struct
from ctypes.wintypes import LPCWSTR

from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.constants import LOAD_LIBRARY_AS_DATAFILE, LOAD_LIBRARY_AS_IMAGE_RESOURCE, RT_GROUP_ICON, RT_ICON

_H = struct.Struct("<H")
_HH = struct.Struct("<HH")
_I = struct.Struct("<I")
_II = struct.Struct("<II")
_IIII = struct.Struct("<IIII")
_HHH = struct.Struct("<HHH")
_HIGH_BIT = 0x80000000


def _mir(n: int) -> LPCWSTR:
    return ctypes.cast(ctypes.c_void_p(n & 0xFFFF), LPCWSTR)


_MIR_ICON = _mir(RT_ICON)
_MIR_GROUP = _mir(RT_GROUP_ICON)


def _enumerate_group_icons(filename: str) -> list[int | str]:
    """Parse PE resource directory to collect RT_GROUP_ICON names."""
    try:
        f = open(filename, "rb")
    except OSError:
        return []
    try:
        dos = f.read(0x40)
        if len(dos) < 0x40 or dos[:2] != b"MZ":
            return []
        f.seek(_I.unpack_from(dos, 0x3C)[0])
        coff = f.read(24)
        if len(coff) < 24 or coff[:4] != b"PE\x00\x00":
            return []
        num_sec = _H.unpack_from(coff, 6)[0]
        opt_sz = _H.unpack_from(coff, 20)[0]
        opt = f.read(opt_sz)
        if len(opt) < opt_sz:
            return []
        dd_off = (112 if _H.unpack_from(opt, 0)[0] == 0x20B else 96) + 16
        if dd_off + 8 > len(opt):
            return []
        res_rva = _I.unpack_from(opt, dd_off)[0]
        if not res_rva:
            return []
        sec_tbl = f.read(num_sec * 40)
        for i in range(num_sec):
            o = i * 40
            if o + 40 > len(sec_tbl):
                break
            vs, va, rs, rp = _IIII.unpack_from(sec_tbl, o + 8)
            span = max(vs, rs)
            if va <= res_rva < va + span:
                f.seek(rp)
                rsrc = f.read(span)
                base = res_rva - va
                break
        else:
            return []
    finally:
        f.close()

    n = len(rsrc)
    if base + 16 > n:
        return []
    # Find RT_GROUP_ICON type entry
    pos = base + 16
    grp_off = -1
    for _ in range(sum(_HH.unpack_from(rsrc, base + 12))):
        if pos + 8 > n:
            break
        nid, dref = _II.unpack_from(rsrc, pos)
        pos += 8
        if not (nid & _HIGH_BIT) and (nid & 0xFFFF) == RT_GROUP_ICON and (dref & _HIGH_BIT):
            grp_off = dref & 0x7FFFFFFF
            break
    if grp_off < 0 or grp_off + 16 > n:
        return []
    # Collect icon name entries
    pos = grp_off + 16
    names: list[int | str] = []
    for _ in range(sum(_HH.unpack_from(rsrc, grp_off + 12))):
        if pos + 8 > n:
            break
        nid, _ = _II.unpack_from(rsrc, pos)
        pos += 8
        if nid & _HIGH_BIT:
            so = nid & 0x7FFFFFFF
            if so + 2 <= n:
                cl = _H.unpack_from(rsrc, so)[0]
                names.append(rsrc[so + 2 : so + 2 + cl * 2].decode("utf-16-le", errors="replace"))
        else:
            names.append(nid & 0xFFFF)
    return names


def _load_resource(hmod: int, name, res_type) -> bytes:
    hrsrc = kernel32.FindResourceW(hmod, name, res_type)
    if not hrsrc:
        raise OSError(f"FindResourceW failed (err={kernel32.GetLastError()})")
    size = kernel32.SizeofResource(hmod, hrsrc)
    hglob = kernel32.LoadResource(hmod, hrsrc)
    if not hglob:
        raise OSError(f"LoadResource failed (err={kernel32.GetLastError()})")
    ptr = kernel32.LockResource(hglob)
    if not ptr:
        raise OSError(f"LockResource failed (err={kernel32.GetLastError()})")
    return (ctypes.c_char * size).from_address(ptr).raw


class IconExtractor:
    """Extract icons from Windows PE files (.exe/.dll/.mun)."""

    def __init__(self, filename: str):
        self._hmod = kernel32.LoadLibraryExW(filename, None, LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE)
        if not self._hmod:
            raise OSError(f"Cannot load '{filename}' (err={kernel32.GetLastError()})")
        self._names: list[int | str] = _enumerate_group_icons(filename)
        if not self._names:
            kernel32.FreeLibrary(self._hmod)
            self._hmod = 0
            raise OSError(f"'{filename}' has no group icon resources")

    def __del__(self):
        if self._hmod:
            kernel32.FreeLibrary(self._hmod)
            self._hmod = 0

    def list_group_icons(self) -> list[int | str]:
        return list(self._names)

    def _build_ico(self, index: int = 0) -> bytes:
        if index >= len(self._names):
            raise IndexError(f"Icon index {index} out of range (file has {len(self._names)})")
        name = self._names[index]
        grp = _load_resource(self._hmod, _mir(name) if isinstance(name, int) else name, _MIR_GROUP)
        count = _H.unpack_from(grp, 4)[0]
        headers: list[bytes] = []
        images: list[bytes] = []
        off = 6
        for _ in range(count):
            entry = grp[off : off + 14]
            images.append(_load_resource(self._hmod, _mir(_H.unpack_from(entry, 12)[0]), _MIR_ICON))
            headers.append(entry[:12])
            off += 14
        parts: list[bytes] = [_HHH.pack(0, 1, len(headers))]
        data_off = 6 + len(headers) * 16
        for hdr, img in zip(headers, images):
            parts.append(hdr)
            parts.append(_I.pack(data_off))
            data_off += len(img)
        parts.extend(images)
        return b"".join(parts)

    def get_icon(self, num: int = 0, resource_id=None) -> io.BytesIO:
        return io.BytesIO(self._build_ico(num))

    def export_icon(self, filename: str, num: int = 0) -> None:
        with open(filename, "wb") as f:
            f.write(self._build_ico(num))
