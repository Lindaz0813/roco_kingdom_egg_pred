.PHONY: dashboard scrape install

install:
	pip install -r requirements.txt

scrape:
	python3 scraper.py

dashboard:
	python3 app.py
