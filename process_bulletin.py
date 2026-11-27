#!/usr/bin/env python3
import requests
import fitz
import json
import re
import os
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

BASE_DIR = Path(".")
DATA_DIR = BASE_DIR / "data"
BULLETINS_DIR = DATA_DIR / "bulletins"
LATEST_JSON = DATA_DIR / "latest.json"
JUBO_URL = "https://somang.net/worship/info/jubo/"

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def get_latest_info():
    resp = session.get(JUBO_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    title_elem = soup.select_one(".kboard-title a") or soup.select_one("a[href*='uid=']")
    title_text = title_elem.get_text(strip=True)
    log(f"주보 제목: {title_text}")
    
    date_match = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", title_text)
    year, month, day = date_match.groups()
    issue_date = f"{year}-{int(month):02d}-{int(day):02d}"
    
    number_match = re.search(r"no\.(\d+)", title_text)
    bulletin_number = int(number_match.group(1)) if number_match else None
    
    pdf_link = title_elem.get("href", "")
    if pdf_link and not pdf_link.startswith("http"):
        pdf_link = "https://somang.net" + pdf_link
    
    log(f"주보 날짜: {issue_date}, 번호: {bulletin_number}")
    return {"issue_date": issue_date, "bulletin_number": bulletin_number, "pdf_url": pdf_link}

def download_pdf(pdf_url, save_path):
    log(f"PDF 다운로드: {pdf_url}")
    resp = session.get(pdf_url, timeout=60, stream=True)
    resp.raise_for_status()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    log(f"PDF 저장 완료: {save_path}")

def pdf_to_image(pdf_path, img_path, dpi=300):
    log(f"PDF 이미지 변환 ({dpi}dpi)")
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    pix = page.get_pixmap(dpi=dpi)
    pix.save(str(img_path))
    log(f"이미지 저장 완료: {img_path}")
    doc.close()

def easyocr_extract(img_path):
    log("easyocr 텍스트 추출...")
    reader = easyocr.Reader(['ko', 'en'], gpu=False)
    result = reader.readtext(str(img_path), detail=0)
    text = '\n'.join(result)
    log(f"텍스트 길이: {len(text)}자")
    return text

def save_text(text, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    log(f"텍스트 저장: {output_path}")

if __name__ == "__main__":
    log("=== 주보 처리 시작 ===")
    
    info = get_latest_info()
    issue_date = info["issue_date"]
    
    if LATEST_JSON.exists():
        with open(LATEST_JSON, "r", encoding="utf-8") as f:
            existing = json.load(f)
        if existing.get("issueDate") == issue_date:
            log(f"이미 최신 주보({issue_date})가 있습니다.")
            exit(0)
    
    pdf_path = BASE_DIR / f"temp_{issue_date}.pdf"
    download_pdf(info["pdf_url"], pdf_path)
    
    img_path = BASE_DIR / f"temp_{issue_date}_page1.png"
    pdf_to_image(pdf_path, img_path, dpi=300)
    
    # LM Studio가 활성화된 경우 먼저 시도 (기본 방법), 실패 시 EasyOCR 폴백    if LM_STUDIO_ENABLED:        log("LM Studio OCR 시도 (기본 방법)...")        with open(img_path, "rb") as f:            img_b64 = base64.b64encode(f.read()).decode()        text = extract_bulletin_from_image(img_b64, issue_date, info["bulletin_number"], info["pdf_url"])        if not text:            log("LM Studio OCR 실패, EasyOCR으로 폴백...")            text = easyocr_extract(img_path)    else:        text = easyocr_extract(img_path)    tmp_dir = Path("/c/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/work/tmp")    text_path = tmp_dir / f"extracted_{issue_date.replace('-', '')}.txt"    save_text(text, text_path)    log(f"=== 추출 텍스트 미리보기 ===")    print(text[:1500])    os.unlink(pdf_path)    os.unlink(img_path)    log("임시 파일 삭제 완료")