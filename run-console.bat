@echo off
REM Nhu run.bat nhung chay trong cua so terminal, thay duoc log va Ctrl+C de dung.
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 ( py -3 run.py --window ) else ( python run.py --window )
pause
endlocal
