@echo off
chcp 65001 >nul
title HLC Live Automation v3 - Auto Cloud Tunnel

echo ======================================================================
echo           🚀 HLC LIVE AUTOMATION v3 - KHOI DONG HE THONG TU DONG
echo ======================================================================
echo.
echo [*] Dang kiem tra moi truong Python va thu vien...
python -c "import flask, obsws_python, cv2, requests" 2>nul
if %errorlevel% neq 0 (
    echo [*] Phat hien thieu thu vien, dang tu dong cai dat dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [!] Loi khi cai dat thu vien. Vui long kiem tra ket noi mang.
        pause
        exit /b 1
    )
)

echo [*] Moi thu da san sang! Dang khoi chay He thong va Cloudflare Tunnel...
echo [*] Trinh duyet Web se tu dong mo len trong giay lat...
echo.
python run.py

if %errorlevel% neq 0 (
    echo.
    echo [!] He thong da dung hoac xay ra loi.
    pause
)
