import feedparser
import re

def update_dashboard():
    # RSS Feed for Medical Imaging & AI news via Google News
    rss_url = "https://news.google.com/rss/search?q=medical+imaging+AI&hl=en-GB&gl=GB&ceid=GB:en"
    feed = feedparser.parse(rss_url)
    
    news_items_html = ""
    for entry in feed.entries[:4]:  # Top 4 stories
        title = re.sub(r'<[^>]*>', '', entry.title)
        link = entry.link
        source = entry.get('source', {}).get('title', 'Industry News')
        
        news_items_html += f'''
        <div class="news-item">
            <a href="{link}" target="_blank" class="news-title">{title}</a>
            <div class="news-meta"><span class="news-tag">LIVE</span> {source}</div>
        </div>
        '''

    # Read the base template
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()

    # Replace placeholder or update news container
    if "<!-- NEWS_ITEMS_PLACEHOLDER -->" in content:
        updated_content = content.replace("<!-- NEWS_ITEMS_PLACEHOLDER -->", news_items_html)
    else:
        # Fallback regex replacement for recurring automated updates
        updated_content = re.sub(
            r'<div id="news-feed-container">.*?</div>',
            f'<div id="news-feed-container">{news_items_html}</div>',
            content,
            flags=re.DOTALL
        )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(updated_content)

    print("✅ Dashboard news feed updated with live links.")

if __name__ == "__main__":
    update_dashboard()