@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Tworzenie wirtualnego srodowiska Python...
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)
echo Sprawdzanie i instalowanie zaleznosci...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error
echo Uruchamianie PhotometryLab...
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 goto :error
exit /b 0
:error
echo.
echo Nie udalo sie uruchomic aplikacji. Sprawdz, czy Python 3.10+ oraz internet sa dostepne.
pause
exit /b 1
