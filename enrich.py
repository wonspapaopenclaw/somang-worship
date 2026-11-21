#!/usr/bin/env python3
"""
2026-11-08 주보 데이터 보강 스크립트
1) 찬송가 제목/이미지: hymn-search 참조
2) 성시교독 85번: responsive_readings_1-137.json 참조
3) 성경봉독 5부: work/bible/bible.py 이용
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(".")
BULLETINS_DIR = BASE_DIR / "data" / "bulletins"
LATEST_JSON = BASE_DIR / "data" / "latest.json"
ASSETS_HYMNS_DIR = BASE_DIR / "assets" / "hymns"

HYMN_DATA = Path("C:/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/work/hymn-search")
HYMN_INDEX = HYMN_DATA / "references" / "hymn_index.json"
HYMN_IMAGES = HYMN_DATA / "data"

RESPONSIVE_FILE = Path("C:/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/outputs/responsive_readings_1-137.json")

BIBLE_DIR = Path("C:/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/work/bible")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


sys.path.insert(0, str(BIBLE_DIR))
from bible import parse_reference, search_by_reference, load_data, BOOK_FULL_NAMES


def fix_hymns(bulletin_data):
    log("=== 찬송가 제목/이미지 수정 ===")
    try:
        index = load_json(HYMN_INDEX)
    except Exception as e:
        log(f"  hymn_index.json 로드 실패: {e}")
        return bulletin_data
    
    ASSETS_HYMNS_DIR.mkdir(parents=True, exist_ok=True)
    copied = []
    for item in bulletin_data["services"][0]["order"]:
        hymn = item.get("hymn")
        if not hymn:
            continue
        num = str(hymn["number"])
        title = index.get(num)
        if title:
            if hymn["title"] != title:
                log(f"  {num}장 제목 교정: '{hymn['title']}' -> '{title}'")
            hymn["title"] = title
            hymn["verifiedTitle"] = title
        # 이미지 복사 (없으면)
        found = False
        for ext in [".jpg", ".png", ".jpeg"]:
            src = HYMN_IMAGES / f"{int(num):03d}{ext}"
            if src.exists():
                dst = ASSETS_HYMNS_DIR / src.name
                if not dst.exists():
                    shutil.copy2(src, dst)
                    copied.append(src.name)
                    log(f"  이미지 복사: {src.name}")
                hymn["image"] = f"assets/hymns/{src.name}"
                hymn["verificationStatus"] = "MATCH"
                found = True
                break
        if not found:
            hymn["verificationStatus"] = "MISSING"
            log(f"  {num}장 이미지 없음 (MISSING)")
    log(f"  복사된 이미지: {len(copied)}개")
    return bulletin_data


def fix_reading(bulletin_data):
    log("=== 성시교독 수정 ===")
    try:
        data = load_json(RESPONSIVE_FILE)
    except Exception as e:
        log(f"  responsive_readings_1-137.json 로드 실패: {e}")
        return bulletin_data
    
    items = data.get("items", [])
    for item in bulletin_data["services"][0]["order"]:
        if item.get("label") != "성시교독":
            continue
        num = item.get("number")
        match = next((it for it in items if it.get("number") == num), None)
        if match:
            item["reading"] = {
                "lines": match.get("lines", []),
                "number": num,
                "reference": match.get("reference", item.get("reference", "")),
                "title": match.get("title", item.get("reference", "")),
            }
            log(f"  교독문 {num}번: {match.get('reference')} ({len(match.get('lines', []))}행)")
        else:
            log(f"  교독문 {num}번: 데이터 없음")
    return bulletin_data


def fix_bible_verses(bulletin_data):
    log("=== 성경봉독 본문 조회 (bible.py) ===")
    try:
        data = load_data()
    except Exception as e:
        log(f"  bible.py 로드 실패: {e}")
        return bulletin_data
    
    for item in bulletin_data["services"][0]["order"]:
        if item.get("label") != "성경봉독":
            continue
        # 기존 reference에서 추출
        ref = item.get("reference", "")
        if not ref:
            continue
        
        parsed = parse_reference(ref)
        if not parsed:
            log(f"  파싱 실패: {ref}")
            continue
        
        book, chapter, v1, v2 = parsed
        results = search_by_reference(data, book, chapter, v1 or 1, v2 or 999)
        
        if results:
            full_book = BOOK_FULL_NAMES.get(book, book)
            all_verses = []
            for r in results:
                all_verses.append({
                    "reference": f"{book} {r['chapter']}:{r['verse']}",
                    "book": book,
                    "chapter": r["chapter"],
                    "verse": r["verse"],
                    "content": r["content"],
                })
            log(f"  {ref} -> {full_book} {chapter}:{v1 or 1}-{v2 or 999} ({len(results)}절)")
            item["verses"] = all_verses
        else:
            log(f"  조회 실패: {ref}")
    return bulletin_data


def main():
    import sys
    if len(sys.argv) < 2:
        log("사용법: python enrich.py <날짜-YYYY-MM-DD>")
        sys.exit(1)
    
    target_date = sys.argv[1]
    bulletin_path = BULLETINS_DIR / f"{target_date}.json"
    
    if not bulletin_path.exists():
        log(f"주보 파일 없음: {bulletin_path}")
        sys.exit(1)
    
    log(f"=== {target_date} 주보 데이터 보강 시작 ===")
    bulletin_data = load_json(bulletin_path)

    bulletin_data = fix_hymns(bulletin_data)
    bulletin_data = fix_reading(bulletin_data)
    bulletin_data = fix_bible_verses(bulletin_data)

    with open(bulletin_path, "w", encoding="utf-8") as f:
        json.dump(bulletin_data, f, ensure_ascii=False, indent=2)
    log(f"저장: {bulletin_path}")

    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(bulletin_data, f, ensure_ascii=False, indent=2)
    log("latest.json 업데이트")

    # 검증
    total_verses = sum(len(v.get("verses", [])) for i in bulletin_data["services"][0]["order"]
                       if i.get("label") == "성경봉독" for v in [i] if "timeVariants" in i for v in i.get("timeVariants", []))
    # Simple count for verses
    verse_count = 0
    for i in bulletin_data["services"][0]["order"]:
        if i.get("label") == "성경봉독":
            if "verses" in i:
                verse_count += len(i["verses"])
    
    missing_hymns = [h["hymn"]["number"] for h in bulletin_data["services"][0]["order"]
                     if h.get("hymn", {}).get("verificationStatus") == "MISSING"]
    log(f"=== 완료: 성경 구절 {verse_count}절, 찬송 이미지 누락 {len(missing_hymns)}개 {missing_hymns} ====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
