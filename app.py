import os
import re
import time
import json
import base64
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

app = Flask(__name__)

class MangaFireDownloader:
    def __init__(self):
        self.base_url = "https://mangafire.to"
        self.playwright = None
        self.browser = None

    def start_browser(self):
        self.playwright = sync_playwright().start()
        # Render環境（Linux）では headless=True が必須
        self.browser = self.playwright.firefox.launch(headless=True)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def close_browser(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def clean_filename(self, text):
        return re.sub(r'[<>"/\\|?*:]', '', text).strip().rstrip('.')

    def extract_manga_id(self, url):
        match = re.search(r'\.([a-zA-Z0-9]+)$', url)
        return match.group(1) if match else url.split('.')[-1]

    def search_manga(self, term):
        self.start_browser()
        resultados = []

        def intercept_search(response):
            if "ajax/manga/search" in response.url and response.status == 200:
                try: resultados.append(response.json())
                except: pass

        self.page.on("response", intercept_search)
        self.page.goto(self.base_url)
        
        try:
            self.page.wait_for_selector('input[name="keyword"]', timeout=5000)
            self.page.type('input[name="keyword"]', term, delay=50)
            self.page.wait_for_timeout(2000)
        except: pass

        self.close_browser()

        if not resultados or 'result' not in resultados[-1]:
            return []

        soup = BeautifulSoup(resultados[-1]['result']['html'], 'html.parser')
        return [{'titulo': item.find('h6').text.strip(), 
                 'link': self.base_url + item.get('href') if item.get('href').startswith('/') else item.get('href')} 
                for item in soup.select('a.unit')]

@app.route('/')
def index():
    return "MangaFire Downloader API is running. Use /search?q=manga_name"

@app.route('/search')
def search():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "No query provided"}), 400
    
    downloader = MangaFireDownloader()
    results = downloader.search_manga(query)
    return jsonify(results)

if __name__ == "__main__":
    # RenderはPORT環境変数を使用するため
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
