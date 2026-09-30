"""Names of fonts available to the caption renderer and uploaded font files."""
import ctypes
import platform
import shutil
import subprocess
from pathlib import Path


def system_font_families():
    if platform.system() == 'Darwin':
        core_text = ctypes.CDLL('/System/Library/Frameworks/CoreText.framework/CoreText')
        core_foundation = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        core_text.CTFontManagerCopyAvailableFontFamilyNames.restype = ctypes.c_void_p
        core_foundation.CFArrayGetCount.argtypes = [ctypes.c_void_p]
        core_foundation.CFArrayGetCount.restype = ctypes.c_long
        core_foundation.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
        core_foundation.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
        core_foundation.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long, ctypes.c_uint32]
        core_foundation.CFStringGetCString.restype = ctypes.c_bool
        core_foundation.CFRelease.argtypes = [ctypes.c_void_p]
        families = core_text.CTFontManagerCopyAvailableFontFamilyNames()
        if not families:
            return []
        try:
            result = []
            for index in range(core_foundation.CFArrayGetCount(families)):
                buffer = ctypes.create_string_buffer(1024)
                string = core_foundation.CFArrayGetValueAtIndex(families, index)
                if core_foundation.CFStringGetCString(string, buffer, len(buffer), 0x08000100):
                    result.append(buffer.value.decode('utf-8'))
            return sorted(set(result), key=str.casefold)
        finally:
            core_foundation.CFRelease(families)
    if shutil.which('fc-list'):
        output = subprocess.run(['fc-list', '-f', '%{family}\n'], capture_output=True,
                                text=True, timeout=10, check=True).stdout
        return sorted({name.strip() for line in output.splitlines()
                       for name in line.split(',') if name.strip()}, key=str.casefold)
    return []


def font_family_from_file(path):
    """Read the SFNT name table from a TTF/OTF without an extra dependency."""
    data = Path(path).read_bytes()
    if len(data) < 12 or data[:4] not in (b'\x00\x01\x00\x00', b'OTTO', b'true'):
        return None
    tables = int.from_bytes(data[4:6], 'big')
    for index in range(min(tables, 256)):
        entry = 12 + 16 * index
        if entry + 16 > len(data):
            break
        if data[entry:entry + 4] != b'name':
            continue
        start = int.from_bytes(data[entry + 8:entry + 12], 'big')
        length = int.from_bytes(data[entry + 12:entry + 16], 'big')
        if start + length > len(data) or length < 6:
            break
        count = int.from_bytes(data[start + 2:start + 4], 'big')
        strings = start + int.from_bytes(data[start + 4:start + 6], 'big')
        names = []
        for item in range(min(count, 4096)):
            offset = start + 6 + 12 * item
            if offset + 12 > start + length:
                break
            platform_id = int.from_bytes(data[offset:offset + 2], 'big')
            name_id = int.from_bytes(data[offset + 6:offset + 8], 'big')
            size = int.from_bytes(data[offset + 8:offset + 10], 'big')
            pos = strings + int.from_bytes(data[offset + 10:offset + 12], 'big')
            if name_id not in (1, 16) or pos + size > start + length:
                continue
            try:
                family = data[pos:pos + size].decode('utf-16-be' if platform_id in (0, 3) else 'mac_roman').strip()
            except UnicodeError:
                continue
            if family:
                names.append((name_id == 16, platform_id in (0, 3), family))
        return max(names)[2] if names else None
    return None
