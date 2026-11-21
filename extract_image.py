#!/usr/bin/env python3
import easyocr
import json
import os
from pathlib import Path

reader = easyocr.Reader(["ko", "en"], gpu=False)

def extract_text_from_image(image_path):
    print(f"이미지에서 텍스트 추출: {image_path}")
    result = reader.readtext(str(image_path), detail=0)
    text = "\n".join(result)
    print(f"추출된 텍스트 길이: {len(text)}자")
    return text

if __name__ == "__main__":
    img_path = Path("temp_2026-11-08_page1.png")
    if img_path.exists():
        text = extract_text_from_image(img_path)
        tmp_dir = Path("/c/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/work/tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        output_path = tmp_dir / "extracted_20261108.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"텍스트 저장 완료: {output_path}")
        print(f"\n추출된 텍스트 (처음 500자):\n{text[:500]}")
    else:
        print(f"이미지 파일이 없습니다: {img_path}")

