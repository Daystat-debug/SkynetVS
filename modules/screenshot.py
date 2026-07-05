# modules/screenshot.py

from __future__ import annotations

import subprocess
import textwrap
from datetime import datetime
from pathlib import Path


class ScreenshotService:
    """
    Создание скриншота на Windows через PowerShell/.NET без внешних Python-зависимостей.
    Сохраняет PNG в указанную директорию и возвращает путь к файлу.
    """

    def __init__(self, output_dir: str = "data/screenshots"):
        self._output_dir = Path(output_dir)

    def make_screenshot(self) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = (self._output_dir / f"screenshot_{ts}.png").resolve()

        p = str(out_path).replace("'", "''")

        ps_script = textwrap.dedent(rf"""
                Add-Type -AssemblyName System.Windows.Forms
                Add-Type -AssemblyName System.Drawing
                Add-Type @"
        using System;
        using System.Runtime.InteropServices;
        public static class DpiHelper {{
            [DllImport("user32.dll")]
            public static extern bool SetProcessDPIAware();
        }}
        "@

                [DpiHelper]::SetProcessDPIAware() | Out-Null

                $bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
                $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
                $g = [System.Drawing.Graphics]::FromImage($bmp)
                $g.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bounds.Size)
                $bmp.Save('{p}', [System.Drawing.Imaging.ImageFormat]::Png)
                $g.Dispose()
                $bmp.Dispose()
                """).strip()

        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        if result.returncode != 0 or not out_path.exists():
            err = (result.stderr or "").strip()
            raise RuntimeError(f"Screenshot failed: {err or f'rc={result.returncode}'}")

        return out_path