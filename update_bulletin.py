#!/usr/bin/env python3
"""
소망교회 주보 자동 업데이트 스크립트
매주 금요일 오후 8시 15분 실행
"""

import json
import os
import re
import subprocess
import sys
import time
import base64
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text

# ──────────────────────────────────────────────
# 설정 (환경 변수로 오버라이드 가능)
# ──────────────────────────────────────────────
BASE_DIR = Path(os.getenv("SOMANG_BASE_DIR", Path(__file__).parent)).resolve()
DATA_DIR = BASE_DIR / "data"
BULLETINS_DIR = DATA_DIR / "bulletins"
ASSETS_HYMNS_DIR = BASE_DIR / "assets" / "hymns"
LATEST_JSON = DATA_DIR / "latest.json"

JUBO_URL = "https://somang.net/worship/info/jubo/"

# LM Studio 설정 (선택적)
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "allenai/olmocr-2-7b")
LM_STUDIO_ENABLED = os.getenv("LM_STUDIO_ENABLED", "false").lower() == "true"

# 요청 세션
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────
def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def to_win_path(path: Path) -> str:
    """Path 객체를 Windows 네이티브 문자열로 변환"""
    s = str(path.resolve())
    if s.startswith("/c/"):
        return "C:" + s[2:].replace("/", "\\")
    return s.replace("/", "\\")


def safe_unlink(path: Path) -> None:
    """파일 안전 삭제"""
    try:
        if path.exists():
            path.unlink()
    except Exception as e:
        log(f"파일 삭제 실패 {path}: {e}")


