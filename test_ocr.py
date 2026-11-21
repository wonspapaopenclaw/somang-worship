import pymupdf as fitz
import easyocr
from pathlib import Path

img_path = Path('temp_2026-11-11_page1.png')
print(f'이미지 존재: {img_path.exists()}')

if img_path.exists():
    print('easyocr 텍스트 추출 시작...')
    reader = easyocr.Reader(['ko', 'en'], gpu=False)
    result = reader.readtext(str(img_path), detail=0)
    text = '\n'.join(result)
    print(f'추출된 텍스트 길이: {len(text)}자')
    print('텍스트 미리보기:')
    print(text[:1000])
    
    tmp_dir = Path('/c/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/work/tmp')
    tmp_dir.mkdir(parents=True, exist_ok=True)
    output = tmp_dir / 'extracted_20261111.txt'
    with open(output, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'텍스트 저장 완료: {output}')
else:
    print('이미지 파일이 없습니다.')
