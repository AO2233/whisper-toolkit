"""Append finalized text and refresh only one terminal line while recognizing."""
import os
import shutil
import sys
import unicodedata


def _enable_ansi(stream):
    if os.name != "nt":
        return True
    try:
        import ctypes
        import msvcrt

        handle = ctypes.c_void_p(msvcrt.get_osfhandle(stream.fileno()))
        mode = ctypes.c_ulong()
        kernel = ctypes.windll.kernel32
        return bool(kernel.GetConsoleMode(handle, ctypes.byref(mode))
                    and kernel.SetConsoleMode(handle, mode.value | 0x0004))
    except (AttributeError, OSError, ValueError):
        return False


def _cell_width(char):
    if unicodedata.combining(char):
        return 0
    return 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1


def _preview(text, columns):
    # Keep the live preview on one physical line, including Chinese/Japanese text.
    # Leave the last column free so automatic wrapping cannot move the cursor.
    chars = []
    width = 0
    for char in reversed(" ".join(text.split())):
        size = _cell_width(char)
        if width + size > max(0, columns - 1):
            break
        chars.append(char)
        width += size
    return "".join(reversed(chars)), width


class TerminalDisplay:
    def __init__(self, stream=None):
        self.stream = sys.stdout if stream is None else stream
        self.interactive = self.stream.isatty()
        self.ansi = self.interactive and _enable_ansi(self.stream)
        self.current = ""
        self.width = 0

    def _erase(self):
        if not self.current:
            return ""
        if self.ansi:
            return "\r\x1b[2K"
        return "\r" + " " * self.width + "\r"

    def update(self, text):
        if not self.interactive:
            return
        preview, width = _preview(text, shutil.get_terminal_size().columns)
        if preview == self.current:
            return
        output = self._erase()
        if preview:
            output += f"\x1b[90m{preview}\x1b[0m" if self.ansi else preview
        self.stream.write(output)
        self.stream.flush()
        self.current, self.width = preview, width

    def finalize(self, text):
        output = self._erase()
        if text:
            output += text + "\n"
        if output:
            self.stream.write(output)
            self.stream.flush()
        self.current, self.width = "", 0

    def close(self):
        self.finalize("")
