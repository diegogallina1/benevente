@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv-benevente\Scripts\python.exe"
set "STREAMLIT_BROWSER_GATHER_USAGE_STATS=false"
if not exist "%PYTHON%" (
  echo Ambiente virtual nao encontrado.
  echo Execute: python -m venv .venv-benevente
  echo Depois: .venv-benevente\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)
echo Iniciando Benevente em http://localhost:8501
echo Mantenha esta janela aberta e acesse o endereco no navegador.
"%PYTHON%" -m streamlit run "%ROOT%app.py" --server.headless=true --browser.gatherUsageStats=false %*
