import json

with open('data/bulletins/2026-11-08.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Fix leader field
data['services'][0]['leader'] = "김경진 목사"

# Fix hymn titles (already updated by enrich, but ensure they're there)
hymn_titles = {
    19: "찬양하는 소리 있어",
    288: "예수를 나의 구주 삼고",
    413: "내 평생에 가는 길",
    384: "나의 갈길 다 가도록",
    630: "진리와 생명 되신 주"
}

for item in data['services'][0]['order']:
    if item.get('label') == '찬송':
        num = item.get('hymn', {}).get('number')
        if num and num in hymn_titles:
            title = hymn_titles[num]
            item['hymn']['title'] = title
            item['hymn']['verifiedTitle'] = title

# Fix sermon title
for item in data['services'][0]['order']:
    if item.get('label') == '말씀':
        item['title'] = "하나님의 무능력"
        item['preacher'] = "김경진 목사"

# Fix time overrides
data['services'][0]['timeOverrides'] = {
    "07:30": {"prayer": "김경진 목사", "praise": ["내 주는 강한 성이요 - Arr. Gordon Young 베다니"]},
    "09:30": {"prayer": "지준 장로", "praise": ["너의인아 오직 믿음으로 - 이민형 시온"]},
    "11:30": {"prayer": "양성옥 장로", "praise": ["거룩하시다 - Charles Gounod 호산나"]},
    "13:30": {"prayer": "박찬만 목사", "praise": ["주의 곁에 있을 때 - Arr. Roger C. Wilson 할렐루야"]},
    "15:30": {"prayer": "박형진 목사", "praise": ["선한 목자 되신 우리 주 - Arr. 김기영 시온"]}
}

# Fix nextWeekPrayer
data['nextWeekPrayer'] = "추상현·문호주·김윤기·정의진·조지훈 목사"

with open('data/bulletins/2026-11-08.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# Update latest.json
with open('data/bulletins/latest.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("JSON 수정 완료")
