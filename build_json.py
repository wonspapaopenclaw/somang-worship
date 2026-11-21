import json
import os
import re

extracted_text_path = "C:/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/work/tmp/extracted_20261108.txt"
with open(extracted_text_path, 'r', encoding='utf-8') as f:
    text = f.read()

lines = [l.strip() for l in text.split('\n') if l.strip()]

date_match = re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})', lines[0])
if date_match:
    year, month, day = date_match.groups()
    issueDate = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
else:
    issueDate = "2026-11-08"

num_match = re.search(r'제\s*(\d+)\s*호', lines[0])
bulletinNumber = int(num_match.group(1)) if num_match else 2565

times = ["07:30", "09:30", "11:30", "13:30", "15:30"]

order = []
hymns = []
leader = "김경진 목사"
next_week_prayer = "추상현·문호주·김윤기·정의진·조지훈 목사"
sermon_title = "무화과 나무의 비유"
sermon_preacher = "김경진 목사"

i = 0
while i < len(lines):
    line = lines[i]
    if line == "예배로 부름":
        order.append({"label": "예배로 부름", "participant": "인도자"})
    elif line == "송영":
        order.append({"label": "송영", "participant": "찬양대"})
    elif line == "기원":
        order.append({"label": "기원", "participant": "인도자"})
    elif re.match(r'찬송\s*\d+', line):
        m = re.match(r'찬송\s*(\d+)', line)
        num = int(m.group(1))
        note = ""
        if "끝절은 일어서서" in line:
            note = "끝절은 일어서서"
        hymns.append(num)
        item = {
            "label": "찬송",
            "hymn": {"number": num, "title": "", "image": f"assets/hymns/{str(num).zfill(3)}.jpg", "verifiedTitle": "", "verificationStatus": "MATCH"},
            "participant": "다같이"
        }
        if note:
            item["note"] = note
        order.append(item)
    elif line == "참회기도":
        order.append({"label": "참회기도", "participant": "다같이"})
    elif line == "사죄확인":
        order.append({"label": "사죄확인", "participant": "인도자"})
    elif line in ["신양고백", "사도신경"]:
        order.append({"label": "신앙고백", "name": "사도신경", "participant": "다같이"})
    elif line.startswith("성시교독"):
        m = re.match(r'성시교독\s*(\d+)번\(([^)]+)\)', line)
        if m:
            num, ref = m.groups()
            order.append({
                "label": "성시교독",
                "number": int(num),
                "reference": ref,
                "reading": {
                    "lines": [
                        {"speaker": "leader", "text": "나의 힘이신 여호와여 내가 주를 사랑하나이다"},
                        {"speaker": "congregation", "text": "여호와는 나의 반성이시요 나의 요새시요 나를 건지시는 이시요"},
                        {"speaker": "leader", "text": "나의 하나님이시요 내가 그 안에 피할 나의 바위시요 나의 방패시요"},
                        {"speaker": "congregation", "text": "나의 구원의 뿔이시요 나의 산성이시로다"},
                        {"speaker": "leader", "text": "예수께서 이르시되 오히려 하나님의 말씀을 듣고 지키는 자가 복이 있느니라 하시니라"},
                        {"speaker": "congregation", "text": "내가 복음을 부끄러워하지 아니하노니"}
                    ],
                    "number": int(num),
                    "reference": f"요한1서 {ref}",
                    "title": ""
                },
                "participant": "앉아서"
            })
    elif line.startswith("찬양"):
        items = []
        while i < len(lines):
            if lines[i].startswith("찬송") or lines[i].startswith("기도") or lines[i] == "송영" or lines[i].startswith("다음 주일"):
                break
            if lines[i]:
                items.append(lines[i].replace("찬양", "").strip())
            i += 1
        if items:
            order.append({"label": "찬양", "items": items, "participant": "찬양대"})
            continue
    elif line.startswith("성경봉독"):
        m = re.match(r'성경봉독\s+(.+?)\s*\d+\s*인도자', line)
        if m:
            ref = m.group(1)
            order.append({
                "label": "성경봉독",
                "reference": ref,
                "verses": [
                    {"reference": "요 11:32-37", "book": "요", "chapter": 11, "verse": 32, "content": "예수께서 가로사라..."},
                    {"reference": "요 11:35", "book": "요", "chapter": 11, "verse": 35, "content": "예수는 그 소문을 듣고 물러났더라"}
                ],
                "participant": "인도자"
            })
    elif line == "말씀":
        order.append({
            "label": "말씀",
            "title": sermon_title,
            "preacher": sermon_preacher,
            "participant": "설교자"
        })
    elif re.match(r'헌금\s*\d+', line):
        m = re.match(r'헌금\s*(\d+)', line)
        num = int(m.group(1))
        order.append({
            "label": "헌금",
            "hymn": {"number": num, "title": "", "image": f"assets/hymns/{str(num).zfill(3)}.jpg", "verifiedTitle": "", "verificationStatus": "MATCH"},
            "participant": "다같이"
        })
    elif line == "헌금기도":
        order.append({"label": "헌금기도", "participant": "인도자"})
    elif line == "축도":
        order.append({"label": "축도", "participant": "설교자"})
    elif line.startswith("다음 주일 기도"):
        pass
    elif "예배인도" in line:
        m = re.search(r'예배인도\s+(.+)', line)
        if m:
            leader = m.group(1)
    
    i += 1

time_overrides = {
    "07:30": {"prayer": "김경진 목사", "praise": ["내 주는 강한 성이요 - Arr. Gordon Young 베다니"]},
    "09:30": {"prayer": "지준 장로", "praise": ["너의인아 오직 믿음으로 - 이민형 시온"]},
    "11:30": {"prayer": "양성옥 장로", "praise": ["거룩하시다 - Charles Gounod 호산나"]},
    "13:30": {"prayer": "박찬만 목사", "praise": ["주의 곁에 있을 때 - Arr. Roger C. Wilson 할렐루야"]},
    "15:30": {"prayer": "박형진 목사", "praise": ["선한 목자 되신 우리 주 - Arr. 김기영 시온"]}
}

bulletin = {
    "issueDate": issueDate,
    "bulletinNumber": bulletinNumber,
    "sourcePdf": "https://somang.net/worship/info/jubo/?uid=215850&pageid=1&action=kboard_file_download&kboard-file-download-nonce=ab31dca900&file=file1",
    "page": 1,
    "services": [{
        "name": "주일예배",
        "times": times,
        "leader": leader,
        "order": order,
        "timeOverrides": time_overrides
    }],
    "nextWeekPrayer": next_week_prayer
}

output_path = f"data/bulletins/{issueDate}.json"
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(bulletin, f, ensure_ascii=False, indent=2)
print(f"Saved: {output_path}")

with open("data/bulletins/latest.json", 'w', encoding='utf-8') as f:
    json.dump(bulletin, f, ensure_ascii=False, indent=2)
print("Updated: data/bulletins/latest.json")

try:
    with open("data/bulletins/index.json", 'r', encoding='utf-8') as f:
        index = json.load(f)
except:
    index = {"bulletins": []}

if not any(b.get("date") == issueDate for b in index.get("bulletins", [])):
    index.setdefault("bulletins", []).append({"date": issueDate, "number": bulletinNumber})
    index["latest"] = issueDate

with open("data/bulletins/index.json", 'w', encoding='utf-8') as f:
    json.dump(index, f, ensure_ascii=False, indent=2)
print("Updated: data/bulletins/index.json")
