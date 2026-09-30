<!--This script runs on a cloud server that automatically builds and updates your dashboard whenever anyone visits the website:   
    Gathers live data: It fetches real-time headlines from medical RSS feeds and queries the openFDA API for device clearance counts.   
    Creates AI analysis: It sends this data to Gemini to generate professional market summaries, sentiment badges, and statistical metrics.   
    Injects and serves: It reads your HTML template, replaces all the placeholders with the fresh live data and charts, 
    and delivers the finished web page to the visitor's browser.-->

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from google import genai
from google.genai import types

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


# Fetches and parses live headlines from medical RSS feeds
def fetch_rss_headlines():
    items = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HealthcareDashboard/1.0"
    }

    for source_name, url in RSS_FEEDS.items():
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                xml_data = response.read().decode("utf-8", errors="ignore")

            raw_items = re.findall(r"<item>(.*?)</item>", xml_data, re.DOTALL)

            for raw_item in raw_items[:3]:
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


# Queries openFDA API for real-time device clearance counts (Product Code: LLZ)
def fetch_openfda_clearances():
    url = "https://api.fda.gov/device/510k.json?search=product_code:LLZ&limit=1"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "HealthcareDashboard/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("meta", {}).get("results", {}).get("total", "Currently unavailable")
    except Exception as e:
        logging.warning(f"Failed to fetch openFDA data: {e}")
        return "Currently unavailable"


# Uses Gemini to synthesise news headlines and clearance metrics into structured market JSON
def generate_gemini_outlook(news_items, fda_count):
    client = genai.Client()

    headlines_text = "\n".join(
        [f"- {item['title']} ({item['source']})" for item in news_items]
    )

    prompt = f"""
    You are a medical technology market analyst. Based on the following live RSS headlines 
    and recent FDA clearance count ({fda_count} total LLZ clearances):
    1. badge: Sentiment badge (e.g., "Bullish").
    2. summary: Professional Sector Outlook Summary (3-4 sentences).
    3. policy_rate: G7 weighted average central bank policy rate (e.g., "3.85%").
    4. healthcare_inflation: Global healthcare services inflation rate (e.g., "3.8%").
    5. medtech_index: Health Care Select Sector SPDR Fund (XLV) index value (e.g., "$142.5").
    6. imaging_backlog: Estimated global pending scans (e.g., "4.2M").
    7. cloud_inference: Compute cost YoY change (e.g., "-8.5%").
    8. vacancy_rate: Radiologist vacancy rate (e.g., "28%").
    9. reimbursement_adoption: Hospitals with active billing (e.g., "42%").
    10. clinical_validation: Peer-reviewed papers YTD (e.g., "340").
    11. modality_description: A descriptive paragraph explaining modality clearances (focusing on CT, MRI, Digital Pathology, and POCUS).
    12. drivers: 4 primary growth drivers as a list of objects with keys "title" and "text".
    13. headwinds: 4 key sector headwinds as a list of objects with keys "title" and "text".
    14. highlights: 3 regional operational highlights as a list of objects with keys "title" and "text".
    15. Revenue figures & vendor breakdown arrays (top 5 vendors: Siemens Healthineers, GE HealthCare, Philips, Aidoc, Fujifilm/Others):
        - total_overall_rev (e.g., "$2.1B")
        - cardiology_rev (e.g., "$580M")
        - pulmonology_rev (e.g., "$450M")
        - neurology_rev (e.g., "$510M")
        - breast_rev (e.g., "$320M")
        - oncology_rev (e.g., "$240M")
        - total_vendor_data (array of 5 numbers summing to 100 or total revenue share)
        - cardio_vendor_data, pulmo_vendor_data, neuro_vendor_data, breast_vendor_data, oncology_vendor_data (arrays of 5 numbers each)

    Recent Headlines:
    {headlines_text}
    
    Return your response strictly as valid JSON containing all these keys.
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        logging.warning(f"Failed to generate Gemini outlook: {e}")
        return {
            "badge": "Unavailable",
            "summary": "Live analysis currently unavailable.",
            "policy_rate": "Unavailable",
            "healthcare_inflation": "Unavailable",
            "medtech_index": "Unavailable",
            "imaging_backlog": "Unavailable",
            "cloud_inference": "Unavailable",
            "vacancy_rate": "Unavailable",
            "reimbursement_adoption": "Unavailable",
            "clinical_validation": "Unavailable",
            "modality_description": "Data currently unavailable.",
            "drivers": [],
            "headwinds": [],
            "highlights": [],
            "total_overall_rev": "Unavailable",
            "cardiology_rev": "Unavailable",
            "pulmonology_rev": "Unavailable",
            "neurology_rev": "Unavailable",
            "breast_rev": "Unavailable",
            "oncology_rev": "Unavailable",
            "total_vendor_data": [35, 25, 20, 12, 8],
            "cardio_vendor_data": [30, 30, 20, 15, 5],
            "pulmo_vendor_data": [40, 25, 15, 12, 8],
            "neuro_vendor_data": [35, 20, 25, 15, 5],
            "breast_vendor_data": [25, 35, 20, 10, 10],
            "oncology_vendor_data": [30, 25, 25, 10, 10]
        }


# Renders news items list into HTML markup
def render_news_html(news_items):
    if not news_items:
        return """
        <div class="news-item">
            <span class="news-title">Unable to fetch live RSS feeds.</span>
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


