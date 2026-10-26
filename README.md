# 티니핑 맞추기

사진을 보고 티니핑 이름을 맞추는 아이용 게임. 다음 문제 버튼(▶)만 있고, 정답 이름은 오른쪽 위에 작게 나온다.

- `index.html`: 게임 화면 (GitHub Pages로 서비스)
- `pings.json`: 티니핑 데이터베이스 (영어 이름, 한글 이름, 이미지 주소)
- `scraper.py`: [Catch! Teenieping 팬 위키](https://catchteenieping.fandom.com)에서 데이터를 받아 `pings.json` 갱신
- `.github/workflows/update.yml`: 매주 자동으로 `scraper.py` 실행

이미지는 위키에서 직접 불러온다. 캐릭터 저작권은 SAMG엔터테인먼트에 있으며, 가족이 개인적으로 쓰는 용도로 만들었다.
