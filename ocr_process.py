import base64
import requests
import json
import os
import sys

img_path = "C:/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/outputs/github-pages/somang-worship/temp_2026-11-08_page1.png"
output_path = "C:/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/work/tmp/extracted_20261108.txt"

# Read and encode image
with open(img_path, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode('utf-8')

# LLM API call
payload = {
    "model": "allenai/olmocr-2-7b",
    "messages": [{
        "role": "user",
        "content": "Extract all Korean text from this church bulletin image. List all times, pastor information, hymn numbers with titles, sermon titles, and biblical readings."
    }],
    "temperature": 0,
    "max_tokens": 8000
}

headers = {"Content-Type": "application/json"}

# For image, we need to send it differently - LM Studio may have specific endpoint
# Let's try the completions endpoint with image_url
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

try:
    resp = requests.post("http://localhost:1234/v1/chat/completions", json=payload_json, headers=headers, timeout=120)
    result = resp.json()
    
    if 'choices' in result and len(result['choices']) > 0:
        content = result['choices'][0]['message']['content']
        print("=== OCR RESULT ===")
        print(content)
        
        # Save extracted text
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\nExtracted text saved to: {output_path}")
    else:
        print("Error: No choices in response", result)
        sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
