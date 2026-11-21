import pymupdf
import base64
import requests
import json
import os
import sys

# PyMuPDF로 PDF에서 이미지 다시 생성 (해상도 낮추기)
pdf_path = "temp_2026-11-08.pdf"
page_num = 0
zoom = 2  # 72dpi * 2 = 144dpi (원본 72dpi에서 시작)

doc = pymupdf.open(pdf_path)
page = doc[page_num]
mat = pymupdf.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat)

resized_path = "temp_2026-11-08_page1_144dpi.png"
pix.save(resized_path)
print(f"Saved resized image: {resized_path} ({pix.width}x{pix.height})")

doc.close()

# base64 인코딩
with open(resized_path, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode('utf-8')

payload_json = {
    "model": "allenai/olmocr-2-7b",
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": "Extract all Korean text from this church bulletin image. Include all times (07:30, 09:30, 11:30, 13:30, 15:30), pastor names, hymn numbers with Korean titles, sermon titles, and biblical readings."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
        ]
    }],
    "temperature": 0,
    "max_tokens": 8000
}

headers = {"Content-Type": "application/json"}

try:
    resp = requests.post("http://localhost:1234/v1/chat/completions", json=payload_json, headers=headers, timeout=300)
    result = resp.json()
    
    if 'choices' in result and len(result['choices']) > 0:
        content = result['choices'][0]['message']['content']
        print("=== OCR RESULT ===")
        print(content)
        
        output_path = "C:/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/work/tmp/extracted_20261108.txt"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\nExtracted text saved to: {output_path}")
    else:
        print("Error: No choices in response", json.dumps(result, indent=2))
        sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
