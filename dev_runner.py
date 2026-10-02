"""Use Codex's bundled Python and local dependencies when no system Python exists."""
import runpy
import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parent
dependencies = app_folder.parent / ".codex_tmp" / "quote-deps"
sys.path.insert(0, str(dependencies))
sys.path.insert(0, str(app_folder))
sys.argv = ["streamlit", "run", str(app_folder / "app.py"), "--server.address=127.0.0.1", *sys.argv[1:]]
runpy.run_module("streamlit", run_name="__main__")
