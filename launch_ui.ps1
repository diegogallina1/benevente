param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$StreamlitArgs
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv-benevente\Scripts\python.exe"
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"

if (-not (Test-Path $python)) {
    throw "Ambiente virtual não encontrado. Execute: python -m venv .venv-benevente; .\.venv-benevente\Scripts\python.exe -m pip install -r requirements.txt"
}

Write-Host "Iniciando Benevente em http://localhost:8501" -ForegroundColor Cyan
Write-Host "Mantenha esta janela aberta e acesse o endereço no navegador." -ForegroundColor DarkGray
& $python -m streamlit run (Join-Path $root "app.py") --server.headless=true --browser.gatherUsageStats=false @StreamlitArgs
