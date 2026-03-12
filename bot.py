import requests
from bs4 import BeautifulSoup
import smtplib
from email.message import EmailMessage
import os
import time
from dotenv import load_dotenv
from urllib.parse import urljoin
from datetime import datetime

# ==============================
# LOAD ENV VARIABLES
# ==============================

load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

URL = "https://www.bitsindri.ac.in/"
CHECK_INTERVAL = 36000  # 10 hours
LAST_NOTICE_FILE = "last_notice.txt"
PDF_FILENAME = "notice.pdf"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


# ==============================
# GET LATEST NOTICE FROM GENERAL TAB
# ==============================

def get_latest_notice():
    res = requests.get(URL, headers=HEADERS, timeout=15)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    # Find General tab content by looping and checking class list
    general_content = None
    for div in soup.find_all("div", class_="tab-content"):
        classes = div.get("class", [])
        if "tab-a956264" in classes:
            general_content = div
            break

    if not general_content:
        raise ValueError("General tab content not found.")

    # Get only the FIRST notice
    notice = general_content.find("article", class_="jkit-post post-list-item")

    if not notice:
        raise ValueError("No notice found inside General tab.")

    link_tag = notice.find("a")
    title_tag = notice.find("span", class_="jkit-postlist-title")

    if not link_tag or not title_tag:
        raise ValueError("Could not extract title or link.")

    title = title_tag.text.strip()
    link = link_tag["href"]

    return title, link


# ==============================
# FIND PDF LINK
# ==============================

def get_pdf_link(notice_link):
    res = requests.get(notice_link, headers=HEADERS, timeout=15)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    pdf = soup.find("a", href=lambda x: x and x.lower().endswith(".pdf"))

    if pdf:
        return urljoin(notice_link, pdf["href"])

    return None


# ==============================
# DOWNLOAD PDF
# ==============================

def download_pdf(pdf_url):
    r = requests.get(pdf_url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    with open(PDF_FILENAME, "wb") as f:
        f.write(r.content)

    return PDF_FILENAME


# ==============================
# SEND EMAIL (multiple receivers)
# ==============================

def send_email(title, file_path=None):
    if not EMAIL_RECEIVER:
        raise ValueError("EMAIL_RECEIVER is not set in .env file")

    if not EMAIL_SENDER:
        raise ValueError("EMAIL_SENDER is not set in .env file")

    if not EMAIL_PASSWORD:
        raise ValueError("EMAIL_PASSWORD is not set in .env file")

    msg = EmailMessage()
    msg["Subject"] = f"New BIT Sindri Notice: {title}"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    msg.set_content(
        f"A new notice has been published on BIT Sindri website.\n\nTitle:\n{title}\n\n"
        f"{'A PDF attachment has been included.' if file_path else 'No PDF was found for this notice.'}"
    )

    if file_path and os.path.exists(file_path):
        with open(file_path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="pdf",
                filename="notice.pdf"
            )

    receivers = [r.strip() for r in EMAIL_RECEIVER.split(",")]

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
        for receiver in receivers:
            msg.replace_header("To", receiver)
            smtp.send_message(msg)
            print(f"✅ Email sent to {receiver}")


# ==============================
# READ / WRITE LAST NOTICE
# ==============================

def read_last_notice():
    if not os.path.exists(LAST_NOTICE_FILE):
        return ""
    with open(LAST_NOTICE_FILE, "r") as f:
        return f.read().strip()


def write_last_notice(link):
    with open(LAST_NOTICE_FILE, "w") as f:
        f.write(link)


# ==============================
# CHECK FOR NEW NOTICE
# ==============================

def check_notice():
    print(f"\n🔍 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking General tab notices...")

    title, link = get_latest_notice()
    last_link = read_last_notice()

    if link != last_link:
        print(f"🚨 New notice found: {title}")

        pdf_link = get_pdf_link(link)

        if pdf_link:
            print(f"📄 Downloading PDF: {pdf_link}")
            file = download_pdf(pdf_link)
            send_email(title, file_path=file)
        else:
            print("⚠️  No PDF found. Sending email without attachment.")
            send_email(title, file_path=None)

        write_last_notice(link)
    else:
        print("✅ No new notice.")


# ==============================
# RUN BOT
# ==============================

if __name__ == "__main__":
    print("🤖 BIT Sindri Notice Bot started.")

    while True:
        try:
            check_notice()
        except Exception as e:
            print(f"❌ Error: {e}")

        time.sleep(CHECK_INTERVAL)