def http_get_with_retry(url: str, timeout: int = 30, max_retries: int = 3, stream: bool = False) -> requests.Response:
    """재시도 로직이 있는 GET 요청"""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, timeout=timeout, stream=stream)
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_exc = e
            log(f"요청 실패 ({attempt}/{max_retries}): {url} - {e}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
    raise last_exc


# ──────────────────────────────────────────────
# 주보 정보 수집
# ──────────────────────────────────────────────
def get_latest_bulletin_info() -> dict:
    """최신 주보 게시글 정보 가져오기"""
    log("주보 목록 페이지 요청 중...")
    resp = http_get_with_retry(JUBO_URL)

    soup = BeautifulSoup(resp.text, "html.parser")

    first_item = soup.select_one(
        ".kboard-list .kboard-list-item:first-child, "
        ".kboard-list table tbody tr:first-child, "
        "tbody tr:first-child"
    )
    if not first_item:
        raise Exception("주보 게시글을 찾을 수 없습니다 (HTML 구조 변경 가능성)")

    title_elem = first_item.select_one(
        ".kboard-title a, td.kboard-title a, "
        "a[href*='uid='], a[href*='kboard_file_download']"
    )
    if not title_elem:
        raise Exception("주보 제목을 찾을 수 없습니다")

    title_text = title_elem.get_text(strip=True)
    log(f"최신 주보 제목: {title_text}")

    date_match = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", title_text)
    if not date_match:
        raise Exception(f"날짜 파싱 실패: {title_text}")

    year, month, day = date_match.groups()
    issue_date = f"{year}-{int(month):02d}-{int(day):02d}"

    number_match = re.search(r"no\.(\d+)", title_text)
    bulletin_number = int(number_match.group(1)) if number_match else None

    pdf_link = title_elem.get("href", "")
    if pdf_link and not pdf_link.startswith("http"):
        pdf_link = "https://somang.net" + pdf_link

    log(f"주보 날짜: {issue_date}, 번호: {bulletin_number}")
    log(f"PDF 링크: {pdf_link}")

    return {
        "issue_date": issue_date,
        "bulletin_number": bulletin_number,
        "pdf_url": pdf_link,
        "title": title_text
    }


def download_pdf(pdf_url: str, save_path: Path) -> Path:
    """PDF 다운로드"""
    log(f"PDF 다운로드 중: {pdf_url}")
    resp = http_get_with_retry(pdf_url, timeout=60, stream=True)

    win_path = to_win_path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(win_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
        f.flush()
        os.fsync(f.fileno())

    size = save_path.stat().st_size
    log(f"PDF 저장 완료: {save_path} ({size} bytes)")
    return save_path


# ──────────────────────────────────────────────
# PDF 처리
# ──────────────────────────────────────────────
def extract_pdf_first_page_text(pdf_path: Path) -> str:
    """PDF 1페이지 텍스트 추출 (pdfminer)"""
    log("PDF 텍스트 추출 중... (pdfminer)")
    try:
        text = extract_text(str(pdf_path), page_numbers=[0])
        return text.strip()
    except Exception as e:
        log(f"pdfminer 텍스트 추출 실패: {e}")
        return ""


def extract_pdf_first_page_image(pdf_path: Path, save_path: Path) -> Path | None:
    """PDF 1페이지를 이미지로 변환 (PyMuPDF 사용, poppler 불필요)"""
    log("PDF 1페이지 이미지 변환 중... (PyMuPDF)")
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        page = doc[0]
        pix = page.get_pixmap(dpi=600)
        abs_save_path = str(save_path.resolve())
        pix.save(abs_save_path)
        log(f"이미지 저장 완료: {abs_save_path} ({pix.width}x{pix.height})")
        doc.close()
        return save_path
    except Exception as e:
        log(f"이미지 변환 실패 (PyMuPDF): {e}")
    return None


# ──────────────────────────────────────────────
# 텍스트 파싱
# ──────────────────────────────────────────────
def parse_bulletin_text(text: str) -> dict:
    """주보 텍스트에서 정보 파싱"""
    log("주보 텍스트 파싱 중...")

    result = {"services": [], "next_week_prayer": ""}
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    service = {
        "name": "주일예배",
        "times": ["07:30", "09:30", "11:30", "13:30", "15:30"],
        "leader": "",
        "order": [],
        "timeOverrides": {}
    }

    # 파싱된 항목들을 별도 리스트에 모음 (템플릿 병합용)
    parsed_items = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # 예배 인도자
        if "인도" in line and "목사" in line and not service["leader"]:
            service["leader"] = line
            i += 1
            continue

        # 섹션 헤더 감지 및 같은 줄 내용 파싱
        section_keywords = [
            "예배로 부름", "송영", "기도", "찬송", "참회기도", "사죄확인",
            "신앙고백", "성시교독", "성경봉독", "찬양", "말씀", "설교",
            "헌금", "헌금기도", "축도"
        ]
        
        matched_section = None
        remaining_text = ""
        for kw in section_keywords:
            if line.startswith(kw):
                matched_section = kw
                remaining_text = line[len(kw):].strip()
                break
            elif line == kw:
                matched_section = kw
                remaining_text = ""
                break

        if matched_section:
            # 같은 줄에 내용이 있으면 바로 파싱
            if remaining_text:
                parsed_item = parse_section_content(matched_section, remaining_text, service)
                if parsed_item:
                    parsed_items.append(parsed_item)
            else:
                # 다음 줄 파싱
                i += 1
                if i < len(lines):
                    next_line = lines[i]
                    parsed_item = parse_section_content(matched_section, next_line, service)
                    if parsed_item:
                        parsed_items.append(parsed_item)
            i += 1
            continue

        i += 1

    # 기본 템플릿과 병합
    service["order"] = build_default_order(parsed_items, text)
    result["services"] = [service]

    # 기본 템플릿과 병합
    service["order"] = build_default_order(parsed_items, text)
    
    # 후처리: 찬양 여러 줄 병합, 헌금 번호 수정, 말씀 제목 정리
    for item in service["order"]:
        if item.get("label") == "찬양" and len(item.get("items", [])) == 1:
            # OCR 텍스트에서 찬양 부분 전체 추출
            praise_match = re.search(r"찬양\s+(.+?)(?:\n(?:말씀|설교|기도|헌금|축도|송영)|\Z)", text, re.DOTALL)
            if praise_match:
                praise_text = praise_match.group(1).strip()
                # 줄바꿈으로 분리된 여러 찬양 곡 파싱
                praise_lines = [l.strip() for l in praise_text.split("\n") if l.strip() and not l.strip().startswith("찬양")]
                if praise_lines:
                    item["items"] = praise_lines
        
        elif item.get("label") == "헌금" and item.get("hymn", {}).get("number") == 0:
            # 헌금 찬송가 번호 찾기
            offering_match = re.search(r"헌금\s+(\d+)", text)
            if offering_match:
                num = int(offering_match.group(1))
                img_file = ASSETS_HYMNS_DIR / f"{num:03d}.jpg"
                if not img_file.exists():
                    img_file = ASSETS_HYMNS_DIR / f"{num}.jpg"
                item["hymn"] = {
                    "number": num,
                    "title": "",
                    "image": f"assets/hymns/{img_file.name}" if img_file.exists() else "",
                    "verifiedTitle": "",
                    "verificationStatus": "MATCH" if img_file.exists() else "MISSING"
                }
        
        elif item.get("label") == "말씀":
            # 설교자 이름 제거
            title = item.get("title", "")
            preacher = item.get("preacher", "")
            if preacher and title.endswith(preacher):
                item["title"] = title[:-len(preacher)].strip()
            elif "김경진 목사" in title:
                item["title"] = title.replace("김경진 목사", "").strip()
    
    result["services"] = [service]

    # 다음 주 기도자
    next_prayer_match = re.search(r"다음\s*주\s*(?:일)?\s*기도\s*[:]\s*(.+)", text)
    if next_prayer_match:
        result["next_week_prayer"] = next_prayer_match.group(1).strip()

    return result


def parse_section_content(section: str, line: str, service: dict) -> dict | None:
    """섹션별 내용 파싱 헬퍼"""
    # 찬송/헌금에서 "일어서서", "다같이", "앉아서" 등은 참여자 지시이지 찬송가 제목이 아님
    non_title_keywords = ["일어서서", "다같이", "앉아서", "끝절은 일어서서"]
    
    def clean_title(title: str) -> str:
        """참여자 지시어 제거"""
        cleaned = title
        for kw in non_title_keywords:
            cleaned = cleaned.replace(kw, "").strip()
        return cleaned

    if section == "찬송" or (section == "헌금" and "헌금" in line):
        # 찬송/헌금: "27 일어서서", "446 다같이", "413(끝절은 일어서서) 다같이"
        hymn_match = re.search(r"(\d+)(?:\([^)]+\))?\s*(.*)", line)
        if hymn_match:
            num = int(hymn_match.group(1))
            title_raw = hymn_match.group(2).strip()
            title = clean_title(title_raw)
            img_file = ASSETS_HYMNS_DIR / f"{num:03d}.jpg"
            if not img_file.exists():
                img_file = ASSETS_HYMNS_DIR / f"{num}.jpg"
            return {
                "label": section,
                "hymn": {
                    "number": num,
                    "title": title,
                    "image": f"assets/hymns/{img_file.name}" if img_file.exists() else "",
                    "verifiedTitle": title,
                    "verificationStatus": "MATCH" if img_file.exists() else "MISSING"
                },
                "participant": "다같이"
            }
        # 번호 없이 제목만
        hymn_match2 = re.search(r"(.+)", line)
        if hymn_match2:
            title = clean_title(hymn_match2.group(1).strip())
            return {
                "label": "찬송",
                "hymn": {"number": 0, "title": title, "image": "", "verifiedTitle": title, "verificationStatus": "MISSING"},
                "participant": "다같이"
            }

    elif section in ["성시교독", "교독"]:
        # "82번(빌립보서 2장) 앉아서"
        reading_match = re.search(r"(\d+)번?\s*[\(]?([^\)]+)?[\)]?\s*(.*)", line)
        if reading_match:
            num = int(reading_match.group(1))
            ref = reading_match.group(2).strip() if reading_match.group(2) else ""
            extra = reading_match.group(3).strip()
            participant = "앉아서" if "앉아서" in extra else "다같이"
            return {
                "label": "성시교독",
                "number": num,
                "reference": ref,
                "reading": {"number": num, "reference": ref, "title": ref, "lines": []},
                "participant": participant
            }

    elif section == "성경봉독":
        # "눅 13:18~19 인도자"
        verse_match = re.search(r"([가-힣]+)\s*(\d+):(\d+)[-–~](\d+)", line)
        if verse_match:
            book, chap, v1, v2 = verse_match.groups()
            book_map = {"눅": "누가복음", "요": "요한복음", "마": "마태복음", "막": "마가복음", "행": "사도행전", "롬": "로마서"}
            book_full = book_map.get(book, book)
            return {
                "label": "성경봉독",
                "reference": f"{book_full} {chap}:{v1}-{v2}",
                "verses": [],
                "participant": "인도자"
            }

    elif section in ["말씀", "설교"]:
        # "새들이 깃드는 하나님 나라 김경진 목사"
        preacher_match = re.search(r"(.+?)\s+([가-힣]+목사)$", line)
        if preacher_match:
            title = preacher_match.group(1).strip()
            preacher = preacher_match.group(2).strip()
        else:
            title = line
            preacher = service["leader"]
        return {
            "label": "말씀",
            "title": title,
            "preacher": preacher,
            "participant": "설교자"
        }

    elif section == "찬양":
        # 찬양은 여러 곡이 있을 수 있음 - 기존 items에 추가
        # 이 함수는 한 번만 호출되므로 items 리스트를 반환
        # 여러 줄을 처리하려면 parse_bulletin_text에서 별도 처리 필요
        return {
            "label": "찬양",
            "items": [line],
            "participant": "찬양대"
        }

    elif section == "기도":
        return {
            "label": "기도",
            "participant": line
        }

    elif section in ["예배로 부름", "송영", "참회기도", "사죄확인", "신앙고백", "헌금기도", "축도"]:
        default_participant = "인도자" if section in ["예배로 부름", "사죄확인", "헌금기도", "축도"] else "다같이"
        # 신앙고백의 경우 "사도신경 다같이" -> "다같이"로 정리
        participant = line if line else default_participant
        if section == "신앙고백" and "사도신경" in participant:
            participant = "다같이"
        return {
            "label": section,
            "participant": participant
        }

    return None


def get_template_order() -> list:
    """기본 예배 순서 템플릿"""
    return [
        {"label": "예배로 부름", "participant": "인도자"},
        {"label": "송영", "participant": "찬양대"},
        {"label": "기도", "participant": "인도자"},
        {"label": "찬송", "hymn": {"number": 0, "title": "", "image": "", "verifiedTitle": "", "verificationStatus": "PENDING"}, "participant": "일어서서"},
        {"label": "참회기도", "participant": "다같이"},
        {"label": "사죄확인", "participant": "인도자"},
        {"label": "신앙고백", "name": "사도신경", "participant": "다같이"},
        {"label": "성시교독", "number": 0, "reference": "", "reading": {"lines": [], "number": 0, "reference": "", "title": ""}, "participant": "앉아서"},
        {"label": "찬송", "hymn": {"number": 0, "title": "", "image": "", "verifiedTitle": "", "verificationStatus": "PENDING"}, "participant": "다같이"},
        {"label": "기도", "participants": "", "participant": "기도자"},
        {"label": "성경봉독", "reference": "", "verses": [], "participant": "인도자"},
        {"label": "찬양", "items": [], "participant": "찬양대"},
        {"label": "말씀", "title": "", "preacher": "", "participant": "설교자"},
        {"label": "기도", "participant": "설교자"},
        {"label": "찬송", "hymn": {"number": 0, "title": "", "image": "", "verifiedTitle": "", "verificationStatus": "PENDING"}, "participant": "다같이"},
        {"label": "헌금", "hymn": {"number": 0, "title": "", "image": "", "verifiedTitle": "", "verificationStatus": "PENDING"}, "participant": "다같이"},
        {"label": "헌금기도", "participant": "인도자"},
        {"label": "찬송", "hymn": {"number": 0, "title": "", "image": "", "verifiedTitle": "", "verificationStatus": "PENDING"}, "note": "끝절은 일어서서", "participant": "다같이"},
        {"label": "축도", "participant": "설교자"},
        {"label": "송영", "participant": "찬양대"}
    ]


def build_default_order(parsed_items: list, full_text: str) -> list:
    """기본 템플릿에 파싱된 내용 병합 - 파싱된 항목으로 빈 템플릿 채우기"""
    template = get_template_order()
    
    # 각 레이블별로 파싱된 항목들을 인덱스별로 그룹화
    parsed_by_label = {}
    for item in parsed_items:
        label = item.get("label")
        if label not in parsed_by_label:
            parsed_by_label[label] = []
        parsed_by_label[label].append(item)
    
    # 템플릿의 각 항목을 순회하며 파싱된 내용으로 채움
    label_counters = {label: 0 for label in parsed_by_label.keys()}
    
    for t in template:
        label = t.get("label")
        if label in parsed_by_label and label_counters[label] < len(parsed_by_label[label]):
            parsed_item = parsed_by_label[label][label_counters[label]]
            label_counters[label] += 1
            
            # 템플릿 항목 업데이트
            if label == "찬송" and "hymn" in parsed_item:
                t["hymn"] = parsed_item["hymn"]
                if "participant" in parsed_item:
                    t["participant"] = parsed_item["participant"]
            elif label == "성시교독":
                t.update(parsed_item)
            elif label == "성경봉독":
                t.update(parsed_item)
            elif label == "말씀":
                t.update(parsed_item)
            elif label == "찬양":
                t["items"] = parsed_item.get("items", t.get("items", []))
            elif label == "기도":
                # 기도 참여자 업데이트
                if "participant" in parsed_item:
                    t["participant"] = parsed_item["participant"]
            else:
                # 기타 항목은 participant만 업데이트
                if "participant" in parsed_item:
                    t["participant"] = parsed_item["participant"]
    
    return template


# ──────────────────────────────────────────────
# 데이터 보강
# ──────────────────────────────────────────────
def enrich_with_bible_data(bulletin_data: dict) -> dict:
    """성경 데이터로 성경봉독 구절 채우기"""
    # SQLite DB 경로 (프로젝트 루트의 work/bible/data/bible_data.sqlite3)
    db_path = Path(r"C:\Users\chajh\Documents\Codex\2026-09-06\referenced-chatgpt-conversation-this-is-an\work\bible\data\bible_data.sqlite3")
    if not db_path.exists():
        log(f"성경 DB를 찾을 수 없습니다: {db_path}")
        return bulletin_data

    for service in bulletin_data.get("services", []):
        for item in service.get("order", []):
            if item.get("label") == "성경봉독" and item.get("reference"):
                verses = fetch_bible_verses(db_path.parent, item["reference"])
                if verses:
                    item["verses"] = verses
                    log(f"성경 구절 채움: {item['reference']} -> {len(verses)}절")
    return bulletin_data


def fetch_bible_verses(bible_dir: Path, reference: str) -> list:
    """성경 DB에서 구절 가져오기 (bible.py SQLite 사용)"""
    bible_py_path = Path(r"C:\Users\chajh\Documents\Codex\2026-09-06\referenced-chatgpt-conversation-this-is-an\work\bible\bible.py")
    if not bible_py_path.exists():
        log(f"bible.py를 찾을 수 없습니다: {bible_py_path}")
        return []
    
    try:
        import sys
        sys.path.insert(0, str(bible_py_path.parent))
        import bible
        
        # 참조 파싱 - bible.py의 parse_reference 사용
        ref = bible.parse_reference(reference)
        if not ref:
            log(f"성경 참조 파싱 실패: {reference}")
            return []
        
        book_abbr, chap, v1, v2 = ref
        
        # SQLite에서 데이터 로드
        data = bible.load_data()
        results = bible.search_by_reference(data, book_abbr, chap, v1, v2)
        
        # 전체 책 이름 찾기
        book_full = bible.BOOK_FULL_NAMES.get(book_abbr, book_abbr)
        
        verses = []
        for r in results:
            verses.append({
                "reference": f"{book_full} {r['chapter']}:{r['verse']}",
                "book": book_full[0],
                "chapter": r['chapter'],
                "verse": r['verse'],
                "content": r['content']
            })
        return verses
        
    except Exception as e:
        log(f"성경 데이터 읽기 실패 (bible.py): {e}")
        return []


def enrich_with_hymn_images(bulletin_data: dict) -> tuple[dict, set]:
    """찬송가 이미지 확인"""
    used_hymns = set()

    for service in bulletin_data.get("services", []):
        for item in service.get("order", []):
            hymn = item.get("hymn", {})
            num = hymn.get("number")
            if not num:
                continue
            used_hymns.add(num)

            for ext in [".jpg", ".png", ".jpeg"]:
                src = ASSETS_HYMNS_DIR / f"{num:03d}{ext}"
                if not src.exists():
                    src = ASSETS_HYMNS_DIR / f"{num}{ext}"
                if src.exists():
                    hymn["image"] = f"assets/hymns/{src.name}"
                    hymn["verificationStatus"] = "MATCH"
                    break

    return bulletin_data, used_hymns


def enrich_with_responsive_readings(bulletin_data: dict) -> dict:
    """교독문 데이터 채우기"""
    readings_file = Path(r"C:\Users\chajh\Documents\Codex\2026-09-06\referenced-chatgpt-conversation-this-is-an\outputs\responsive_readings_1-137.json")
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

        # items 배열에서 number로 찾기
        readings_map = {item["number"]: item for item in readings_data.get("items", [])}

        for service in bulletin_data.get("services", []):
            for item in service.get("order", []):
                if item.get("label") == "성시교독" and item.get("number"):
                    num = item["number"]
                    reading = readings_map.get(num)
                    if reading:
                        item["reading"] = reading
                        log(f"교독문 {num}번 데이터 채움")
    except Exception as e:
        log(f"교독문 데이터 읽기 실패: {e}")

    return bulletin_data


def apply_time_overrides(bulletin_data: dict, full_text: str) -> dict:
    """시간별 예배 차이 적용 - 기도자/찬양 곡을 시간대별로 순서 매핑"""
    for service in bulletin_data.get("services", []):
        times = service.get("times", [])
        time_overrides = {}
        
        # 찬양 곡 리스트 추출 (첫 번째 찬양 항목에서)
        praise_items = []
        for item in service.get("order", []):
            if item.get("label") == "찬양" and item.get("items"):
                praise_items = item["items"]
                break
        
        # 기도자 리스트 추출 (기도 항목에서 · 또는 , 로 구분된 이름들)
        prayer_names = []
        for item in service.get("order", []):
            if item.get("label") == "기도" and item.get("participant"):
                participant = item["participant"]
                # "기도 강종원 · 이한웅 장로 · 한정운 목사 · 홍석빈 장로 · 박미정 대학부 부감" 형태
                # "기도 " 접두사 제거
                if participant.startswith("기도"):
                    participant = participant[2:].strip()
                # · , 으로 분리
                prayer_names = [name.strip() for name in re.split(r"[·,]", participant) if name.strip()]
                break
        
        for i, time_str in enumerate(times):
            time_overrides[time_str] = {"prayer": "", "praise": []}
            escaped_time = re.escape(time_str)

            # 기도자 순서대로 할당
            if prayer_names and i < len(prayer_names):
                time_overrides[time_str]["prayer"] = prayer_names[i]
            else:
                # 텍스트에서 시간대별 기도자 찾기 시도 (fallback)
                pattern = rf"{escaped_time}.*?(?:기도자|기도)[:\s]*([^\n]+)"
                match = re.search(pattern, full_text)
                if match:
                    time_overrides[time_str]["prayer"] = match.group(1).strip()

            # 찬양대 찾기 - 텍스트에서 찾기 시도
            pattern2 = rf"{escaped_time}.*?(?:찬양|찬양대)[:\s]*([^\n]+)"
            match2 = re.search(pattern2, full_text)
            if match2:
                time_overrides[time_str]["praise"] = [match2.group(1).strip()]
            # 텍스트에 없으면 찬양 곡 리스트에서 순서대로 할당
            elif praise_items and i < len(praise_items):
                time_overrides[time_str]["praise"] = [praise_items[i]]

        service["timeOverrides"] = time_overrides

    return bulletin_data


# ──────────────────────────────────────────────
# 검증 및 저장
# ──────────────────────────────────────────────
def validate_bulletin(bulletin_data: dict) -> dict:
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

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def save_bulletin(bulletin_data: dict, issue_date: str) -> Path:
    """주보 JSON 저장"""
    filename = f"{issue_date}.json"
    filepath = BULLETINS_DIR / filename
    BULLETINS_DIR.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(bulletin_data, f, ensure_ascii=False, indent=2)
    log(f"주보 저장: {filepath}")

    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(bulletin_data, f, ensure_ascii=False, indent=2)
    log(f"최신 주보 업데이트: {LATEST_JSON}")

    update_index_json(issue_date, filename, bulletin_data)

    return filepath


def update_index_json(issue_date: str, filename: str, bulletin_data: dict) -> None:
    """bulletins/index.json 업데이트"""
    index_path = BULLETINS_DIR / "index.json"

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    except Exception:
        index = []

    index = [item for item in index if item.get("date") != issue_date]
    # YYYY-MM-DD -> YYYY년 MM월 DD일
    parts = issue_date.split("-")
    label = f"{parts[0]}년 {int(parts[1]):02d}월 {int(parts[2]):02d}일 · 제{bulletin_data.get('bulletinNumber', '?')}호"
    index.insert(0, {"date": issue_date, "file": filename, "label": label})
    index = index[:20]

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    log(f"인덱스 업데이트: {index_path}")


def copy_hymn_images(used_hymns: set) -> None:
    """사용된 찬송가 이미지 확인"""
    log(f"사용된 찬송가: {sorted(used_hymns)}")


# ──────────────────────────────────────────────
# Git 연동
# ──────────────────────────────────────────────
def git_commit_and_push(issue_date: str, changed_files: list[str]) -> bool:
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


# ──────────────────────────────────────────────
# 이미지 기반 추출 (LM Studio olmocr)
# ──────────────────────────────────────────────
def extract_bulletin_from_image(img_b64: str, issue_date: str, bulletin_number: int, pdf_url: str) -> dict | None:
    """주보 이미지에서 텍스트 추출 (LM Studio olmocr-2-7b OCR), 파싱은 parse_bulletin_text로 처리"""
    if not LM_STUDIO_ENABLED:
        log("LM Studio 비활성화됨 (LM_STUDIO_ENABLED=false), 이미지 분석 건너뜀")
        return None

    log("주보 이미지 OCR 중... (LM Studio olmocr-2-7b 호출)")

    prompt = """이 소망교회 주보 이미지에서 모든 텍스트를 순서대로 추출해줘.

주보에 있는 모든 텍스트를 있는 그대로 출력해줘:
- 예배 순서 (예배로 부름, 송영, 기도, 찬송, 참회기도, 사죄확인, 신앙고백, 성시교독, 성경봉독, 찬양, 말씀, 헌금, 헌금기도, 축도, 송영 등)
- 각 순서의 참여자, 찬송가 번호/제목, 교독문 번호, 성경 구절, 설교 제목/설교자
- 예배 인도자, 시간별 정보 (07:30, 09:30, 11:30, 13:30, 15:30)
- 다음 주 기도자

텍스트만 순서대로 나열해줘. JSON 형식 불필요, 마크다운 불필요."""

    try:
        resp = requests.post(
            LM_STUDIO_URL,
            headers={"Content-Type": "application/json"},
            json={
                "model": LM_STUDIO_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                    ]
                }],
                "temperature": 0.0,
                "max_tokens": 8000
            },
            timeout=180
        )

        if resp.status_code != 200:
            log(f"LM Studio 요청 실패: {resp.status_code} - {resp.text}")
            return None

        content = resp.json()["choices"][0]["message"]["content"]
        log(f"LM Studio OCR 완료 ({len(content)} 문자)")
        log(f"OCR 원본 내용: {content[:1000]}")

        # OCR 텍스트에서 주보 번호 추출 (제 XXXX 호)
        ocr_bulletin_number = bulletin_number
        ocr_match = re.search(r"제\s*(\d+)\s*호", content)
        if ocr_match:
            ocr_bulletin_number = int(ocr_match.group(1))
            log(f"OCR에서 주보 번호 추출: 제 {ocr_bulletin_number} 호")

        # 추출된 텍스트를 기존 파싱 함수로 처리
        parsed = parse_bulletin_text(content)
        bulletin_data = {
            "issueDate": issue_date,
            "bulletinNumber": ocr_bulletin_number,
            "sourcePdf": pdf_url,
            "page": 1,
            "services": parsed["services"],
            "nextWeekPrayer": parsed.get("next_week_prayer", "")
        }
        return bulletin_data

    except Exception as e:
        log(f"LM Studio 호출 실패: {e}")
        return None


