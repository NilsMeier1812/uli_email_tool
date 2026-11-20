@echo off
cd /d "%~dp0"
pip install -r requirements.txt
python create_shortcut.py
echo.
pause
