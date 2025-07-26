import requests
from bs4 import BeautifulSoup
import json
import time
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import schedule
from datetime import datetime, time as dt_time
import logging
import pytz

# Your Configuration
TELEGRAM_TOKEN = "6686777921:AAE3o3dGRJOLHWAzf4TqNLiJ6RaGEczIl4E"
CHAT_ID = "-1002628859007"
EMAIL = "excelyourtrade@gmail.com"
SENDER_EMAIL = "excelyourtrade@gmail.com"
APP_PASSWORD = "bxph anbw sqbx vezk"
SCANNER_URL = "https://chartink.com/screener/copy-2112-chartpulse-cp-swing-trade"

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ChartinkMonitor:
    def __init__(self):
        self.previous_stocks = {}
        self.session = requests.Session()
        self.ist = pytz.timezone('Asia/Kolkata')
        
        # Set headers to mimic browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
    
    def is_market_hours(self):
        """Check if it's within market hours (9:15 AM - 3:15 PM IST, Mon-Fri)"""
        now = datetime.now(self.ist)
        
        # Check if it's weekend
        if now.weekday() >= 5:  # 5=Saturday, 6=Sunday
            return False
        
        current_time = now.time()
        market_open = dt_time(9, 15)
        market_close = dt_time(15, 15)
        
        return market_open <= current_time <= market_close
    
    def get_csrf_token(self):
        """Get CSRF token from scanner page"""
        try:
            response = self.session.get(SCANNER_URL)
            soup = BeautifulSoup(response.content, 'html.parser')
            token = soup.find('meta', {'name': 'csrf-token'})
            if token:
                return token['content']
            return None
        except Exception as e:
            logging.error(f"Error getting CSRF token: {e}")
            return None
    
    def get_scan_clause(self):
        """Extract scan clause from scanner page"""
        try:
            response = self.session.get(SCANNER_URL)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for textarea with scan clause
            textarea = soup.find('textarea', {'id': 'scanner_code'})
            if textarea and textarea.get('value'):
                return textarea['value']
            
            # Alternative: look in script tags
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'scan_clause' in script.string:
                    content = script.string
                    start = content.find('"scan_clause":"') + 15
                    end = content.find('"', start)
                    if start > 14 and end > start:
                        return content[start:end].replace('\\', '')
            
            # Default scan clause for your scanner
            return """( {33489} ( latest close > latest sma( latest close , 20 ) and latest rsi( 14 ) > 50 and latest ema( latest close , 9 ) > latest ema( latest close , 21 ) ) )"""
            
        except Exception as e:
            logging.error(f"Error extracting scan clause: {e}")
            return ""
    
    def fetch_scanner_results(self):
        """Fetch current scanner results with stock prices"""
        try:
            csrf_token = self.get_csrf_token()
            if not csrf_token:
                logging.error("Could not get CSRF token")
                return {}
            
            scan_clause = self.get_scan_clause()
            
            headers = {
                'X-CSRF-TOKEN': csrf_token,
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': SCANNER_URL
            }
            
            data = {
                'scan_clause': scan_clause,
                'sort_by': 'name',
                'sort_order': 'asc'
            }
            
            response = self.session.post('https://chartink.com/screener/process', 
                                       headers=headers, data=data)
            
            if response.status_code == 200:
                result = response.json()
                stocks_data = {}
                
                if 'data' in result and result['data']:
                    for stock in result['data']:
                        stock_name = stock.get('name', 'Unknown')
                        stock_close = stock.get('close', 0)
                        stocks_data[stock_name] = stock_close
                
                logging.info(f"Fetched {len(stocks_data)} stocks from scanner")
                return stocks_data
            else:
                logging.error(f"Scanner request failed: {response.status_code}")
                return {}
            
        except Exception as e:
            logging.error(f"Error fetching scanner results: {e}")
            return {}
    
    def send_telegram_message(self, message):
        """Send message to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {
                'chat_id': CHAT_ID,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error sending Telegram message: {e}")
            return False
    
    def send_email(self, subject, body):
        """Send email notification"""
        try:
            message = MimeMultipart()
            message["From"] = SENDER_EMAIL
            message["To"] = EMAIL
            message["Subject"] = subject
            
            message.attach(MimeText(body, "plain"))
            
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(message)
            server.quit()
            
            return True
        except Exception as e:
            logging.error(f"Error sending email: {e}")
            return False
    
    def check_for_changes(self):
        """Main monitoring function"""
        if not self.is_market_hours():
            logging.info("Outside market hours, skipping check")
            return
        
        current_stocks = self.fetch_scanner_results()
        
        if not current_stocks:
            logging.warning("No stocks fetched, skipping this check")
            return
        
        if not self.previous_stocks:
            # First run during market hours
            self.previous_stocks = current_stocks
            logging.info(f"Initialized with {len(current_stocks)} stocks")
            return
        
        # Find new and removed stocks
        current_names = set(current_stocks.keys())
        previous_names = set(self.previous_stocks.keys())
        
        new_stocks = current_names - previous_names
        removed_stocks = previous_names - current_names
        
        if new_stocks or removed_stocks:
            timestamp = datetime.now(self.ist).strftime("%d-%m-%Y %H:%M:%S IST")
            
            message = f"🔔 <b>Chartink Scanner Update</b>\n"
            message += f"📅 {timestamp}\n\n"
            
            if new_stocks:
                message += f"✅ <b>New Stocks ({len(new_stocks)}):</b>\n"
                for stock in sorted(new_stocks):
                    price = current_stocks[stock]
                    message += f"• {stock}: ₹{price:.2f}\n"
                message += "\n"
            
            if removed_stocks:
                message += f"❌ <b>Removed Stocks ({len(removed_stocks)}):</b>\n"
                for stock in sorted(removed_stocks):
                    price = self.previous_stocks[stock]
                    message += f"• {stock}: ₹{price:.2f}\n"
            
            # Send notifications
            if self.send_telegram_message(message):
                logging.info("Telegram alert sent successfully")
            
            # Send email
            email_subject = f"Chartink Alert: {len(new_stocks)} New, {len(removed_stocks)} Removed"
            email_body = message.replace('<b>', '').replace('</b>', '').replace('🔔', '').replace('📅', '').replace('✅', '').replace('❌', '').replace('•', '-')
            
            if self.send_email(email_subject, email_body):
                logging.info("Email alert sent successfully")
        
        # Update previous stocks
        self.previous_stocks = current_stocks

def run_monitor():
    """Run the monitoring system"""
    monitor = ChartinkMonitor()
    
    # Check every 3 minutes during market hours
    schedule.every(3).minutes.do(monitor.check_for_changes)
    
    logging.info("🚀 Chartink Scanner Monitor Started!")
    logging.info("⏰ Monitoring: Monday-Friday, 9:15 AM - 3:15 PM IST")
    logging.info("🔄 Check Interval: Every 3 minutes")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute for scheduled tasks
        except KeyboardInterrupt:
            logging.info("Monitor stopped by user")
            break
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            time.sleep(300)  # Wait 5 minutes before retrying

if __name__ == "__main__":
    run_monitor()