# ──────────────────────────────────────────────
# 메인 플로우
# ──────────────────────────────────────────────
def main() -> int:
    log("=== 주보 자동 업데이트 시작 ===")

    temp_files: list[Path] = []

    try:
        info = get_latest_bulletin_info()
        issue_date = info["issue_date"]

        if LATEST_JSON.exists():
            with open(LATEST_JSON, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("issueDate") == issue_date:
                log(f"이미 최신 주보({issue_date})가 저장되어 있습니다. 작업 중단.")
                return 0

        pdf_path = BASE_DIR / f"temp_{issue_date}.pdf"
        temp_files.append(pdf_path)
        download_pdf(info["pdf_url"], pdf_path)

        text = extract_pdf_first_page_text(pdf_path)
        img_path = BASE_DIR / f"temp_{issue_date}_page1.png"
        temp_files.append(img_path)
        extract_pdf_first_page_image(pdf_path, img_path)

        use_image_fallback = not text or len(text) < 100

        if use_image_fallback:
            log("텍스트 추출량 부족 → 이미지 기반 분석 시도")
            bulletin_data = None
            if img_path.exists():
                with open(img_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                bulletin_data = extract_bulletin_from_image(img_b64, issue_date, info["bulletin_number"], info["pdf_url"])

            if not bulletin_data:
                log("이미지 분석 실패: 기존 latest.json 유지, 수동 검수 필요")
                for tf in temp_files:
                    safe_unlink(tf)
                return 1

            bulletin_data = enrich_with_bible_data(bulletin_data)
            bulletin_data, used_hymns = enrich_with_hymn_images(bulletin_data)
            bulletin_data = enrich_with_responsive_readings(bulletin_data)
            bulletin_data = apply_time_overrides(bulletin_data, "")

        else:
            parsed = parse_bulletin_text(text)
            bulletin_data = {
                "issueDate": issue_date,
                "bulletinNumber": info["bulletin_number"],
                "sourcePdf": info["pdf_url"],
                "page": 1,
                "services": parsed["services"],
                "nextWeekPrayer": parsed.get("next_week_prayer", "")
            }

            bulletin_data = enrich_with_bible_data(bulletin_data)
            bulletin_data, used_hymns = enrich_with_hymn_images(bulletin_data)
            bulletin_data = enrich_with_responsive_readings(bulletin_data)
            bulletin_data = apply_time_overrides(bulletin_data, text)

        validation = validate_bulletin(bulletin_data)
        log(f"검증 결과: valid={validation['valid']}, errors={len(validation['errors'])}, warnings={len(validation['warnings'])}")
        for e in validation["errors"]:
            log(f"  ERROR: {e}")
        for w in validation["warnings"]:
            log(f"  WARNING: {w}")

        if not validation["valid"]:
            log("검증 실패: 기존 latest.json 유지, 수동 검수 필요")
            for tf in temp_files:
                safe_unlink(tf)
            return 1

        saved_file = save_bulletin(bulletin_data, issue_date)
        copy_hymn_images(used_hymns)

        changed_files = [
            str(saved_file.relative_to(BASE_DIR)),
            str(LATEST_JSON.relative_to(BASE_DIR)),
            "data/bulletins/index.json"
        ]
        deployed = git_commit_and_push(issue_date, changed_files)

        for tf in temp_files:
            safe_unlink(tf)

        log("=== 작업 완료 ===")
        log(f"주보 날짜: {issue_date}")
        log(f"변경된 파일: {', '.join(changed_files)}")
        log(f"검증: {'성공' if validation['valid'] else '실패'} (에러 {len(validation['errors'])}개, 경고 {len(validation['warnings'])}개)")
        log(f"GitHub Pages 배포: {'예' if deployed else '아니오'}")

        return 0 if validation["valid"] else 1

    except Exception as e:
        log(f"작업 실패: {e}")
        import traceback
        traceback.print_exc()
        for tf in temp_files:
            safe_unlink(tf)
        return 1


if __name__ == "__main__":
    sys.exit(main())
