import os
import json
import yfinance as yf
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import analyze

# -------------------------
# Finnhub: basic info only
# -------------------------

FINNHUB_API_KEY = 'd5fhadhr01qnjhoc9sbgd5fhadhr01qnjhoc9sc0'  # set this on Render

def finnhub_get(path, params=None):
	if not FINNHUB_API_KEY:
		raise RuntimeError("Missing FINNHUB_API_KEY environment variable")

	base = "https://finnhub.io/api/v1"
	params = params or {}
	params["token"] = FINNHUB_API_KEY

	r = requests.get(f"{base}{path}", params=params, timeout=15)
	r.raise_for_status()
	return r.json()

def getBasicInfoFromFinnhub(symbol):
	"""
	Returns your existing basicInfo format:
	{ longName, website, sector, fullTimeEmployees, marketCap, totalRevenue, trailingEps }
	Best-effort mapping from Finnhub fields.
	"""
	profile = finnhub_get("/stock/profile2", {"symbol": symbol})
	# metrics contains market cap / eps ttm / etc (varies by symbol/plan)
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
		"fullTimeEmployees": pick_first(profile.get("employeeTotal"), profile.get("shareOutstanding")),  # employeeTotal is the usual
		"marketCap": pick_first(metric.get("marketCapitalization"), profile.get("marketCapitalization")),
		"totalRevenue": pick_first(metric.get("revenueTTM"), metric.get("totalRevenueTTM")),
		"trailingEps": pick_first(metric.get("epsTTM"), metric.get("epsAnnual")),
	}

	# Normalize employees to int if it's numeric-ish, else keep as-is / empty
	try:
		if basicInfo["fullTimeEmployees"] != "":
			basicInfo["fullTimeEmployees"] = int(float(basicInfo["fullTimeEmployees"]))
	except Exception:
		pass

	return basicInfo

# -------------------------
# Existing code below
# -------------------------

def extractBasicInfo(data):
	keysToExtract = [ 'longName', 'website', 'sector', 'fullTimeEmployees', 'marketCap', 'totalRevenue', 'trailingEps' ]
	basicInfo = {}
	for key in keysToExtract:
		if key in data:
			basicInfo[key] = data[key]
		else:
			basicInfo[key] = ''
	return basicInfo

def getPriceHistory(company):
	historyDf = company.history(period='12mo')
	prices = historyDf['Open'].tolist()
	dates = historyDf.index.strftime('%Y-%m-%d').tolist()
	return {
		'price': prices,
		'date': dates
	}

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
	result = soup.find_all('div', {'class':'body'})
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
		page = requests.get(url, headers=headers)
		soup = BeautifulSoup(page.text, 'html.parser')
		if not soup.findAll(string='Continue reading'):
			allArticlesText += extractNewsArticleTextFromHtml(soup)
	return allArticlesText

def getCompanyStockInfo(tickerSymbol):
	# Still use yfinance for history + news (as you requested)
	company = yf.Ticker(tickerSymbol)

	# ✅ Use Finnhub for basic info instead of company.info
	# NO LONGER extractBasicInfo(company.info)
	basicInfo = extractBasicInfo(getBasicInfoFromFinnhub(tickerSymbol))

	if not basicInfo["longName"]:
		raise NameError("Could not find stock info (Finnhub profile missing). Ticker may be invalid.")

	priceHistory = getPriceHistory(company)
	futureEarningsDates = getEarningsDates(company)
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

companyStockAnalysis = getCompanyStockInfo('MSFT')
print(json.dumps(companyStockAnalysis, indent=4))
