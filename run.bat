@echo off
REM Chay jobbot tren Windows. Bam dup vao file nay.
REM Khong can cai gi ngoai Python 3.11+ va Google Chrome.

setlocal
cd /d "%~dp0"

REM py.exe (Python Launcher) di kem ban cai Python chinh thuc va biet chon
REM dung phien ban. Khong co thi lui ve python trong PATH.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 run.py %*
) else (
    python run.py %*
)

if %errorlevel% neq 0 (
    echo.
    echo   Chay that bai. Kiem tra:
    echo     1. Da cai Python 3.11 tro len chua^?  python --version
    echo     2. Da cai Google Chrome chua^?
    echo.
    pause
)
endlocal
