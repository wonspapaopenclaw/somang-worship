@echo off
REM 소망교회 주보 자동 업데이트 - Windows 작업 스케줄러용 배치 파일
REM 매주 금요일 오후 8시 15분 실행

cd /d "C:\Users\chajh\Documents\Codex\2026-09-06\referenced-chatgpt-conversation-this-is-an\outputs\github-pages\somang-worship"

REM Python 실행 (UTF-8 인코딩 설정)
set PYTHONIOENCODING=utf-8
python update_bulletin.py >> logs/update_bulletin.log 2>&1

exit /b %ERRORLEVEL%