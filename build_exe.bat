@echo off
cd /d "%~dp0"
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --onefile --windowed --name VertriebEmailTool --icon icon.ico --add-data "icon.ico;." email_tool.pyw
echo.
echo Fertig: dist\VertriebEmailTool.exe
pause
