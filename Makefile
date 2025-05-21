# Makefile은 자주 쓰는 명령어 쓰기 귀찮으니까 줄여 놓은거임.
# 예를 들어 이 명령어(uvicorn app:app --reload)를 실행하고 싶으면
# 터미널에서 make run이라고 입력하면 됨.
# 추가하고 싶은 명령어가 있으면 어떻게 줄일건지 적고, 다음 줄에 탭으로 들여쓰기 해야 함. 스페이스로 하면 안됨.

# 개발 서버 실행
run:
	uvicorn main:app --reload

# 패키지 설치 (requirements.txt 기반)
install:
	pip3 install -r requirements.txt

# 현재 설치된 패키지를 requirements.txt로 저장
freeze:
	pip3 freeze > requirements.txt

# 코드 포맷팅 (black 사용)
format:
	black .

# 코드 린트 검사 (ruff 사용)
lint:
	ruff .

# 테스트 실행 (pytest 사용)
test:
	pytest
