import pandas as pd
import feedparser
import requests
from bs4 import BeautifulSoup
import time
import os

# ----------------------
# Configuration
# ----------------------

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_FOLDER = os.path.join(BASE_DIR, "data")
COMPANIES_FILE = os.path.join(DATA_FOLDER, "companies.xlsx")
MASTER_OUTPUT_FILE = os.path.join(DATA_FOLDER, "company_master.xlsx")
PROGRESS_FILE = os.path.join(DATA_FOLDER, "progress.json")

# Keywords for different modules
FUNDING_KEYWORDS = ["funding", "investment", "raised", "series a", "series b", "seed"]
MA_KEYWORDS = ["merger", "mergers", "acquisition", "acquire", "takeover", "buyout", "joint venture", "stake", "partnership"]
LEADERSHIP_KEYWORDS = ["CEO", "CFO", "CTO", "CXO", "executive", "appointed", "resigns", "joins", "leaves", "promoted"]

CATEGORY_KEYWORDS = {
    "Funding": FUNDING_KEYWORDS,
    "Acquisition": ["acquisition", "acquire", "buyout", "stake"],
    "Partnership": ["joint venture", "partnership"],
    "Merger": ["merger", "mergers"],
    "Takeover": ["takeover"],
    "Leadership Change": LEADERSHIP_KEYWORDS
}

EXPANSION_GROUP = ["Funding", "Acquisition", "Partnership"]
CHURN_GROUP = ["Merger", "Takeover", "Leadership Change"]

# RSS / Website sources
RSS_FEEDS = {
    "Google News": "https://news.google.com/rss/search?q={query}",
    "Yahoo Finance": "https://feeds.finance.yahoo.com/rss/2.0/headline?s={company}&region=US&lang=en-US",
    "PRNewswire": "https://www.prnewswire.com/rss/finance-business-latest-news.rss",
    "BusinessWire": "https://feeds.businesswire.com/BW/Finance"
}

SCRAPE_SITES = {
    "TechCrunch": "https://techcrunch.com/startups/",
    "Crunchbase News": "https://news.crunchbase.com/",
    "ETTech": "https://tech.economictimes.indiatimes.com/funding"
}

# ----------------------
# Helper Functions
# ----------------------
def fetch_rss_feed(url, company_name, keywords, source_name=None):
    try:
        feed = feedparser.parse(url)
        if feed.bozo:
            return []
        articles = []
        for entry in feed.entries[:10]:
            title = entry.title
            link = entry.link
            pub_date = entry.get("published", entry.get("pubDate", ""))
            snippet = entry.get("summary", entry.get("description", ""))[:300]

            if not any(k.lower() in (title + snippet).lower() for k in keywords):
                continue

            source = source_name if source_name else entry.get("source", {}).get("title", "RSS")
            articles.append({
                "Company": company_name,
                "Source": source,
                "Title": title,
                "Event Type": " / ".join(keywords),
                "Published": pub_date,
                "Link": link,
                "Snippet": snippet
            })
        return articles
    except:
        return []

def scrape_site(url, company_name, keywords, source_name):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (CompanyIntelAnalyzer)"}
        response = requests.get(url, timeout=10, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        articles = []

        for h in soup.find_all(["h2","h3","a"]):
            title = h.get_text(strip=True)
            link = h.get("href")
            if not link or company_name.lower() not in title.lower():
                continue
            if not any(k.lower() in title.lower() for k in keywords):
                continue

            snippet = ""
            pub_date = ""
            p_tag = h.find_next("p")
            if p_tag:
                snippet = p_tag.get_text(strip=True)[:300]
            time_tag = h.find_next("time")
            if time_tag:
                pub_date = time_tag.get("datetime", "")

            if link.startswith("/"):
                link = url.rstrip("/") + link

            articles.append({
                "Company": company_name,
                "Source": source_name,
                "Title": title,
                "Event Type": " / ".join(keywords),
                "Published": pub_date,
                "Link": link,
                "Snippet": snippet
            })
        return articles
    except:
        return []

def categorize_article(title, snippet):
    text = (title + " " + snippet).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(k.lower() in text for k in keywords):
            group = "Expansion Opportunity" if category in EXPANSION_GROUP else "Churn Signal"
            return category, group
    return "No recent updates found", "-"

# ----------------------
# Main Function
# ----------------------
def run_company_intel():
    df_companies = pd.read_excel(COMPANIES_FILE)
    company_list = []
    for _, row in df_companies.iterrows():
        company_list.append({
            "name": row["Company"].strip(),
            "domain": row.get("Domain", ""),
            "hq": row.get("HQ Location", "")
        })

    all_articles = []

    for idx, company in enumerate(company_list, 1):
        print(f" Analyzing: {company['name']}")

        # ✅ Progress update
        with open(PROGRESS_FILE, "w") as f:
            f.write(f"Analyzing {idx}/{len(company_list)}: {company['name']}")

        company_articles = []

        # Build refined query
        query = company["name"].replace(" ", "+")
        if company["domain"]:
            query += "+" + company["domain"]
        if company["hq"]:
            query += "+" + company["hq"].replace(",", "+")

        # Funding / Investments
        for name, url_template in RSS_FEEDS.items():
            company_articles.extend(fetch_rss_feed(url_template.format(query=query, company=company["name"]), company["name"], FUNDING_KEYWORDS, name))
        for name, url in SCRAPE_SITES.items():
            company_articles.extend(scrape_site(url, company["name"], FUNDING_KEYWORDS, name))

        # M&A / Takeovers
        for name, url_template in RSS_FEEDS.items():
            company_articles.extend(fetch_rss_feed(url_template.format(query=query, company=company["name"]), company["name"], MA_KEYWORDS, name))
        for name, url in SCRAPE_SITES.items():
            company_articles.extend(scrape_site(url, company["name"], MA_KEYWORDS, name))

        # Leadership Changes
        for name, url_template in RSS_FEEDS.items():
            company_articles.extend(fetch_rss_feed(url_template.format(query=query, company=company["name"]), company["name"], LEADERSHIP_KEYWORDS, name))
        for name, url in SCRAPE_SITES.items():
            company_articles.extend(scrape_site(url, company["name"], LEADERSHIP_KEYWORDS, name))

        # If no articles, add placeholder
        if not company_articles:
            company_articles.append({
                "Company": company["name"],
                "Source": "-",
                "Title": "-",
                "Event Type": "No recent updates found",
                "Published": "-",
                "Link": "-",
                "Snippet": "-",
                "Domain": company["domain"],
                "HQ Location": company["hq"]
            })

        # Categorize each article and add domain/HQ
        for article in company_articles:
            category, group = categorize_article(article["Title"], article["Snippet"])
            article["Category"] = category
            article["Group Type"] = group
            article["Domain"] = company["domain"]
            article["HQ Location"] = company["hq"]

        all_articles.extend(company_articles)
        time.sleep(2)

    # Save master Excel
    if all_articles:
        df_master = pd.DataFrame(all_articles)
        df_master.to_excel(MASTER_OUTPUT_FILE, index=False)
        print(f" Master company intelligence saved: {MASTER_OUTPUT_FILE}")
    else:
        print("️ No articles found for any company.")

    # ✅ Final progress update
    with open(PROGRESS_FILE, "w") as f:
        f.write(" Analysis complete. Ready for download.")

# ----------------------
# Run Script
# ----------------------
if __name__ == "__main__":
    run_company_intel()
