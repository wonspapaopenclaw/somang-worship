# 소망교회 예배 페이지

2026년 9월 6일 주보를 기준으로 만든 GitHub Pages용 정적 예배 화면입니다.

## 주보 데이터 구조

현재 화면은 `data/latest.json`을 읽습니다. 원본 주보는 날짜별로 `data/bulletins/`에 보관합니다.

```text
data/
├─ latest.json
└─ bulletins/
   └─ 2026-09-06.json
```

다음 주에는 새 파일을 `data/bulletins/YYYY-MM-DD.json`으로 추가한 뒤, 같은 파일을 `data/latest.json`으로 교체하면 됩니다. 화면 코드와 배포 설정은 수정할 필요가 없습니다.

## 포함 기능

- 예배 시간 선택
- 성경봉독 접기·펼치기
- 성시교독 접기·펼치기
- 찬송가 악보 접기·펼치기
- 시간별 기도자·찬양·찬양대 표시
- 큰 글씨 모드

## GitHub Pages 배포

저장소의 Pages 설정에서 Source를 GitHub Actions로 선택한 뒤 `main` 브랜치에 올리면 `deploy-pages.yml`이 사이트를 배포합니다.
