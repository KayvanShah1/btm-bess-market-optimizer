from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from bess_dashboard.seo import patch_streamlit_static_index


def main() -> None:
    patch_streamlit_static_index()
    app_path = Path(__file__).with_name("app.py")
    command = [sys.executable, "-m", "streamlit", "run", *sys.argv[1:], str(app_path)]
    raise SystemExit(subprocess.run(command, check=False).returncode)


if __name__ == "__main__":
    main()
