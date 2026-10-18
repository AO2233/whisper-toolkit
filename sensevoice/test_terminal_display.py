import io
import os
import unittest
from unittest.mock import patch

from terminal_display import TerminalDisplay, _preview


class TerminalStream(io.StringIO):
    def isatty(self):
        return True


class TerminalDisplayTests(unittest.TestCase):
    def make_display(self, ansi=True):
        stream = TerminalStream()
        with patch("terminal_display._enable_ansi", return_value=ansi):
            display = TerminalDisplay(stream)
        return display, stream

    def test_live_updates_do_not_clear_screen_or_reprint_history(self):
        display, stream = self.make_display()
        with patch("os.system", side_effect=AssertionError("must not clear the console")):
            display.finalize("[2026-10-18 18:04:44] 第一句。")
            display.update("正在识别很长的一句话")
            display.update("较短")
            display.finalize("[2026-10-18 18:04:46] 第二句。")
        output = stream.getvalue()
        self.assertEqual(output.count("第一句。"), 1)
        self.assertIn("\r\x1b[2K", output)
        self.assertNotIn("\x1b[2J", output)
        self.assertNotIn("1. ", output)
        self.assertTrue(output.endswith("[2026-10-18 18:04:46] 第二句。\n"))

    def test_identical_preview_is_not_redrawn(self):
        display, stream = self.make_display()
        display.update("相同内容")
        before = stream.getvalue()
        display.update("相同内容")
        self.assertEqual(stream.getvalue(), before)

    def test_preview_stays_on_one_line_with_wide_characters(self):
        preview, width = _preview("最初的文本\n中文abc", 8)
        self.assertEqual(preview, "中文abc")
        self.assertEqual(width, 7)
        display, stream = self.make_display()
        with patch("terminal_display.shutil.get_terminal_size", return_value=os.terminal_size((8, 24))):
            display.update("最初的文本\n中文abc")
        self.assertEqual(stream.getvalue(), "\x1b[90m中文abc\x1b[0m")

    def test_redirected_output_contains_only_final_text(self):
        stream = io.StringIO()
        display = TerminalDisplay(stream)
        display.update("临时识别")
        display.finalize("[18:04:44] 最终正文。")
        display.close()
        self.assertEqual(stream.getvalue(), "[18:04:44] 最终正文。\n")

    def test_plain_console_clears_shorter_preview(self):
        display, stream = self.make_display(ansi=False)
        display.update("中文abc")
        display.update("短")
        display.close()
        self.assertEqual(stream.getvalue(), "中文abc\r       \r短\r  \r")

    def test_rejected_noise_clears_preview_without_blank_line(self):
        display, stream = self.make_display()
        display.update("噪声")
        display.finalize("")
        before = stream.getvalue()
        display.close()
        self.assertEqual(stream.getvalue(), before)
        self.assertTrue(before.endswith("\r\x1b[2K"))
        self.assertNotIn("\n", before)


if __name__ == "__main__":
    unittest.main()
