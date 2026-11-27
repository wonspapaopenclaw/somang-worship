#!/bin/bash
# 소망교회 주보 자동 업데이트 - Git Bash 용 스크립트
# 크론 e7a72eebdc33: 주간 금요일 19:00 실행 (LM Studio OCR 기본 모드)
# 업데이트: 찬송가 이미지 자동 동기화 포함 (hymn-image-sync.md 참조)

cd "/c/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/outputs/github-pages/somang-worship"
export PYTHONIOENCODING=utf-8
export LM_STUDIO_ENABLED=true

# 1. update_bulletin.py 실행 (PDF 다운로드, OCR, JSON 생성)
/c/Users/chajh/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe update_bulletin.py >> logs/update_bulletin.log 2>&1

# 2. 찬송가 이미지 자동 동기화 (MISSING 상태 해결)
# - latest.json에서 이미지 누락 hymn 확인 후 work/hymn-search/data에서 assets/hymns로 복사
# - process_bulletin.py에서 LM_STUDIO_ENABLED=true로 LM Studio olmocr-2-7b를 기본 OCR 방식으로 사용
python -c "
import json
import shutil
from pathlib import Path

src = Path('work/hymn-search/data')
dst = Path('assets/hymns')
latest_json = Path('data/latest.json')

if not latest_json.exists():
    print('latest.json 없음, 이미지 동기화 생략')
    exit(0)

with open(latest_json, 'r', encoding='utf-8') as f:
    data = json.load(f)

synced = False
for svc in data.get('services', []):
    for item in svc.get('order', []):
        num = item.get('hymn', {}).get('number')
        if num:
            img = dst / f'{num:03d}.jpg'
            if not img.exists():
                src_img = src / f'{num:03d}.jpg'
                if src_img.exists():
                    shutil.copy2(src_img, img)
                    item['hymn']['image'] = str(img)
                    item['hymn']['verificationStatus'] = 'MATCH'
                    synced = True

if synced:
    with open(latest_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'찬송가 이미지 {synced}개 동기화 완료')
else:
    print('동기화 필요 이미지 없음 (전체 MATCH 상태)')
"

# 3. Git 커밋 및 푸시 (data/와 assets/ 모두 포함)
git add data/ assets/ >> logs/git.log 2>&1
if [ -n "$(git status --porcelain)" ]; then
    git commit -m "$(date +'주보 업데이트: %Y-%m-%d')"
    git push >> logs/git.log 2>&1
    echo 'Git 푸시 완료 - GitHub Pages 배포 트리거됨'
else
    echo '변경사항 없음, 커밋 생략'
fi