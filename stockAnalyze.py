import os
import json
import yfinance as yf
import requests
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import analyze
import csv
import io

# -------------------------
# Finnhub: basic info only
# -------------------------

FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "").strip()

def finnhub_get(path, params=None):
	if not FINNHUB_API_KEY:
		raise RuntimeError("Missing FINNHUB_API_KEY environment variable")

	base = "https://finnhub.io/api/v1"
	params = params or {}
	params["token"] = FINNHUB_API_KEY

	r = requests.get(f"{base}{path}", params=params, timeout=15)
	if r.status_code >= 400:
		try:
			detail = r.json()
		except Exception:
			detail = r.text[:300]
		raise RuntimeError(f"Finnhub error {r.status_code}: {detail}")

	return r.json()

def getBasicInfoFromFinnhub(symbol):
	profile = finnhub_get("/stock/profile2", {"symbol": symbol})
	metrics_resp = finnhub_get("/stock/metric", {"symbol": symbol, "metric": "all"})
	metric = (metrics_resp or {}).get("metric", {}) or {}

	def pick_first(*vals):
		for v in vals:
			if v is None:
				continue
			if isinstance(v, str) and v.strip() == "":
				continue
			return v
		return ""

	basicInfo = {
		"longName": pick_first(profile.get("name")),
		"website": pick_first(profile.get("weburl")),
		"sector": pick_first(profile.get("finnhubIndustry"), profile.get("sector")),
		"fullTimeEmployees": pick_first(profile.get("employeeTotal")),
		"marketCap": pick_first(metric.get("marketCapitalization"), profile.get("marketCapitalization")),
		"totalRevenue": pick_first(metric.get("revenueTTM"), metric.get("totalRevenueTTM")),
		"trailingEps": pick_first(metric.get("epsTTM"), metric.get("epsAnnual")),
	}

	try:
		if basicInfo["fullTimeEmployees"] != "":
			basicInfo["fullTimeEmployees"] = int(float(basicInfo["fullTimeEmployees"]))
	except Exception:
		pass

	return basicInfo

# -------------------------
# Free price history: Stooq (no key)
# -------------------------

def getPriceHistoryStooq(symbol):
	"""
	Free daily OHLC via Stooq CSV.
	Returns same shape you used: {'price': [...], 'date': [...]}
	Uses Open price to match your previous behavior.
	"""
	# Stooq uses lower-case tickers, US tickers often need ".us"
	stooq_symbol = symbol.lower()
	if "." not in stooq_symbol:
		stooq_symbol = f"{stooq_symbol}.us"

	url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"

	r = requests.get(url, timeout=20)
	r.raise_for_status()

	# CSV format: Date,Open,High,Low,Close,Volume
	f = io.StringIO(r.text)
	reader = csv.DictReader(f)

	rows = []
	for row in reader:
		# Skip empty lines
		if not row or not row.get("Date"):
			continue
		rows.append(row)

	if not rows:
		return {"price": [], "date": []}

	# Only last ~12 months
	end_dt = datetime.now(timezone.utc).date()
	start_dt = end_dt - timedelta(days=365)

	prices = []
	dates = []
	for row in rows:
		try:
			d = datetime.strptime(row["Date"], "%Y-%m-%d").date()
		except Exception:
			continue

		if d < start_dt or d > end_dt:
			continue

		open_str = (row.get("Open") or "").strip()
		if open_str == "" or open_str.lower() == "null":
			continue

		try:
			open_price = float(open_str)
		except Exception:
			continue

		dates.append(d.strftime("%Y-%m-%d"))
		prices.append(open_price)

	return {"price": prices, "date": dates}

# -------------------------
# Existing code below
# -------------------------

def extractBasicInfo(data):
	keysToExtract = ['longName', 'website', 'sector', 'fullTimeEmployees', 'marketCap', 'totalRevenue', 'trailingEps']
	basicInfo = {}
	for key in keysToExtract:
		basicInfo[key] = data.get(key, '')
	return basicInfo

# Future Earnings no longer supported
def getEarningsDates(company):
	return []

def getCompanyNews(company):
	newsList = company.news
	allNewsArticles = []
	for newsDict in newsList:
		newsDictToAdd = {
			'title': newsDict['content']['title'],
			'link': newsDict['content']['canonicalUrl']['url']
		}
		allNewsArticles.append(newsDictToAdd)
	return allNewsArticles

def extractNewsArticleTextFromHtml(soup):
	allText = ''
	result = soup.find_all('div', {'class': 'body'})
	for res in result:
		allText += res.text
	return allText

headers = {
	'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

def extractCompanyNewsArticles(newsArticles):
	allArticlesText = ''
	for newsArticle in newsArticles:
		url = newsArticle['link']
		page = requests.get(url, headers=headers, timeout=15)
		soup = BeautifulSoup(page.text, 'html.parser')
		if not soup.findAll(string='Continue reading'):
			allArticlesText += extractNewsArticleTextFromHtml(soup)
	return allArticlesText

def getCompanyStockInfo(tickerSymbol):
	# Still use yfinance for news (your experiment)
	company = yf.Ticker(tickerSymbol)

	# ✅ Finnhub basic info
	basicInfo = extractBasicInfo(getBasicInfoFromFinnhub(tickerSymbol))
	if not basicInfo["longName"]:
		raise NameError("Could not find stock info (Finnhub profile missing). Ticker may be invalid.")

	# ✅ Free price history (Stooq)
	priceHistory = getPriceHistoryStooq(tickerSymbol)

	futureEarningsDates = getEarningsDates(company)

	# Keep yfinance news "as usual" for now
	newsArticles = getCompanyNews(company)

	newsArticlesAllText = extractCompanyNewsArticles(newsArticles)
	newsTextAnalysis = analyze.analyzeText(newsArticlesAllText)

	finalStockAnalysis = {
		"basicInfo": basicInfo,
		"priceHistory": priceHistory,
		"futureEarningsDates": futureEarningsDates,
		"newsArticles": newsArticles,
		"newsTextAnalysis": newsTextAnalysis
	}
	return finalStockAnalysis

if __name__ == "__main__":
	companyStockAnalysis = getCompanyStockInfo('MSFT')
	print(json.dumps(companyStockAnalysis, indent=4))
