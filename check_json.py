import json
p='data/bulletins/2026-10-18.json'
d=json.load(open(p,encoding='utf-8'))
print(d['issueDate'], d['bulletinNumber'])
services=d['services'][0]
print('leader', services['leader'])
for item in services['order']:
    if item['label']=='말씀':
        print('sermon', item['title'], item['preacher'])
    if item['label']=='성경봉독':
        print('bible', item['reference'])
    if item['label']=='찬송' and item.get('hymn',{}).get('number') in [15,85,428,630,335]:
        hymn=item['hymn']
        print('hymn', hymn.get('number'), hymn.get('verificationStatus'))
