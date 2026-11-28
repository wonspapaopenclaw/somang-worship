import json

# Read current bulletins/2026-11-29.json
with open('data/bulletins/2026-11-29.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

order = data['services'][0]['order']

# Find the 성시교독 item and fill in the lines
for item in order:
    if item.get('label') == '성시교독':
        item['reading'] = {
            "number": 115,
            "reference": "눅 3:4-6",
            "title": "구주 강림(1)",
            "lines": [
                {"speaker": "leader", "text": "성문으로 나아가라 나아가라 백성이 올 길을 닦으라"},
                {"speaker": "congregation", "text": "큰 길을 수축하고 수축하라 돌을 제하라 만민을 위하여 기치를 들라"},
                {"speaker": "leader", "text": "여호와께서 땅 끝까지 선포하시되 너희는 딸 시온에게 이르기를 보라 네 구원이 이르렀느니라"},
                {"speaker": "congregation", "text": "보라 상급이 그에게 있고 보응이 그 앞에 있느니라 하셨느니라"},
                {"speaker": "leader", "text": "사람들이 너를 일컬어 거룩한 백성이라 여호와께서 구속하신 자라 하겠고"},
                {"speaker": "congregation", "text": "또 너를 일컬어 찾은 바 된 자요 버림 받지 아니한 성읍이라 하리라"},
                {"speaker": "leader", "text": "선지자 이사야의 책에 쓴 바 광야에서 외치는 자의 소리가 있어 이르기를"},
                {"speaker": "congregation", "text": "너는 주의 길을 준비하라 그의 오실 길을 곧게 하라"},
                {"speaker": "leader", "text": "모든 골짜기가 메워지고 모든 산과 작은 산이 낮아지고"},
                {"speaker": "congregation", "text": "굽은 것이 곧아지고 험한 길이 평탄하여질 것이요"},
                {"speaker": "all", "text": "모든 육체가 하나님의 구원하심을 볼까 함과 같으니라"}
            }
        print('bulletins/2026-11-29.json reading lines filled in')

# Save updated JSON
with open('data/bulletins/2026-11-29.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('bulletins/2026-11-29.json updated successfully')