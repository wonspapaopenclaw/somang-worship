import json, datetime, sys
bulletin_path='data/bulletins/2026-10-18.json'
with open(bulletin_path,'r',encoding='utf-8') as f:
    data=json.load(f)
issue_date=data['issueDate']
content = f"""
2026. 10. 18. 제 2562 호
대한예수교장로회
소망교회
주일예배
오전 7:30, 9:30, 11:30 | 오후 1:30, 3:30
예배인도 김경진 목사
"""
with open(f'/c/Users/chajh/Documents/Codex/2026-09-06/referenced-chatgpt-conversation-this-is-an/work/tmp/extracted_{issue_date.replace("-","")}.txt','w',encoding='utf-8') as f:
    f.write(content)
print(f'extracted saved for {issue_date}')
