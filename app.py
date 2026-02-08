import os
import re
import time
import json
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

app = Flask(__name__)

class MangaFireDownloader:
    def __init__(self):
        self.base_url = "https://mangafire.to"
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def start_browser(self):
        """Playwrightを起動し、ブラウザをセットアップする"""
        try:
            self.playwright = sync_playwright().start()
            # Renderのメモリ制限を考慮し、軽量な設定で起動
            self.browser = self.playwright.firefox.launch(
                headless=True,
                args=["--disable-gpu", "--no-sandbox"]
            )
            self.context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
            )
            self.page = self.context.new_page()
        except Exception as e:
            self.close_browser()
            raise e

    def close_browser(self):
        """リソースを解放する"""
        if self.page: self.page.close()
        if self.context: self.context.close()
        if self.browser: self.browser.close()
        if self.playwright: self.playwright.stop()

    def search_manga(self, term):
        """漫画を検索して結果をリストで返す"""
        self.start_browser()
        resultados = []

        # ネットワークレスポンスを監視してAjax結果を取得
        def intercept_search(response):
            if "ajax/manga/search" in response.url and response.status == 200:
                try:
                    resultados.append(response.json())
                except:
                    pass

        try:
            self.page.on("response", intercept_search)
            self.page.goto(self.base_url, wait_until="networkidle")
            
            # 検索窓に入力
            search_input = 'input[name="keyword"]'
            self.page.wait_for_selector(search_input, timeout=10000)
            self.page.fill(search_input, term)
            
            # 結果が出るまで少し待機（Ajax待ち）
            self.page.wait_for_timeout(3000)
        except Exception as e:
            print(f"Search Error: {e}")
        finally:
            self.close_browser()

        if not resultados or 'result' not in resultados[-1]:
            return []

        # HTMLをパースして整形
        soup = BeautifulSoup(resultados[-1]['result']['html'], 'html.parser')
        final_list = []
        for item in soup.select('a.unit'):
            titulo = item.find('h6').text.strip()
            link = item.get('href')
            if link.startswith('/'):
                link = self.base_url + link
            final_list.append({'titulo': titulo, 'link': link})

        return final_list

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "message": "MangaFire API is running",
        "usage": "/search?q=manga_name"
    })

@app.route('/search')
def search():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    
    downloader = MangaFireDownloader()
    try:
        results = downloader.search_manga(query)
        return jsonify({
            "query": query,
            "count": len(results),
            "results": results
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Renderのポート指定に対応
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
