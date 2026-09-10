# Four commands. A reader can run all four without asking anyone.
.PHONY: all setup data test run clean

all: data test run

setup:
	python3 -m pip install -r requirements.txt

data:
	python3 get_data.py

test:
	python3 -m pytest -q

run:
	python3 analyse.py

clean:
	rm -rf data __pycache__ .pytest_cache change.png
