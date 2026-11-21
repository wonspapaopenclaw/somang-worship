#!/usr/bin/env python3
"""LM Studio 서버 실행 스크립트"""
import subprocess
import time
import os
import sys
import urllib.request
import urllib.error

def check_lm_studio():
    """LM Studio 서버 확인"""
    try:
        req = urllib.request.Request("http://localhost:1234/v1/models")
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except:
        return False

def start_lm_studio():
    """LM Studio 실행"""
    lm_path = r"C:\Users\chajh\.lmstudio\bin\lms.exe"
    if not os.path.exists(lm_path):
        print(f"LM Studio executable not found: {lm_path}")
        return False
    
    print(f"LM Studio 실행: {lm_path}")
    proc = subprocess.Popen(
        [lm_path, "--server", "--port", "1234"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    print(f"PID: {proc.pid}")
    return True

if __name__ == "__main__":
    if check_lm_studio():
        print("LM Studio 서버가 이미 실행 중입니다.")
        sys.exit(0)
    
    if start_lm_studio():
        print("5초 대기 중...")
        time.sleep(5)
        
        if check_lm_studio():
            print("LM Studio 서버 시작 성공!")
            sys.exit(0)
        else:
            print("LM Studio 서버 시작 실패!")
            sys.exit(1)
    else:
        sys.exit(1)
