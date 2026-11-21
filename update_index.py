import json

issueDate = "2026-11-08"
bulletinNumber = 2565

with open("data/bulletins/index.json", 'r', encoding='utf-8') as f:
    index = json.load(f)

new_entry = {
    "date": issueDate,
    "file": f"{issueDate}.json",
    "label": f"2026년 11월 08일 · 제{bulletinNumber}호"
}

if not any(b.get("date") == issueDate for b in index):
    index.insert(0, new_entry)

with open("data/bulletins/index.json", 'w', encoding='utf-8') as f:
    json.dump(index, f, ensure_ascii=False, indent=2)
print("Updated index.json")
