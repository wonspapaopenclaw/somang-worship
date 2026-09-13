#!/usr/bin/env python3
"""
특정 날짜 주보 수동 다운로드 및 JSON 추출
AI 모델(LM Studio)을 이용해 PDF 이미지에서 주보 데이터를 추출
"""
import base64
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# PyMuPDF 또는 pdf2image 중 하나
try:
    import pymupdf
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    try:
        from pdf2image import convert_from_path
        HAS_PDF2IMAGE = True
    except ImportError:
        HAS_PDF2IMAGE = False

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
BULLETINS_DIR = DATA_DIR / "bulletins"
ASSETS_HYMNS_DIR = BASE_DIR / "assets" / "hymns"
LATEST_JSON = DATA_DIR / "latest.json"

TARGET_DATE = "2026-08-23"  # 8월 23일 no.1236
JUBO_URL = "https://somang.net/worship/info/jubo/"

# LM Studio API
LMSTUDIO_API = "http://localhost:1234/v1/chat/completions"
LMSTUDIO_MODEL = "qwen/qwen3.8-27b"


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def find_bulletin(date_str):
    """주보 목록에서 특정 날짜 게시글 찾기"""
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    
    year, month, day = date_str.split("-")
    search_term = f"{int(year)}년 {int(month)}월 {int(day)}일"
    log(f"검색: {search_term}")
    
    resp = session.get(JUBO_URL, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")
    
    for item in soup.select('.kboard-list-item'):
        text = item.get_text(' ', strip=True)
        if search_term in text:
            a = item.select_one('a[href*="uid="]')
            if a:
                title = re.search(r'no\.(\d+)', text)
                return {
                    "title": text,
                    "number": int(title.group(1)) if title else None,
                    "pdf_url": "https://somang.net" + a.get("href")
                }
    return None


def pdf_to_image_base64(pdf_path):
    """PDF 1페이지를 base64 이미지로 변환"""
    log("PDF 1페이지 이미지 변환 중...")
    
    if HAS_PYMUPDF:
        doc = pymupdf.open(str(pdf_path))
        page = doc[0]
        # 150dpi로 줄여 이미지 크기 축소 (추론 시간 단축)
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("jpeg", jpg_quality=75)
        doc.close()
    elif HAS_PDF2IMAGE:
        images = convert_from_path(str(pdf_path), first_page=1, last_page=1, dpi=200)
        if not images:
            raise Exception("PDF 1페이지 변환 실패")
        import io
        buf = io.BytesIO()
        images[0].save(buf, format="PNG")
        img_bytes = buf.getvalue()
    else:
        raise Exception("PyMuPDF 또는 pdf2image가 설치되어 있지 않습니다")
    
    return base64.b64encode(img_bytes).decode("utf-8")


def extract_with_ai(base64_image, issue_date, bulletin_number):
    """
    LM Studio API에 주보 이미지를 보내 데이터를 추출
    """
    log(f"AI 모델에 이미지 전송 중 ({issue_date} 주보)...")
    
    prompt = f"""소망교회 주보 1페이지 이미지를 분석해서 JSON으로 변환하세요.

주보 날짜: {issue_date}
주보 번호: 제{bulletin_number}호

다음 형식으로 JSON만 반환하세요. 다른 설명은 절대 포함하지 마세요.

{{
  "issueDate": "{issue_date}",
  "bulletinNumber": {bulletin_number},
  "services": [
    {{
      "name": "주일예배",
      "times": ["07:30", "09:30", "11:30", "13:30", "15:30"],
      "leader": "예배 인도자 이름",
      "order": [
        {{"label": "예배로 부름", "participant": "인도자"}},
        {{"label": "송영", "participant": "찬양대"}},
        {{"label": "기도", "participant": "인도자"}},
        {{"label": "찬송", "hymn": {{"number": 번호, "title": "찬송가 제목"}}, "participant": "일어서서"}},
        {{"label": "참회기도", "participant": "다같이"}},
        {{"label": "사죄확인", "participant": "인도자"}},
        {{"label": "신앙고백", "name": "사도신경", "participant": "다같이"}},
        {{"label": "성시교독", "number": 번호, "reference": "교독문 범위"}},
        {{"label": "찬송", "hymn": {{"number": 번호, "title": "찬송가 제목"}}, "participant": "다같이"}},
        {{"label": "기도", "participants": "기도자 이름"}},
        {{"label": "성경봉독", "reference": "예: 요한복음 4:49-53"}},
        {{"label": "찬양", "items": ["찬양 곡 목록"]}},
        {{"label": "말씀", "title": "설교 제목", "preacher": "설교자 이름"}},
        {{"label": "기도", "participant": "설교자"}},
        {{"label": "찬송", "hymn": {{"number": 번호, "title": "찬송가 제목"}}, "participant": "다같이"}},
        {{"label": "헌금", "hymn": {{"number": 번호, "title": "찬송가 제목"}}, "participant": "다같이"}},
        {{"label": "헌금기도", "participant": "인도자"}},
        {{"label": "찬송", "hymn": {{"number": 번호, "title": "찬송가 제목"}}, "participant": "다같이"}},
        {{"label": "축도", "participant": "설교자"}},
        {{"label": "송영", "participant": "찬양대"}}
      ],
      "timeOverrides": {{
        "07:30": {{"prayer": "기도자", "praise": ["찬양 곡", "찬양부"]}},
        "09:30": {{"prayer": "기도자", "praise": ["찬양 곡", "찬양부"]}},
        "11:30": {{"prayer": "기도자", "praise": ["찬양 곡", "찬양부"]}},
        "13:30": {{"prayer": "기도자", "praise": ["찬양 곡", "찬양부"]}},
        "15:30": {{"prayer": "기도자", "praise": ["찬양 곡", "찬양부"]}}
      }}
    }}
  ],
  "nextWeekPrayer": "다음 주 기도자"
}}

중요 규칙:
- 찬송가 번호는 반드시 숫자만 입력하세요 (예: 36, 379, 545)
- 성경봉독 reference는 "예: 요한복음 4:49-53" 형식으로
- 기도자는 이미지에서 확인한 실제 이름
- 찬양 곡은 이미지에서 확인한 곡 제목
- timeOverrides의 기도자와 찬양은 이미지에서 시간별로 확인
- 읽을 수 없거나 불확실한 필드는 빈 문자열("")으로
- JSON만 반환하세요. ```json 마크다운 없이 순수 JSON으로
"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer lm-studio"
    }
    
    payload = {
        "model": LMSTUDIO_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": 8192
    }
    
    resp = requests.post(LMSTUDIO_API, json=payload, timeout=300)
    resp.raise_for_status()
    
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    
    log(f"AI 응답 길이: {len(content)}자")
    log("AI 응답 (첫 500자):")
    log(content[:500])
    
    # JSON 추출 (마크다운 코드 블록 제거)
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    
    # JSON 파싱 시도
    try:
        bulletin_data = json.loads(content)
        log("JSON 파싱 성공")
        return bulletin_data
    except json.JSONDecodeError as e:
        log(f"JSON 파싱 실패: {e}")
        log("응답 전체:")
        log(content)
        
        # 재시도: 더 명확한 프롬프트
        retry_prompt = f"""위에서 보내준 주보 이미지를 다시 분석해서 JSON으로 변환하세요.

이미지에는 예배 순서, 찬송가 번호, 기도자, 성경봉독, 설교 등이 적혀 있습니다.

반드시 다음 JSON 형식으로 반환하세요:
{{"issueDate": "{issue_date}", "bulletinNumber": {bulletin_number}, "services": [{{"name": "주일예배", "times": ["07:30","09:30","11:30","13:30","15:30"], "leader": "...", "order": [...], "timeOverrides": {{...}}}}], "nextWeekPrayer": "..."}}

순서(order) 배열에는 예배 순서대로 항목을 넣으세요. 각 항목은 {{"label": "..."}} 형식입니다.
읽을 수 없는 부분은 빈 문자열로 하세요. JSON만 반환하세요.
"""
        
        retry_payload = {
            "model": LMSTUDIO_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": retry_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 8192
        }
        
        log("재시도 중...")
        retry_resp = requests.post(LMSTUDIO_API, json=retry_payload, timeout=300)
        retry_resp.raise_for_status()
        
        data = retry_resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.strip("`\n").replace("json", "").strip()
        
        try:
            bulletin_data = json.loads(content)
            log("재시도 JSON 파싱 성공")
            return bulletin_data
        except json.JSONDecodeError:
            log("재시도도 실패했습니다")
            return None


def enrich_with_bible_data(bulletin_data):
    """성경 데이터로 성경봉독 구절 채우기"""
    bible_dir = BASE_DIR / "work" / "bible"
    if not bible_dir.exists():
        log("성경 데이터 폴더가 없습니다. 건너뜀.")
        return bulletin_data

    for service in bulletin_data.get("services", []):
        for item in service.get("order", []):
            if item.get("label") == "성경봉독" and item.get("reference"):
                ref = item["reference"]
                verses = fetch_bible_verses(bible_dir, ref)
                if verses:
                    item["verses"] = verses
                    log(f"성경 구절 채움: {ref} -> {len(verses)}절")

    return bulletin_data


def fetch_bible_verses(bible_dir, reference):
    """성경 파일에서 구절 가져오기"""
    match = re.search(r"([가-힣]+)\s*(\d+):(\d+)[-–](\d+)", reference)
    if not match:
        return []

    book, chap, v1, v2 = match.groups()
    chap, v1, v2 = int(chap), int(v1), int(v2)

    book_map = {
        "요한복음": "john", "요": "john",
        "창세기": "genesis", "창": "genesis",
        "출애굽기": "exodus", "출": "exodus",
        "레위기": "leviticus", "레": "leviticus",
        "신명기": "deuteronomy", "신": "deuteronomy",
        "역대상": "1samuel", "대하": "2samuel",
        "시편": "psalms", "시": "psalms",
        "잠언": "proverbs", "잠": "proverbs",
        " 이사야": "isaiah", "사": "isaiah",
        "여호수아": "joshua", "수": "joshua",
        "스다라": "ruth", "스": "ruth",
        " 사무엘상": "1samuel", "상": "1samuel",
        " 사무엘하": "2samuel", "하": "2samuel",
        " 열왕기상": "1kings", "상": "1kings",
        " 열왕기하": "2kings", "하": "2kings",
        " 느헤미야": "nehemiah", "느": "nehemiah",
        " 에스라": "ezra", "스": "ezra",
        " 에스델": "esther", "스": "esther",
        "但以理": "daniel", "단": "daniel",
        " 호세아": "hosea", "호": "hosea",
        " 요엘": "joel", "요": "joel",
        " 아모스": "amos", "암": "amos",
        " 오바댜": "obadiah", "오": "obadiah",
        " 요나": "jonah", "요": "jonah",
        " 미가": "micah", "미": "micah",
        " 나훗": "nahum", "나": "nahum",
        "哈박": "habakkuk", "합": "habakkuk",
        " 스바냐": "zephaniah", "스": "zephaniah",
        " 학개": "haggai", "학": "haggai",
        " 스가랴": "zechariah", "스": "zechariah",
        " 말라기": "malachi", "말": "malachi",
        " 마태복음": "matthew", "마": "matthew",
        " 마가복음": "mark", "마": "mark",
        " 누가복음": "luke", "누": "luke",
        " 행전": "acts", "행": "acts",
        " 로마서": "romans", "롬": "romans",
        " 고린도전서": "1corinthians", "고전": "1corinthians",
        " 고린도후서": "2corinthians", "고후": "2corinthians",
        " 갈라디아서": "galatians", "갈": "galatians",
        " 에베소서": "ephesians", "엡": "ephesians",
        " 필립보서": "philippians", "빌": "philippians",
        " 골로새서": "colossians", "골": "colossians",
        " 데살로니가전서": "1thessalonians", "살전": "1thessalonians",
        " 데살로니가후서": "2thessalonians", "살후": "2thessalonians",
        " 디모데전서": "1timothy", "디전": "1timothy",
        " 디모데후서": "2timothy", "디후": "2timothy",
        " 디도서": "titus", "디": "titus",
        " 필레몬서": "philemon", "몬": "philemon",
        " 히브리서": "hebrews", "히": "hebrews",
        " 야고보서": "james", "약": "james",
        " 베드로전서": "1peter", "벧전": "1peter",
        " 베드로후서": "2peter", "벧후": "2peter",
        " 요한일서": "1john", "요일": "1john",
        " 요한이서": "2john", "요이": "2john",
        " 요한삼서": "3john", "요삼": "3john",
        " 유다서": "jude", "유": "jude",
        " 요한계시록": "revelation", "계": "revelation"
    }

    book_key = book_map.get(book, book.lower())
    bible_file = bible_dir / f"{book_key}.json"

    if not bible_file.exists():
        for f in bible_dir.glob("*.json"):
            if book_key in f.stem.lower():
                bible_file = f
                break

    if not bible_file.exists():
        return []

    try:
        with open(bible_file, "r", encoding="utf-8") as f:
            bible_data = json.load(f)

        verses = []
        for v in range(v1, v2 + 1):
            verse_text = bible_data.get(str(chap), {}).get(str(v), "")
            if verse_text:
                verses.append({
                    "reference": f"{book} {chap}:{v}",
                    "book": book[0],
                    "chapter": chap,
                    "verse": v,
                    "content": verse_text
                })
        return verses
    except Exception as e:
        log(f"성경 데이터 읽기 실패: {e}")
        return []


def enrich_with_hymn_images(bulletin_data):
    """찬송가 이미지 확인 및 복사"""
    used_hymns = set()

    for service in bulletin_data.get("services", []):
        for item in service.get("order", []):
            hymn = item.get("hymn", {})
            if hymn.get("number"):
                num = hymn["number"]
                used_hymns.add(num)

                for ext in [".jpg", ".png", ".jpeg"]:
                    src = ASSETS_HYMNS_DIR / f"{num:03d}{ext}"
                    if not src.exists():
                        src = ASSETS_HYMNS_DIR / f"{num}{ext}"
                    if src.exists():
                        hymn["image"] = f"assets/hymns/{src.name}"
                        hymn["verificationStatus"] = "MATCH"
                        break
                else:
                    hymn["image"] = ""
                    hymn["verificationStatus"] = "MISSING"
                hymn["verifiedTitle"] = hymn.get("title", "")

    return bulletin_data, used_hymns


def enrich_with_responsive_readings(bulletin_data):
    """교독문 데이터 채우기"""
    readings_file = BASE_DIR / "work" / "responsive_readings.json"
    if not readings_file.exists():
        for f in BASE_DIR.rglob("*.json"):
            if "reading" in f.name.lower() or "교독" in f.name:
                readings_file = f
                break

    if not readings_file.exists():
        log("교독문 데이터 파일이 없습니다. 건너뜀.")
        return bulletin_data

    try:
        with open(readings_file, "r", encoding="utf-8") as f:
            readings_data = json.load(f)

        for service in bulletin_data.get("services", []):
            for item in service.get("order", []):
                if item.get("label") == "성시교독" and item.get("number"):
                    num = item["number"]
                    reading = readings_data.get(str(num)) or readings_data.get(num)
                    if reading:
                        item["reading"] = reading
                        log(f"교독문 {num}번 데이터 채움")
    except Exception as e:
        log(f"교독문 데이터 읽기 실패: {e}")

    return bulletin_data


def validate_bulletin(bulletin_data):
    """주보 데이터 검증"""
    errors = []
    warnings = []

    required_fields = ["issueDate", "bulletinNumber", "services"]
    for field in required_fields:
        if not bulletin_data.get(field):
            errors.append(f"필수 필드 누락: {field}")

    for service in bulletin_data.get("services", []):
        if not service.get("times"):
            errors.append("예배 시간이 없습니다")
        if not service.get("leader"):
            warnings.append("예배 인도자가 없습니다")

        for i, item in enumerate(service.get("order", [])):
            label = item.get("label", "")
            if label == "찬송":
                hymn = item.get("hymn", {})
                if not hymn.get("number"):
                    errors.append(f"순서 {i}: 찬송가 번호가 없습니다")
                if hymn.get("verificationStatus") == "MISSING":
                    warnings.append(f"순서 {i}: 찬송가 {hymn.get('number')}장 이미지 없음")
            elif label == "성시교독":
                if not item.get("number"):
                    errors.append(f"순서 {i}: 교독문 번호가 없습니다")
            elif label == "성경봉독":
                if not item.get("reference"):
                    warnings.append(f"순서 {i}: 성경봉독 구절이 없습니다")
                if not item.get("verses"):
                    warnings.append(f"순서 {i}: 성경 구절 내용이 없습니다")
            elif label == "말씀":
                if not item.get("title"):
                    warnings.append(f"순서 {i}: 설교 제목이 없습니다")
                if not item.get("preacher"):
                    warnings.append(f"순서 {i}: 설교자가 없습니다")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def save_bulletin(bulletin_data, issue_date):
    """주보 JSON 저장"""
    filename = f"{issue_date}.json"
    filepath = BULLETINS_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(bulletin_data, f, ensure_ascii=False, indent=2)
    log(f"주보 저장: {filepath}")

    # latest.json 업데이트
    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(bulletin_data, f, ensure_ascii=False, indent=2)
    log(f"최신 주보 업데이트: {LATEST_JSON}")

    update_index_json(issue_date, filename, bulletin_data.get("bulletinNumber"))
    return filepath


def update_index_json(issue_date, filename, bulletin_number=None):
    """bulletins/index.json 업데이트"""
    index_path = BULLETINS_DIR / "index.json"

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    except:
        index = []

    index = [item for item in index if item.get("date") != issue_date]
    label = f"{issue_date.replace('-', '년 ').replace('-', '월 ')}일 · 제{bulletin_number or '?'}호"
    index.insert(0, {"date": issue_date, "file": filename, "label": label})
    index = index[:20]

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    log(f"인덱스 업데이트: {index_path}")


def git_commit_and_push(issue_date, changed_files):
    """Git 커밋 및 푸시"""
    try:
        os.chdir(BASE_DIR)
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not result.stdout.strip():
            log("변경사항 없음, 커밋 생략")
            return False

        for f in changed_files:
            subprocess.run(["git", "add", f], check=True)

        commit_msg = f"주보 업데이트: {issue_date}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        log(f"커밋 완료: {commit_msg}")

        subprocess.run(["git", "push"], check=True)
        log("푸시 완료 - GitHub Pages 배포 트리거됨")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Git 작업 실패: {e}")
        return False


import os


def main():
    log("=== 특정 날짜 주보 추출 시작 (AI 모델 사용) ===")

    try:
        # 1. 주보 찾기
        info = find_bulletin(TARGET_DATE)
        if not info:
            log(f"ERROR: {TARGET_DATE} 주보를 찾을 수 없습니다")
            return 1

        log(f"제목: {info['title'][:50]}")
        log(f"번호: {info['number']}")

        # 2. PDF 다운로드
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        pdf_path = BASE_DIR / f"temp_{TARGET_DATE}.pdf"

        log("PDF 다운로드 중...")
        resp = session.get(info["pdf_url"], timeout=60)
        resp.raise_for_status()
        with open(pdf_path, "wb") as f:
            f.write(resp.content)
        log(f"PDF 저장: {pdf_path.stat().st_size} bytes")

        # 3. 이미 저장되어 있는지 확인
        existing_file = BULLETINS_DIR / f"{TARGET_DATE}.json"
        if existing_file.exists():
            log(f"이미 {TARGET_DATE} 주보가 저장되어 있습니다")
            pdf_path.unlink(missing_ok=True)
            return 0

        # 4. PDF 1페이지 이미지 변환
        base64_image = pdf_to_image_base64(pdf_path)
        log(f"이미지 base64 길이: {len(base64_image)}자")

        # 5. AI 모델로 추출
        bulletin_data = extract_with_ai(base64_image, TARGET_DATE, info["number"])
        pdf_path.unlink(missing_ok=True)

        if not bulletin_data:
            log("ERROR: AI 모델에서 유효한 JSON을 추출할 수 없습니다")
            return 1

        # 6. 원본 URL 추가
        bulletin_data["sourcePdf"] = info["pdf_url"]
        bulletin_data["page"] = 1

        # 7. 데이터 보강
        log("성경 데이터 보강 중...")
        bulletin_data = enrich_with_bible_data(bulletin_data)

        log("찬송가 이미지 보강 중...")
        bulletin_data, used_hymns = enrich_with_hymn_images(bulletin_data)

        log("교독문 데이터 보강 중...")
        bulletin_data = enrich_with_responsive_readings(bulletin_data)

        # 8. 검증
        validation = validate_bulletin(bulletin_data)
        log(f"검증: valid={validation['valid']}, errors={len(validation['errors'])}, warnings={len(validation['warnings'])}")

        if validation["errors"]:
            for e in validation["errors"]:
                log(f"  ERROR: {e}")
        for w in validation["warnings"]:
            log(f"  WARNING: {w}")

        if not validation["valid"]:
            log("검증 실패: 기존 latest.json을 유지합니다. 수동 검수 필요.")
            return 1

        # 9. 저장
        saved_file = save_bulletin(bulletin_data, TARGET_DATE)

        # 10. Git
        changed_files = [str(saved_file.relative_to(BASE_DIR)), str(LATEST_JSON.relative_to(BASE_DIR)), "data/bulletins/index.json"]
        deployed = git_commit_and_push(TARGET_DATE, changed_files)

        log("=== 작업 완료 ===")
        log(f"주보 날짜: {TARGET_DATE}")
        log(f"변경된 파일: {', '.join(changed_files)}")
        log(f"검증: 성공 (경고 {len(validation['warnings'])}개)")
        log(f"GitHub Pages 배포: {'예' if deployed else '아니오'}")

        return 0

    except Exception as e:
        log(f"작업 실패: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())