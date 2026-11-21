import pymupdf  # PyMuPDF
import base64
import requests
import json
import os
import sys

# 이미지 리사이즈 및 OCR
img_path = "temp_2026-11-08_page1.png"
output_path = "C:/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/work/tmp/extracted_20261108.txt"

# Pillow로 이미지 리사이즈 시도
try:
    from PIL import Image
    
    img = Image.open(img_path)
    # 50%로 축소
    new_size = (img.width // 2, img.height // 2)
    img_resized = img.resize(new_size, Image.LANCZOS)
    resized_path = "temp_2026-11-08_page1_resized.png"
    img_resized.save(resized_path, quality=85)
    print(f"Image resized to {new_size}")
    
    # base64 인코딩
    with open(resized_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')
    
    payload_json = {
        "model": "allenai/olmocr-2-7b",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Extract all Korean text from this church bulletin image. Include all times, pastor names, hymn numbers and titles, sermon titles, and biblical readings."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
            ]
        }],
        "temperature": 0,
        "max_tokens": 8000
    }
    
    headers = {"Content-Type": "application/json"}
    
    resp = requests.post("http://localhost:1234/v1/chat/completions", json=payload_json, headers=headers, timeout=180)
    result = resp.json()
    
    if 'choices' in result and len(result['choices']) > 0:
        content = result['choices'][0]['message']['content']
        print("=== OCR RESULT ===")
        print(content)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\nExtracted text saved to: {output_path}")
    else:
        print("Error: No choices in response", result)
        sys.exit(1)
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
