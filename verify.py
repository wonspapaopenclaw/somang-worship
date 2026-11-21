import json
p='data/bulletins/2026-11-08.json'
d=json.load(open(p,encoding='utf-8'))
print("issueDate:", d['issueDate'])
print("bulletinNumber:", d['bulletinNumber'])
services=d['services'][0]
print('leader:', services['leader'])
for item in services['order']:
    if item['label']=='말씀':
        print('sermon:', item.get('title', ''), 'by', item.get('preacher', ''))
    if item['label']=='성경봉독':
        print('bible:', item.get('reference', ''))
        if 'verses' in item:
            print('  verses count:', len(item['verses']))
    if item['label']=='찬송':
        hymn=item.get('hymn',{})
        num = hymn.get('number')
        if num in [19, 288, 413, 384, 630]:
            print('hymn', num, 'status:', hymn.get('verificationStatus'), '- title:', hymn.get('title')[:30] if hymn.get('title') else '')
    if item['label']=='성시교독':
        print('reading:', item.get('number'), item.get('reference'))
