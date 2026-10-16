import json, datetime, sys, os
bulletin_path='data/bulletins/2026-10-18.json'
with open(bulletin_path,'r',encoding='utf-8') as f:
    data=json.load(f)
issue_date=data['issueDate']
content = f"""2026. 10. 18. 제 2562 호
대한예수교장로회
소망교회
THE SO-MANG PRESBYTERIAN CHURCH
주일예배
오전 7:30, 9:30, 11:30 | 오후 1:30, 3:30
예배인도 김경진 목사
예배로 부름 인도자
송영 찬양대
기원 인도자
찬송 15 일어서서
참회기도 다같이
사죄확인 인도자
신앙고백 사도신경 다같이
성시교독 83번(빌립보서 4장) 앉아서
찬송 85 다같이
기도 김주경 목사 · 홍선표 · 백광흠 · 박동찬 장로 · 임대성 청년부 부감
성경봉독 눅 1:76~79 인도자
찬양 진실하신 친구 - Arr. John M.rasley 베다니
성부의 아들이여 - A. Vivaldi 호산나
하나님의 전신갑주 - 김신웅 시온
하늘의 아버지 - G. F. Handel 할렐루야
하나님 없이는 - 김재훈 에벤에셀
말씀 그늘에 비치는 따뜻한 빛 김경진 목사
기도 설교자
찬송 428 다같이
헌금 630 다같이
헌금기도 인도자
찬송 335(끝절은 일어서서) 다같이
축도 설교자
송영 찬양대
다음 주일 기도 : 박형진 장로 · 장재원 목사 · 김덕영 · 장형기 장로 · 홍경화 청년부 부감
"""
out_path='C:/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/work/tmp/extracted_20261018.txt'
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path,'w',encoding='utf-8') as f:
    f.write(content)
print(f'saved to {out_path}')
