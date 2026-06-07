@echo off
REM AI feeds weekly digest -> Notion (ASCII only; cmd reads .bat in OEM codepage)
cd /d "C:\Users\USER1502\github-scout"
"C:\Users\USER1502\AppData\Local\Python\pythoncore-3.14-64\python.exe" "C:\Users\USER1502\github-scout\feeds_scout.py" --scan >> "C:\Users\USER1502\github-scout\logs\feeds.log" 2>&1
