#!/usr/bin/env python3
"""
2026-09-20 주보 데이터 보강 스크립트
1) 찬송가 제목/이미지: hymn-search 참조
2) 성시교독 81번: responsive_readings_1-137.json 참조
3) 성경봉독 5부: work/bible/bible.py 이용
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
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


# hymn.py의 parse_reference 재사용 (bible.py가 있는 경로를 sys.path에 추가)
sys.path.insert(0, str(BIBLE_DIR))
from bible import parse_reference, search_by_reference, load_data, BOOK_FULL_NAMES


def fix_hymns(bulletin_data):
    log("=== 찬송가 제목/이미지 수정 ===")
    index = load_json(HYMN_INDEX)
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
                break
        else:
            hymn["verificationStatus"] = "MISSING"
            log(f"  {num}장 이미지 없음 (MISSING)")
    log(f"  복사된 이미지: {len(copied)}개")
    return bulletin_data


def fix_reading(bulletin_data):
    log("=== 성시교독 81번 수정 ===")
    data = load_json(RESPONSIVE_FILE)
    items = data["items"]
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
    data = load_data()
    for item in bulletin_data["services"][0]["order"]:
        if item.get("label") != "성경봉독":
            continue
        variants = item.get("timeVariants", [])
        for v in variants:
            ref = v.get("reference", "")
            # 다중 참조 지원 (예: "출애굽기 3:1-12, 요한복음 20:21")
            parts = [p.strip() for p in ref.split(",")]
            all_verses = []
            for part in parts:
                parsed = parse_reference(part)
                if not parsed:
                    log(f"  파싱 실패: {part}")
                    continue
                book, chapter, v1, v2 = parsed
                results = search_by_reference(data, book, chapter, v1 or 1, v2 or 999)
                if not results:
                    log(f"  조회 실패: {part}")
                    continue
                full_book = BOOK_FULL_NAMES.get(book, book)
                for r in results:
                    all_verses.append({
                        "reference": f"{book} {r['chapter']}:{r['verse']}",
                        "book": book,
                        "chapter": r["chapter"],
                        "verse": r["verse"],
                        "content": r["content"],
                    })
                log(f"  {part} -> {full_book} {chapter}:{v1}-{v2} ({len(results)}절)")
            if all_verses:
                v["verses"] = all_verses
        # 기존 reference 필드도 첫 번째 variant로 업데이트 (하위호환)
        if variants:
            item["reference"] = variants[0].get("reference", item.get("reference", ""))
    return bulletin_data


def main():
    log("=== 2026-09-20 주보 데이터 보강 시작 ===")
    bulletin_path = BULLETINS_DIR / "2026-09-20.json"
    bulletin_data = load_json(bulletin_path)

    bulletin_data = fix_hymns(bulletin_data)
    bulletin_data = fix_reading(bulletin_data)
    bulletin_data = fix_bible_verses(bulletin_data)

    with open(bulletin_path, "w", encoding="utf-8") as f:
        json.dump(bulletin_data, f, ensure_ascii=False, indent=2)
    log(f"저장: {bulletin_path}")

    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(bulletin_data, f, ensure_ascii=False, indent=2)
    log(f"latest.json 업데이트")

    # 검증
    total_verses = sum(len(v.get("verses", [])) for i in bulletin_data["services"][0]["order"]
                       if i.get("label") == "성경봉독" for v in i.get("timeVariants", []))
    missing_hymns = [h["hymn"]["number"] for h in bulletin_data["services"][0]["order"]
                     if h.get("hymn", {}).get("verificationStatus") == "MISSING"]
    log(f"=== 완료: 성경 구절 {total_verses}절, 찬송 이미지 누락 {len(missing_hymns)}개 {missing_hymns} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
