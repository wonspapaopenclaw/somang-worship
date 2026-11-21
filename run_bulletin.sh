#!/bin/bash
# 소망교회 주보 자동 업데이트 - Git Bash 용 스크립트
cd "/c/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/outputs/github-pages/somang-worship"
export PYTHONIOENCODING=utf-8
export LM_STUDIO_ENABLED=true
/c/Users/chajh/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe update_bulletin.py >> logs/update_bulletin.log 2>&1