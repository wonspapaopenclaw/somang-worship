#!/usr/bin/env python3
"""
소망교회 주보 자동 업데이트 스크립트
매주 금요일 오후 8시 15분 실행
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from pdf2image import convert_from_path
from pdfminer.high_level import extract_text
from PIL import Image

# 설정
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
BULLETINS_DIR = DATA_DIR / "bulletins"
ASSETS_HYMNS_DIR = BASE_DIR / "assets" / "hymns"
LATEST_JSON = DATA_DIR / "latest.json"

# 소망교회 주보 페이지
JUBO_URL = "https://somang.net/worship/info/jubo/"

# 세션 설정
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def get_latest_bulletin_info():
    """최신 주보 게시글 정보 가져오기"""
    log("주보 목록 페이지 요청 중...")
    resp = session.get(JUBO_URL, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # 첫 번째 게시글 (최신) 찾기
    # KBoard 리스트에서 첫 번째 항목
    first_item = soup.select_one(".kboard-list .kboard-list-item:first-child, .kboard-list table tbody tr:first-child")
    if not first_item:
        # 대체 셀렉터
        first_item = soup.select_one("tbody tr:first-child")

    if not first_item:
        raise Exception("주보 게시글을 찾을 수 없습니다")

    # 제목에서 날짜 추출
    title_elem = first_item.select_one(".kboard-title a, td.kboard-title a, a[href*='kboard_file_download']")
    if not title_elem:
        title_elem = first_item.select_one("a[href*='uid=']")

    if not title_elem:
        raise Exception("주보 제목을 찾을 수 없습니다")

    title_text = title_elem.get_text(strip=True)
    log(f"최신 주보 제목: {title_text}")

    # 날짜 추출 (예: "2026년 9월 13일 no.1239")
    date_match = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", title_text)
    if not date_match:
        raise Exception("날짜를 파싱할 수 없습니다")

    year, month, day = date_match.groups()
    issue_date = f"{year}-{int(month):02d}-{int(day):02d}"

    # 주보 번호 추출
    number_match = re.search(r"no\.(\d+)", title_text)
    bulletin_number = int(number_match.group(1)) if number_match else None

    # PDF 다운로드 링크
    pdf_link = title_elem.get("href", "")
    if not pdf_link.startswith("http"):
        pdf_link = "https://somang.net" + pdf_link

    log(f"주보 날짜: {issue_date}, 번호: {bulletin_number}")
    log(f"PDF 링크: {pdf_link}")

    return {
        "issue_date": issue_date,
        "bulletin_number": bulletin_number,
        "pdf_url": pdf_link,
        "title": title_text
    }


def download_pdf(pdf_url, save_path):
    """PDF 다운로드"""
    log(f"PDF 다운로드 중: {pdf_url}")
    resp = session.get(pdf_url, timeout=60, stream=True)
    resp.raise_for_status()

    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    log(f"PDF 저장 완료: {save_path} ({save_path.stat().st_size} bytes)")
    return save_path


def extract_pdf_first_page_text(pdf_path):
    """PDF 1페이지 텍스트 추출 (pdfminer)"""
    log("PDF 텍스트 추출 중...")
    try:
        text = extract_text(str(pdf_path), page_numbers=[0])
        return text.strip()
    except Exception as e:
        log(f"pdfminer 텍스트 추출 실패: {e}")
        return ""


def extract_pdf_first_page_image(pdf_path, save_path):
    """PDF 1페이지를 이미지로 변환"""
    log("PDF 1페이지 이미지 변환 중...")
    try:
        images = convert_from_path(str(pdf_path), first_page=1, last_page=1, dpi=200)
        if images:
            images[0].save(save_path, "PNG")
            log(f"이미지 저장 완료: {save_path}")
            return save_path
    except Exception as e:
        log(f"이미지 변환 실패: {e}")
    return None


def parse_bulletin_text(text):
    """주보 텍스트에서 정보 파싱"""
    log("주보 텍스트 파싱 중...")

    result = {
        "services": [],
        "next_week_prayer": ""
    }

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # 주일예배 정보 찾기
    service = {
        "name": "주일예배",
        "times": ["07:30", "09:30", "11:30", "13:30", "15:30"],
        "leader": "",
        "order": [],
        "timeOverrides": {}
    }

    current_section = None
    i = 0
    while i < len(lines):
        line = lines[i]

        # 예배 인도자
        if "인도" in line and "목사" in line and not service["leader"]:
            service["leader"] = line
            i += 1
            continue

        # 순서 파싱
        if any(keyword in line for keyword in ["예배로 부름", "송영", "기도", "찬송", "참회기도", "사죄확인", "신앙고백", "성시교독", "성경봉독", "찬양", "말씀", "헌금", "헌금기도", "축도"]):
            current_section = line
            i += 1
            continue

        # 구체적인 내용 파싱
        if current_section:
            if "기도자" in current_section or current_section == "기도":
                # 기도자 정보
                pass
            elif "찬송" in current_section:
                # 찬송가 번호 추출
                hymn_match = re.search(r"(\d+)장\s*(.+)", line)
                if hymn_match:
                    num = int(hymn_match.group(1))
                    title = hymn_match.group(2).strip()
                    # 찬송가 이미지 확인
                    img_file = ASSETS_HYMNS_DIR / f"{num:03d}.jpg"
                    if not img_file.exists():
                        img_file = ASSETS_HYMNS_DIR / f"{num}.jpg"

                    service["order"].append({
                        "label": "찬송",
                        "hymn": {
                            "number": num,
                            "title": title,
                            "image": f"assets/hymns/{img_file.name}" if img_file.exists() else "",
                            "verifiedTitle": title,
                            "verificationStatus": "MATCH" if img_file.exists() else "MISSING"
                        },
                        "participant": "다같이"
                    })
            elif "성시교독" in current_section:
                # 교독문 번호
                reading_match = re.search(r"(\d+)번?\s*(.+)", line)
                if reading_match:
                    num = int(reading_match.group(1))
                    ref = reading_match.group(2).strip()
                    service["order"].append({
                        "label": "성시교독",
                        "number": num,
                        "reference": ref,
                        "reading": {"number": num, "reference": ref, "title": ref, "lines": []},
                        "participant": "앉아서"
                    })
            elif "성경봉독" in current_section:
                # 성경 구절
                verse_match = re.search(r"([가-힣]+)\s*(\d+):(\d+)[-–](\d+)", line)
                if verse_match:
                    book, chap, v1, v2 = verse_match.groups()
                    service["order"].append({
                        "label": "성경봉독",
                        "reference": f"{book} {chap}:{v1}-{v2}",
                        "verses": [],
                        "participant": "인도자"
                    })
            elif "말씀" in current_section or "설교" in current_section:
                # 설교 제목
                service["order"].append({
                    "label": "말씀",
                    "title": line,
                    "preacher": service["leader"],
                    "participant": "설교자"
                })
            elif "찬양" in current_section:
                # 찬양 곡목
                service["order"].append({
                    "label": "찬양",
                    "items": [line],
                    "participant": "찬양대"
                })

            current_section = None

        i += 1

    # 기본 순서 템플릿 적용 (파싱된 내용으로 보완)
    service["order"] = build_default_order(service["order"], text)

    result["services"] = [service]

    # 다음 주 기도자
    next_prayer_match = re.search(r"다음\s*주\s*기도자?[:\s]*(.+)", text)
    if next_prayer_match:
        result["next_week_prayer"] = next_prayer_match.group(1).strip()

    return result


def build_default_order(parsed_items, full_text):
    """기본 예배 순서 템플릿에 파싱된 내용 병합"""
    # 기존 latest.json의 구조를 템플릿으로 사용
    template = get_template_order()

    # 파싱된 항목으로 업데이트
    for item in parsed_items:
        label = item.get("label")
        if label == "찬송" and "hymn" in item:
            # 찬송가 업데이트
            for t in template:
                if t.get("label") == "찬송" and t.get("hymn", {}).get("number") == item["hymn"]["number"]:
                    t["hymn"] = item["hymn"]
                    break
        elif label == "성시교독":
            for t in template:
                if t.get("label") == "성시교독" and t.get("number") == item.get("number"):
                    t.update(item)
                    break
        elif label == "성경봉독":
            for t in template:
                if t.get("label") == "성경봉독":
                    t.update(item)
                    break
        elif label == "말씀":
            for t in template:
                if t.get("label") == "말씀":
                    t.update(item)
                    break
        elif label == "찬양":
            for t in template:
                if t.get("label") == "찬양":
                    t["items"] = item.get("items", t.get("items", []))
                    break

    return template


def get_template_order():
    """기본 예배 순서 템플릿 반환"""
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


def enrich_with_bible_data(bulletin_data):
    """성경 데이터로 성경봉독 구절 채우기"""
    bible_dir = BASE_DIR / "work" / "bible"
    if not bible_dir.exists():
        log("성경 데이터 폴더가 없습니다. 건너뜀.")
        return bulletin_data

    for service in bulletin_data.get("services", []):
        for item in service.get("order", []):
            if item.get("label") == "성경봉독" and item.get("reference"):
                # reference 예: "요한복음 4:49-53"
                ref = item["reference"]
                verses = fetch_bible_verses(bible_dir, ref)
                if verses:
                    item["verses"] = verses
                    log(f"성경 구절 채움: {ref} -> {len(verses)}절")

    return bulletin_data


def fetch_bible_verses(bible_dir, reference):
    """성경 파일에서 구절 가져오기"""
    # 간단한 구현: 참조 파싱하여 해당 파일에서 읽기
    match = re.search(r"([가-힣]+)\s*(\d+):(\d+)[-–](\d+)", reference)
    if not match:
        return []

    book, chap, v1, v2 = match.groups()
    chap, v1, v2 = int(chap), int(v1), int(v2)

    # 성경 파일 찾기 (예: john.json, genesis.json 등)
    book_map = {
        "요한복음": "john", "요": "john",
        "창세기": "genesis", "창": "genesis",
        # 필요시 추가
    }

    book_key = book_map.get(book, book.lower())
    bible_file = bible_dir / f"{book_key}.json"

    if not bible_file.exists():
        # 다른 파일명 시도
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
            if item.get("hymn", {}).get("number"):
                num = item["hymn"]["number"]
                used_hymns.add(num)

                # 이미지 파일 확인
                for ext in [".jpg", ".png", ".jpeg"]:
                    src = ASSETS_HYMNS_DIR / f"{num:03d}{ext}"
                    if not src.exists():
                        src = ASSETS_HYMNS_DIR / f"{num}{ext}"
                    if src.exists():
                        item["hymn"]["image"] = f"assets/hymns/{src.name}"
                        item["hymn"]["verificationStatus"] = "MATCH"
                        break

    return bulletin_data, used_hymns


def enrich_with_responsive_readings(bulletin_data):
    """교독문 데이터 채우기"""
    readings_file = BASE_DIR / "work" / "responsive_readings.json"
    if not readings_file.exists():
        # 대체 위치 찾기
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


def apply_time_overrides(bulletin_data, full_text):
    """시간별 예배 차이 적용 (기도자, 찬양대)"""
    # 기존 latest.json에서 timeOverrides 패턴 참조
    # 텍스트에서 시간별 정보 추출 시도
    time_overrides = {}

    for service in bulletin_data.get("services", []):
        for time_str in service.get("times", []):
            time_overrides[time_str] = {"prayer": "", "praise": []}

        # 텍스트에서 "07:30", "09:30" 등 시간대별 기도자/찬양 찾기
        for time_str in service.get("times", []):
            pattern = rf"{time_str}.*?(?:기도자|기도)[:\s]*([^\n]+)"
            match = re.search(pattern, full_text)
            if match:
                time_overrides[time_str]["prayer"] = match.group(1).strip()

            pattern = rf"{time_str}.*?(?:찬양|찬양대)[:\s]*([^\n]+)"
            match = re.search(pattern, full_text)
            if match:
                time_overrides[time_str]["praise"] = [match.group(1).strip()]

        service["timeOverrides"] = time_overrides

    return bulletin_data


def validate_bulletin(bulletin_data):
    """주보 데이터 검증"""
    errors = []
    warnings = []

    # 필수 필드 검사
    required_fields = ["issueDate", "bulletinNumber", "services"]
    for field in required_fields:
        if not bulletin_data.get(field):
            errors.append(f"필수 필드 누락: {field}")

    for service in bulletin_data.get("services", []):
        # 예배 시간
        if not service.get("times"):
            errors.append("예배 시간이 없습니다")
        # 인도자
        if not service.get("leader"):
            warnings.append("예배 인도자가 없습니다")
        # 순서 검사
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
    # data/bulletins/YYYY-MM-DD.json
    filename = f"{issue_date}.json"
    filepath = BULLETINS_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(bulletin_data, f, ensure_ascii=False, indent=2)
    log(f"주보 저장: {filepath}")

    # data/latest.json 업데이트
    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(bulletin_data, f, ensure_ascii=False, indent=2)
    log(f"최신 주보 업데이트: {LATEST_JSON}")

    # index.json 업데이트
    update_index_json(issue_date, filename)

    return filepath


def update_index_json(issue_date, filename):
    """bulletins/index.json 업데이트"""
    index_path = BULLETINS_DIR / "index.json"

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    except:
        index = []

    # 중복 제거 후 맨 앞에 추가
    index = [item for item in index if item.get("date") != issue_date]
    label = f"{issue_date.replace('-', '년 ').replace('-', '월 ')}일 · 제{bulletin_data.get('bulletinNumber', '?')}호"
    index.insert(0, {"date": issue_date, "file": filename, "label": label})

    # 최대 20개만 유지
    index = index[:20]

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    log(f"인덱스 업데이트: {index_path}")


def copy_hymn_images(used_hymns):
    """사용된 찬송가 이미지만 assets/hymns/에 확보 (이미 있으면 건너뜀)"""
    log(f"사용된 찬송가: {sorted(used_hymns)}")
    # 이미 assets/hymns에 있으므로 별도 복사 불필요
    # 필요시 외부 소스에서 가져오는 로직 추가 가능
    pass


def git_commit_and_push(issue_date, changed_files):
    """Git 커밋 및 푸시"""
    try:
        os.chdir(BASE_DIR)

        # git status 확인
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not result.stdout.strip():
            log("변경사항 없음, 커밋 생략")
            return False

        # git add
        for f in changed_files:
            subprocess.run(["git", "add", f], check=True)

        # git commit
        commit_msg = f"주보 업데이트: {issue_date}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        log(f"커밋 완료: {commit_msg}")

        # git push
        subprocess.run(["git", "push"], check=True)
        log("푸시 완료 - GitHub Pages 배포 트리거됨")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Git 작업 실패: {e}")
        return False


def main():
    log("=== 주보 자동 업데이트 시작 ===")

    try:
        # 1. 최신 주보 정보 가져오기
        info = get_latest_bulletin_info()
        issue_date = info["issue_date"]

        # 이미 최신 주보가 저장되어 있는지 확인
        if LATEST_JSON.exists():
            with open(LATEST_JSON, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("issueDate") == issue_date:
                log(f"이미 최신 주보({issue_date})가 저장되어 있습니다. 작업 중단.")
                return 0

        # 2. PDF 다운로드
        pdf_path = BASE_DIR / f"temp_{issue_date}.pdf"
        download_pdf(info["pdf_url"], pdf_path)

        # 3. PDF 1페이지 텍스트/이미지 추출
        text = extract_pdf_first_page_text(pdf_path)
        img_path = BASE_DIR / f"temp_{issue_date}_page1.png"
        extract_pdf_first_page_image(pdf_path, img_path)

        if not text or len(text) < 100:
            log("경고: PDF 텍스트 추출량이 적습니다. OCR 결과가 불확실할 수 있습니다.")
            # 기존 latest.json 유지하고 검수 필요 보고
            log("기존 latest.json을 유지합니다. 수동 검수 필요.")
            pdf_path.unlink(missing_ok=True)
            img_path.unlink(missing_ok=True)
            return 1

        # 4. 텍스트 파싱
        parsed = parse_bulletin_text(text)

        # 5. 기본 데이터 구성
        bulletin_data = {
            "issueDate": issue_date,
            "bulletinNumber": info["bulletin_number"],
            "sourcePdf": info["pdf_url"],
            "page": 1,
            "services": parsed["services"],
            "nextWeekPrayer": parsed.get("next_week_prayer", "")
        }

        # 6. 데이터 보강
        bulletin_data = enrich_with_bible_data(bulletin_data)
        bulletin_data, used_hymns = enrich_with_hymn_images(bulletin_data)
        bulletin_data = enrich_with_responsive_readings(bulletin_data)
        bulletin_data = apply_time_overrides(bulletin_data, text)

        # 7. 검증
        validation = validate_bulletin(bulletin_data)
        log(f"검증 결과: valid={validation['valid']}, errors={len(validation['errors'])}, warnings={len(validation['warnings'])}")

        if validation["errors"]:
            for e in validation["errors"]:
                log(f"  ERROR: {e}")
        for w in validation["warnings"]:
            log(f"  WARNING: {w}")

        if not validation["valid"]:
            log("검증 실패: 기존 latest.json을 유지합니다. 수동 검수 필요.")
            pdf_path.unlink(missing_ok=True)
            img_path.unlink(missing_ok=True)
            return 1

        # 8. 저장
        saved_file = save_bulletin(bulletin_data, issue_date)

        # 9. 찬송가 이미지 확인
        copy_hymn_images(used_hymns)

        # 10. Git 커밋 및 푸시
        changed_files = [str(saved_file.relative_to(BASE_DIR)), str(LATEST_JSON.relative_to(BASE_DIR)), "data/bulletins/index.json"]
        deployed = git_commit_and_push(issue_date, changed_files)

        # 정리
        pdf_path.unlink(missing_ok=True)
        img_path.unlink(missing_ok=True)

        # 결과 요약
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
        return 1


if __name__ == "__main__":
    sys.exit(main())