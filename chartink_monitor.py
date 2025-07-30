import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import smtplib
import email.mime.text
import email.mime.multipart
from datetime import datetime, timedelta
import logging
import pytz
import os
import glob

# Your Configuration
TELEGRAM_TOKEN = "6686777921:AAE3o3dGRJOLHWAzf4TqNLiJ6RaGEczIl4E"
CHAT_ID = "-1002628859007"
EMAIL = "excelyourtrade@gmail.com"
SENDER_EMAIL = "excelyourtrade@gmail.com"
APP_PASSWORD = "bxph anbw sqbx vezk"
SCANNER_URL = "https://chartink.com/screener/copy-2112-chartpulse-cp-swing-trade"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class CSVYesterdayMonitor:
    def __init__(self):
        self.previous_yesterday_stocks = set()
        self.ist = pytz.timezone('Asia/Kolkata')
        self.driver = None
        self.download_dir = "/tmp/chartink_downloads"
        
        # Calculate yesterday's date
        yesterday = datetime.now(self.ist) - timedelta(days=1)
        while yesterday.weekday() >= 5:  # Skip weekends
            yesterday -= timedelta(days=1)
        self.target_date = yesterday.strftime('%Y-%m-%d')
        self.target_date_display = yesterday.strftime('%d-%m-%Y')
        
        # Create download directory
        os.makedirs(self.download_dir, exist_ok=True)
    
    def setup_browser(self):
        """Setup Chrome browser with download preferences"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Set download preferences
            prefs = {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            return True
        except Exception as e:
            logging.error(f"Browser setup failed: {e}")
            return False
    
    def download_csv(self):
        """Download CSV from Chartink using browser automation"""
        try:
            if not self.driver:
                if not self.setup_browser():
                    return None
            
            # Clear previous downloads
            for file in glob.glob(f"{self.download_dir}/*.csv"):
                os.remove(file)
            
            # Load scanner page
            logging.info("Loading scanner page...")
            self.driver.get(SCANNER_URL)
            time.sleep(5)
            
            # Wait for page to load and find CSV download button
            try:
                # Look for download CSV button (multiple possible selectors)
                download_selectors = [
                    "//a[contains(text(), 'Download csv') or contains(text(), 'CSV') or contains(text(), 'download')]",
                    "//button[contains(text(), 'Download') or contains(text(), 'CSV')]",
                    "//a[@href*='csv']",
                    "//a[contains(@class, 'download')]"
                ]
                
                download_button = None
                for selector in download_selectors:
                    try:
                        download_button = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        break
                    except:
                        continue
                
                if not download_button:
                    logging.error("Download button not found")
                    return None
                
                # Click download
                logging.info("Clicking download button...")
                download_button.click()
                time.sleep(10)  # Wait for download to complete
                
                # Find downloaded CSV file
                csv_files = glob.glob(f"{self.download_dir}/*.csv")
                if csv_files:
                    latest_csv = max(csv_files, key=os.path.getctime)
                    logging.info(f"Downloaded CSV: {latest_csv}")
                    return latest_csv
                else:
                    logging.error("No CSV file found after download")
                    return None
                    
            except Exception as e:
                logging.error(f"Download process failed: {e}")
                return None
                
        except Exception as e:
            logging.error(f"CSV download error: {e}")
            return None
    
    def parse_csv_for_yesterday(self, csv_file):
        """Parse CSV and extract stocks for yesterday's date"""
        try:
            # Read CSV file
            df = pd.read_csv(csv_file)
            logging.info(f"CSV loaded with {len(df)} rows")
            
            # Look for date column (various possible names)
            date_columns = ['date', 'Date', 'per_chg_date', 'scan_date', 'Date Time']
            date_col = None
            
            for col in date_columns:
                if col in df.columns:
                    date_col = col
                    break
            
            if not date_col:
                # If no date column, assume all stocks are recent and filter by target date logic
                logging.warning("No date column found, using all stocks")
                yesterday_stocks = {}
                for _, row in df.iterrows():
                    stock_name = row.get('name', row.get('Name', 'Unknown'))
                    stock_price = row.get('close', row.get('Close', row.get('price', 0)))
                    if stock_name != 'Unknown':
                        yesterday_stocks[stock_name] = stock_price
                return yesterday_stocks
            
            # Filter for yesterday's date
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            yesterday_data = df[df[date_col].dt.strftime('%Y-%m-%d') == self.target_date]
            
            yesterday_stocks = {}
            for _, row in yesterday_data.iterrows():
                stock_name = row.get('name', row.get('Name', 'Unknown'))
                stock_price = row.get('close', row.get('Close', row.get('price', 0)))
                if stock_name != 'Unknown':
                    yesterday_stocks[stock_name] = stock_price
            
            logging.info(f"Found {len(yesterday_stocks)} stocks for {self.target_date}")
            return yesterday_stocks
            
        except Exception as e:
            logging.error(f"CSV parsing error: {e}")
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
    
    def check_yesterday_csv_data(self):
        """Main function to check CSV data for yesterday's stocks"""
        # Download CSV
        csv_file = self.download_csv()
        if not csv_file:
            logging.error("Failed to download CSV")
            return
        
        # Parse CSV for yesterday's data
        current_yesterday_stocks = self.parse_csv_for_yesterday(csv_file)
        current_stock_names = set(current_yesterday_stocks.keys())
        
        # Find new stocks for yesterday
        new_yesterday_stocks = current_stock_names - self.previous_yesterday_stocks
        
        if new_yesterday_stocks:
            timestamp = datetime.now(self.ist).strftime("%d-%m-%Y %H:%M:%S IST")
            
            alert_msg = f"📊 <b>CSV ALERT - New Stocks for Yesterday!</b>\n\n"
            alert_msg += f"📅 <b>Date:</b> {self.target_date_display}\n"
            alert_msg += f"⏰ <b>Detected:</b> {timestamp}\n"
            alert_msg += f"📁 <b>Source:</b> Downloaded CSV file\n\n"
            alert_msg += f"🟢 <b>NEW STOCKS FOR {self.target_date_display} ({len(new_yesterday_stocks)}):</b>\n\n"
            
            for stock in sorted(new_yesterday_stocks):
                price = current_yesterday_stocks.get(stock, 0)
                alert_msg += f"• <b>{stock}</b> - ₹{price:.2f}\n"
            
            alert_msg += f"\n💡 <b>These stocks appeared in CSV for {self.target_date_display}!</b>\n"
            alert_msg += f"🎯 <b>Perfect for catching GALLANTT-type repainting!</b>"
            
            # Send alerts
            telegram_sent = self.send_telegram(alert_msg)
            email_sent = self.send_email(
                f"📊 CSV ALERT: {len(new_yesterday_stocks)} stocks for {self.target_date_display}",
                alert_msg.replace('<b>', '').replace('</b>', '').replace('📊', '').replace('📅', '').replace('⏰', '').replace('📁', '').replace('🟢', '').replace('💡', '').replace('🎯', '').replace('•', '-')
            )
            
            logging.info(f"📊 CSV ALERT SENT: {new_yesterday_stocks} for {self.target_date_display}")
        
        # Update previous stocks
        self.previous_yesterday_stocks = current_stock_names
        
        # Clean up CSV file
        if os.path.exists(csv_file):
            os.remove(csv_file)
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()

