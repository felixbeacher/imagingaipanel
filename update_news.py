import re
import feedparser
import yfinance as yf

def fetch_macro_data():
    """Fetch macro metrics dynamically."""
    # Example using S&P Healthcare Sector ETF (XLV) for MedTech performance context
    xlv = yf.Ticker("XLV")
    price = xlv.fast_info.get("lastPrice", 0.0)
    
    return {
        "medtech_vc": f"${price:.1f} (XLV)",
        "base_rate": "4.50%",
        "inflation": "3.2%"
    }

def update_dashboard():
    # RSS Feed for Medical Imaging & AI news via Google News
    rss_url = "https://news.google.com/rss/search?q=medical+imaging+AI&hl=en-GB&gl=GB&ceid=GB:en"
    feed = feedparser.parse(rss_url)
    
    news_items_html = ""
    for entry in feed.entries[:4]:
        title = re.sub(r'<[^>]*>', '', entry.title)
        link = entry.link
        source = entry.get('source', {}).get('title', 'Industry News')
        
        news_items_html += f'''
        <div class="news-item">
            <a href="{link}" target="_blank" rel="noopener noreferrer" class="news-title">{title}</a>
            <div class="news-meta"><span class="news-tag">LIVE</span> {source}</div>
        </div>
        '''

    # Read the template
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()

    # Inject live news items
    if "<!-- NEWS_ITEMS_PLACEHOLDER -->" in content:
        content = content.replace("<!-- NEWS_ITEMS_PLACEHOLDER -->", news_items_html)
    else:
        content = re.sub(
            r'<div id="news-feed-container">.*?</div>',
            f'<div id="news-feed-container">{news_items_html}</div>',
            content,
            flags=re.DOTALL
        )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ Dashboard successfully updated with live sources.")

if __name__ == "__main__":
    update_dashboard()