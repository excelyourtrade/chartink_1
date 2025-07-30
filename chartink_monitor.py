import requests
from bs4 import BeautifulSoup
import time
import smtplib
import email.mime.text
import email.mime.multipart
from datetime import datetime, timedelta
import logging
import pytz
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Your Configuration
TELEGRAM_TOKEN = "6686777921:AAE3o3dGRJOLHWAzf4TqNLiJ6RaGEczIl4E"
CHAT_ID = "-1002628859007"
EMAIL = "excelyourtrade@gmail.com"
SENDER_EMAIL = "excelyourtrade@gmail.com"
APP_PASSWORD = "bxph anbw sqbx vezk"
SCANNER_URL = "https://chartink.com/screener/copy-2112-chartpulse-cp-swing-trade"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class WebsiteBacktestMonitor:
    def __init__(self):
        self.previous_backtest_stocks = {}  # {date: [stock_names]}
        self.ist = pytz.timezone('Asia/Kolkata')
        self.target_date = "29-07-2025"
        self.driver = None
        
    def setup_browser(self):
        """Setup headless Chrome browser"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            return True
        except Exception as e:
            logging.error(f"Browser setup failed: {e}")
            return False
    
    def get_backtest_results(self):
        """Scrape backtest results from the actual website"""
        try:
            if not self.driver:
                if not self.setup_browser():
                    return {}
            
            # Load the scanner page
            self.driver.get(SCANNER_URL)
            time.sleep(5)
            
            # Look for backtest results button and click it
            try:
                backtest_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'backtest') or contains(text(), 'Backtest')]"))
                )
                backtest_button.click()
                time.sleep(3)
            except:
                logging.error("Backtest button not found")
                return {}
            
            # Extract date-wise results
            backtest_data = {}
            
            # Look for date sections in the backtest results
            date_sections = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'date') or contains(text(), '2025')]")
            
            for section in date_sections:
                try:
                    # Extract date from section
                    section_text = section.text
                    if "29-07-2025" in section_text or "29/07/2025" in section_text or "Jul 29" in section_text:
                        # This section contains results for our target date
                        
                        # Find stock names in this section
                        stocks_in_section = []
                        stock_elements = section.find_elements(By.XPATH, ".//following-sibling::*//td[contains(@class, 'name')] | .//following-sibling::*//a[contains(@href, 'quote')]")
                        
                        for stock_elem in stock_elements[:10]:  # Limit to first 10 to avoid overflow
                            stock_name = stock_elem.text.strip()
                            if stock_name and len(stock_name) > 2:
                                stocks_in_section.append(stock_name)
                        
                        if stocks_in_section:
                            backtest_data[self.target_date] = stocks_in_section
                            break
                
                except Exception as e:
                    continue
            
            return backtest_data
            
        except Exception as e:
            logging.error(f"Backtest scraping error: {e}")
            return {}
    
    def send_telegram(self, message):
        """Send Telegram message"""
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {
                'chat_id': CHAT_ID,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            response = requests.post(url, data=data, timeout=15)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Telegram error: {e}")
            return False
    
    def send_email(self, subject, body):
        """Send email"""
        try:
            msg = email.mime.multipart.MIMEMultipart()
            msg["From"] = SENDER_EMAIL
            msg["To"] = EMAIL
            msg["Subject"] = subject
            msg.attach(email.mime.text.MIMEText(body, "plain"))
            
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            logging.error(f"Email error: {e}")
            return False
    
    def check_backtest_changes(self):
        """Check for new stocks in backtest results"""
        current_backtest = self.get_backtest_results()
        
        if self.target_date in current_backtest:
            current_stocks = set(current_backtest[self.target_date])
            previous_stocks = set(self.previous_backtest_stocks.get(self.target_date, []))
            
            new_stocks = current_stocks - previous_stocks
            
            if new_stocks:
                timestamp = datetime.now(self.ist).strftime("%d-%m-%Y %H:%M:%S IST")
                
                alert_msg = f"🎯 <b>BACKTEST ALERT - New Stocks for {self.target_date}!</b>\n\n"
                alert_msg += f"⏰ <b>Detected at:</b> {timestamp}\n"
                alert_msg += f"📊 <b>Source:</b> Website backtest results\n\n"
                alert_msg += f"🟢 <b>NEW STOCKS FOR {self.target_date} ({len(new_stocks)}):</b>\n\n"
                
                for stock in sorted(new_stocks):
                    alert_msg += f"• <b>{stock}</b>\n"
                
                alert_msg += f"\n💡 <b>These stocks appeared in backtest results for {self.target_date}!</b>\n"
                alert_msg += f"🎯 <b>This is the GALLANTT-type alert you wanted!</b>"
                
                # Send alerts
                self.send_telegram(alert_msg)
                self.send_email(f"🎯 BACKTEST: New stocks for {self.target_date}", alert_msg)
                
                logging.info(f"🎯 BACKTEST ALERT: {new_stocks} for {self.target_date}")
            
            # Update previous stocks
            self.previous_backtest_stocks[self.target_date] = list(current_stocks)
    
    def cleanup(self):
        """Clean up browser"""
        if self.driver:
            self.driver.quit()

def main():
    monitor = WebsiteBacktestMonitor()
    
    try:
        # Send startup message
        startup_msg = f"🌐 <b>WEBSITE BACKTEST MONITOR</b>\n\n"
        startup_msg += f"🎯 <b>Method:</b> Scrape actual website backtest results\n"
        startup_msg += f"📅 <b>Target:</b> {monitor.target_date}\n"
        startup_msg += f"🔍 <b>Source:</b> Browser automation on chartink.com\n"
        startup_msg += f"⚡ <b>This will catch GALLANTT in backtest results!</b>"
        
        monitor.send_telegram(startup_msg)
        logging.info("🌐 Website Backtest Monitor Started")
        
        while True:
            monitor.check_backtest_changes()
            time.sleep(300)  # Check every 5 minutes
            
    except KeyboardInterrupt:
        logging.info("Monitor stopped")
    finally:
        monitor.cleanup()

if __name__ == "__main__":
    main()
        