def main():
    monitor = CSVYesterdayMonitor()
    
    try:
        # Send startup message
        startup_msg = f"📊 <b>CSV YESTERDAY MONITOR STARTED</b>\n\n"
        startup_msg += f"🎯 <b>Method:</b> Download CSV every 10 minutes\n"
        startup_msg += f"📅 <b>Target Date:</b> {monitor.target_date_display}\n"
        startup_msg += f"📁 <b>Source:</b> Direct CSV download (blob URL handled)\n"
        startup_msg += f"⚡ <b>Frequency:</b> Every 10 minutes during market hours\n\n"
        startup_msg += f"✅ <b>This will catch GALLANTT appearing in CSV for yesterday!</b>"
        
        monitor.send_telegram(startup_msg)
        logging.info(f"📊 CSV Monitor Started for {monitor.target_date_display}")
        
        check_count = 0
        
        while True:
            try:
                now = datetime.now(monitor.ist)
                if now.weekday() < 5 and 9 <= now.hour <= 16:  # Market hours
                    monitor.check_yesterday_csv_data()
                    check_count += 1
                    logging.info(f"Completed CSV check #{check_count}")
                
                time.sleep(600)  # Check every 10 minutes
                
            except KeyboardInterrupt:
                logging.info("CSV Monitor stopped")
                break
            except Exception as e:
                logging.error(f"Main loop error: {e}")
                time.sleep(300)  # Wait 5 minutes on error
                
    finally:
        monitor.cleanup()

if __name__ == "__main__":
    main()
        