# Renders dynamic factor cards into HTML markup
def render_factor_cards(items):
    if not items:
        return "<div class='factor-card'><div class='factor-text'>Data unavailable</div></div>"
    html_out = ""
    for item in items:
        html_out += f"""
        <div class="factor-card">
            <div class="factor-card-title">{item.get('title', '')}</div>
            <div class="factor-card-text">{item.get('text', '')}</div>
        </div>
        """
    return html_out


# Handles incoming HTTP requests for the dashboard and API routes
class DashboardRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)

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

        if parsed_path.path in ["/", "/1_ai_6.html", "/1_ai.html"]:
            try:
                # Open your HTML file template
                html_filename = "1_ai_6.html" if os.path.exists("1_ai_6.html") else "1_ai.html"
                with open(html_filename, "r", encoding="utf-8") as file:
                    html_content = file.read()

                # Fetch fresh data and generate Gemini analysis
                news_items = fetch_rss_headlines()
                news_html = render_news_html(news_items)
                fda_count = fetch_openfda_clearances()
                ai_analysis = generate_gemini_outlook(news_items, fda_count)

                # Render dynamic factor cards
                drivers_html = render_factor_cards(ai_analysis.get("drivers", []))
                headwinds_html = render_factor_cards(ai_analysis.get("headwinds", []))
                highlights = ai_analysis.get("highlights", [{}, {}, {}])

                # Inject all metrics, ticker values, and text placeholders
                html_content = html_content.replace("<!-- NEWS_ITEMS_PLACEHOLDER -->", news_html)
                html_content = html_content.replace("<!-- OUTLOOK_BADGE_PLACEHOLDER -->", ai_analysis.get("badge", ""))
                html_content = html_content.replace("<!-- OUTLOOK_SUMMARY_PLACEHOLDER -->", ai_analysis.get("summary", ""))
                
                # Tickers
                html_content = html_content.replace("<!-- POLICY_RATE_PLACEHOLDER -->", ai_analysis.get("policy_rate", ""))
                html_content = html_content.replace("<!-- HEALTHCARE_INFLATION_PLACEHOLDER -->", ai_analysis.get("healthcare_inflation", ""))
                html_content = html_content.replace("<!-- MEDTECH_INDEX_PLACEHOLDER -->", ai_analysis.get("medtech_index", ""))
                html_content = html_content.replace("<!-- IMAGING_BACKLOG_PLACEHOLDER -->", ai_analysis.get("imaging_backlog", ""))
                html_content = html_content.replace("<!-- CLOUD_INFERENCE_PLACEHOLDER -->", ai_analysis.get("cloud_inference", ""))

                # Drivers & Headwinds
                html_content = html_content.replace("<!-- DRIVERS_CARDS_PLACEHOLDER -->", drivers_html)
                html_content = html_content.replace("<!-- HEADWINDS_CARDS_PLACEHOLDER -->", headwinds_html)

                # Regional Highlights Footer
                for i in range(3):
                    hl = highlights[i] if i < len(highlights) else {}
                    html_content = html_content.replace(f"<!-- HL{i+1}_TITLE_PLACEHOLDER -->", hl.get("title", ""))
                    html_content = html_content.replace(f"<!-- HL{i+1}_TEXT_PLACEHOLDER -->", hl.get("text", ""))

                # Key Sector Metrics Cards
                html_content = html_content.replace("<!-- CLEARANCES_METRIC_PLACEHOLDER -->", str(fda_count))
                html_content = html_content.replace("<!-- VACANCY_RATE_PLACEHOLDER -->", ai_analysis.get("vacancy_rate", ""))
                html_content = html_content.replace("<!-- REIMBURSEMENT_ADOPTION_PLACEHOLDER -->", ai_analysis.get("reimbursement_adoption", ""))
                html_content = html_content.replace("<!-- CLINICAL_VALIDATION_PLACEHOLDER -->", ai_analysis.get("clinical_validation", ""))

                # Modality Description
                html_content = html_content.replace("<!-- MODALITY_DESCRIPTION_PLACEHOLDER -->", ai_analysis.get("modality_description", ""))

                # Vendor Revenue Breakdown Placeholders
                html_content = html_content.replace("<!-- TOTAL_OVERALL_REV_PLACEHOLDER -->", ai_analysis.get("total_overall_rev", ""))
                html_content = html_content.replace("<!-- CARDIOLOGY_REV_PLACEHOLDER -->", ai_analysis.get("cardiology_rev", ""))
                html_content = html_content.replace("<!-- PULMONOLOGY_REV_PLACEHOLDER -->", ai_analysis.get("pulmonology_rev", ""))
                html_content = html_content.replace("<!-- NEUROLOGY_REV_PLACEHOLDER -->", ai_analysis.get("neurology_rev", ""))
                html_content = html_content.replace("<!-- BREAST_REV_PLACEHOLDER -->", ai_analysis.get("breast_rev", ""))
                html_content = html_content.replace("<!-- ONCOLOGY_REV_PLACEHOLDER -->", ai_analysis.get("oncology_rev", ""))

                # Vendor Pie Chart Dataset Arrays (JSON stringified)
                html_content = html_content.replace("<!-- TOTAL_VENDOR_DATA_PLACEHOLDER -->", json.dumps(ai_analysis.get("total_vendor_data", [35, 25, 20, 12, 8])))
                html_content = html_content.replace("<!-- CARDIO_VENDOR_DATA_PLACEHOLDER -->", json.dumps(ai_analysis.get("cardio_vendor_data", [30, 30, 20, 15, 5])))
                html_content = html_content.replace("<!-- PULMO_VENDOR_DATA_PLACEHOLDER -->", json.dumps(ai_analysis.get("pulmo_vendor_data", [40, 25, 15, 12, 8])))
                html_content = html_content.replace("<!-- NEURO_VENDOR_DATA_PLACEHOLDER -->", json.dumps(ai_analysis.get("neuro_vendor_data", [35, 20, 25, 15, 5])))
                html_content = html_content.replace("<!-- BREAST_VENDOR_DATA_PLACEHOLDER -->", json.dumps(ai_analysis.get("breast_vendor_data", [25, 35, 20, 10, 10])))
                html_content = html_content.replace("<!-- ONCOLOGY_VENDOR_DATA_PLACEHOLDER -->", json.dumps(ai_analysis.get("oncology_vendor_data", [30, 25, 25, 10, 10])))

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_content.encode("utf-8"))

            except FileNotFoundError:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(
                    b"Error: HTML file not found in the working directory."
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


# Initialises and starts the local HTTP server
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
