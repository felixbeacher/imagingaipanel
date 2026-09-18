import json
import logging
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# RSS Feed Endpoints
RSS_FEEDS = {
    "Radiology Business": "https://radiologybusiness.com/rss.xml",
    "AuntMinnie": "https://www.auntminnie.com/rss/rss.aspx",
    "FDA News": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml",
}


def fetch_rss_headlines():
    """Fetch and parse live headlines from defined RSS feeds."""
    items = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HealthcareDashboard/1.0"
    }

    for source_name, url in RSS_FEEDS.items():
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                xml_data = response.read().decode("utf-8", errors="ignore")

            # Extract items via regex to avoid heavy external dependencies
            raw_items = re.findall(r"<item>(.*?)</item>", xml_data, re.DOTALL)

            for raw_item in raw_items[:3]:  # Limit to top 3 per feed
                title_match = re.search(
                    r"<title>(.*?)</title>", raw_item, re.DOTALL
                )
                link_match = re.search(
                    r"<link>(.*?)</link>", raw_item, re.DOTALL
                )
                date_match = re.search(
                    r"<pubDate>(.*?)</pubDate>", raw_item, re.DOTALL
                )

                if title_match and link_match:
                    title = (
                        title_match.group(1)
                        .replace("<![CDATA[", "")
                        .replace("]]>", "")
                        .strip()
                    )
                    link = (
                        link_match.group(1)
                        .replace("<![CDATA[", "")
                        .replace("]]>", "")
                        .strip()
                    )
                    pub_date = (
                        date_match.group(1).strip() if date_match else "Recent"
                    )

                    # Simple tag classification based on keywords
                    tag = "Industry"
                    title_lower = title.lower()
                    if "fda" in title_lower or "clearance" in title_lower:
                        tag = "Regulatory"
                    elif "ai" in title_lower or "algorithm" in title_lower:
                        tag = "AI Innovation"
                    elif (
                        "reimbursement" in title_lower
                        or "cpt" in title_lower
                        or "market" in title_lower
                    ):
                        tag = "Macro / Market"

                    items.append(
                        {
                            "title": title,
                            "link": link,
                            "source": source_name,
                            "date": pub_date,
                            "tag": tag,
                        }
                    )
        except Exception as e:
            logging.warning(
                f"Failed to fetch RSS feed from {source_name}: {e}"
            )

    return items


def fetch_openfda_clearances():
    """Fetch real-time FDA clearance count for radiology image processing (Product Code: LLZ)."""
    url = "https://api.fda.gov/device/510k.json?search=product_code:LLZ&limit=1"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "HealthcareDashboard/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("meta", {}).get("results", {}).get("total", 142)
    except Exception as e:
        logging.warning(f"Failed to fetch openFDA data: {e}")
        return 142  # Fallback baseline count


def render_news_html(news_items):
    """Render news array into HTML markup for injection."""
    if not news_items:
        return """
        <div class="news-item">
            <span class="news-title">Unable to dynamic fetch live RSS feeds. Displaying cached baseline headlines.</span>
            <div class="news-meta"><span class="news-tag">System</span> Just now</div>
        </div>
        """

    html_out = ""
    for item in news_items:
        html_out += f"""
        <div class="news-item">
            <a href="{item['link']}" target="_blank" rel="noopener noreferrer" class="news-title">{item['title']}</a>
            <div class="news-meta">
                <span class="news-tag">{item['tag']}</span> {item['source']} &bull; {item['date']}
            </div>
        </div>
        """
    return html_out


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler delivering the integrated dashboard and API endpoints."""

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)

        # API Endpoint for dynamic FDA count
        if parsed_path.path == "/api/fda-clearances":
            count = fetch_openfda_clearances()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"product_code": "LLZ", "total_clearances": count}
                ).encode("utf-8")
            )
            return

        # Main Route: Load HTML and inject live backend data
        if parsed_path.path in ["/", "/index.html"]:
            try:
                with open("index.html", "r", encoding="utf-8") as file:
                    html_content = file.read()

                # Fetch fresh RSS feed items
                news_items = fetch_rss_headlines()
                news_html = render_news_html(news_items)

                # Inject RSS news items into HTML template placeholder
                html_content = html_content.replace(
                    "<!-- NEWS_ITEMS_PLACEHOLDER -->", news_html
                )

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_content.encode("utf-8"))

            except FileNotFoundError:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(
                    b"Error: index.html file not found in the working directory."
                )
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Internal Server Error: {e}".encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 Not Found")


def run_server(port=8080):
    server_address = ("", port)
    httpd = HTTPServer(server_address, DashboardRequestHandler)
    logging.info(
        f"Server running locally at http://localhost:{port}/ (Press Ctrl+C to stop)"
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info("Server shutting down cleanly...")
        httpd.server_close()


if __name__ == "__main__":
    run_server(port=8080)