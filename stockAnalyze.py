import os
import json
import requests
from datetime import datetime, timedelta, timezone
import analyze
import csv
import io

# -------------------------
# Finnhub
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

def extractBasicInfo(data):
	keysToExtract = ['longName', 'website', 'sector', 'fullTimeEmployees', 'marketCap', 'totalRevenue', 'trailingEps']
	return {k: data.get(k, '') for k in keysToExtract}

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

def getCompanyNewsFinnhub(symbol, days_back=14, max_items=12):
	end_dt = datetime.now(timezone.utc).date()
	start_dt = end_dt - timedelta(days=days_back)

	data = finnhub_get("/company-news", {
		"symbol": symbol,
		"from": start_dt.strftime("%Y-%m-%d"),
		"to": end_dt.strftime("%Y-%m-%d"),
	})

	news = []
	for item in (data or [])[:max_items]:
		title = item.get("headline") or ""
		link = item.get("url") or ""
		summary = item.get("summary") or ""
		source = item.get("source") or ""
		ts = item.get("datetime")

		pubDate = ""
		if ts:
			pubDate = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

		if title and link:
			news.append({
				"title": title,
				"link": link,
				"summary": summary,
				"source": source,
				"pubDate": pubDate
			})

	return news

# -------------------------
# Free price history: Stooq (no key)
# -------------------------

def getPriceHistoryStooq(symbol):
	"""
	Free daily OHLC via Stooq CSV.
	Returns: {'price': [...], 'date': [...]}
	Uses Open price to match your previous behavior.
	"""
	stooq_symbol = symbol.lower()
	if "." not in stooq_symbol:
		stooq_symbol = f"{stooq_symbol}.us"

	url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
	r = requests.get(url, timeout=20)
	r.raise_for_status()

	f = io.StringIO(r.text)
	reader = csv.DictReader(f)

	rows = [row for row in reader if row and row.get("Date")]
	if not rows:
		return {"price": [], "date": []}

	end_dt = datetime.now(timezone.utc).date()
	start_dt = end_dt - timedelta(days=365)

	prices, dates = [], []
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
# Earnings (kept as before)
# -------------------------

def getEarningsDates():
	return []

# -------------------------
# Stock analysis
# -------------------------

def getCompanyStockInfo(tickerSymbol):
	basicInfo = extractBasicInfo(getBasicInfoFromFinnhub(tickerSymbol))
	if not basicInfo.get("longName"):
		raise NameError("Could not find stock info (Finnhub profile missing). Ticker may be invalid.")

	priceHistory = getPriceHistoryStooq(tickerSymbol)
	futureEarningsDates = getEarningsDates()
	newsArticles = getCompanyNewsFinnhub(tickerSymbol)

	# No scraping: analyze headline + summary only
	newsText = "\n".join(
		f"{a.get('title','')}. {a.get('summary','')}"
		for a in newsArticles
	)
	newsTextAnalysis = analyze.analyzeText(newsText)

	return {
		"basicInfo": basicInfo,
		"priceHistory": priceHistory,
		"futureEarningsDates": futureEarningsDates,
		"newsArticles": newsArticles,
		"newsTextAnalysis": newsTextAnalysis
	}

if __name__ == "__main__":
	companyStockAnalysis = getCompanyStockInfo("AAPL")
	print(json.dumps(companyStockAnalysis, indent=4))
