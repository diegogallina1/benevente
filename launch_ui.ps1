$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$root\.venv-benevente\Scripts\streamlit.exe" run "$root\app.py"
