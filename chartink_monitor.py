import requests
from bs4 import BeautifulSoup
import json
import time
import smtplib
import email.mime.text
import email.mime.multipart
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

# Your ACTUAL scan clause
YOUR_SCAN_CLAUSE = """( {cash} ( ( {cash} ( quarterly gross sales > 1 quarter ago gross sales and quarterly foreign institutional investors percentage > 1 quarter ago foreign institutional investors percentage and net profit[yearly] > 0 and weekly cci( 34 ) > 100 and weekly high > 1.10 * latest close and 1 week ago high < 1.20 * yearly close and latest rsi( 14 ) >= 50 and market cap > 500 and latest ema( latest close , 50 ) > latest ema( latest close , 200 ) and latest ema( latest close , 10 ) > latest ema( latest close , 20 ) and latest ema( latest close , 20 ) > latest ema( latest close , 89 ) and latest ema( latest close , 89 ) > latest ema( latest close , 200 ) and latest close > 50 and latest close > latest ema( latest close , 10 ) ) ) ) )"""

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ChartinkMonitor:
    def __init__(self):
        self.previous_stocks = {}
        self.session = requests.Session()
        self.ist = pytz.timezone('Asia/Kolkata')
        self.initialized = False
        self.last_check_time = None
        
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
    
    def fetch_scanner_results(self):
        """Fetch current scanner results with stock prices using YOUR actual scan clause"""
        try:
            csrf_token = self.get_csrf_token()
            if not csrf_token:
                logging.error("Could not get CSRF token")
                return {}
            
            headers = {
                'X-CSRF-TOKEN': csrf_token,
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': SCANNER_URL,
                'Accept': 'application/json, text/javascript, */*; q=0.01'
            }
            
            data = {
                'scan_clause': YOUR_SCAN_CLAUSE,
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
                
                # Only log when there are changes or every 100 checks
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
            message = email.mime.multipart.MIMEMultipart()
            message["From"] = SENDER_EMAIL
            message["To"] = EMAIL
            message["Subject"] = subject
            
            message.attach(email.mime.text.MIMEText(body, "plain"))
            
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
        """Main monitoring function - ONLY alerts on actual changes"""
        # Skip if outside market hours
        if not self.is_market_hours():
            return
        
        current_stocks = self.fetch_scanner_results()
        self.last_check_time = datetime.now(self.ist)
        
        # First-time initialization (silent)
        if not self.initialized:
            self.previous_stocks = current_stocks
            self.initialized = True
            logging.info(f"Monitor initialized silently with {len(current_stocks)} stocks")
            return
        
        # Find changes (repainting detection)
        current_names = set(current_stocks.keys())
        previous_names = set(self.previous_stocks.keys())
        
        new_stocks = current_names - previous_names
        removed_stocks = previous_names - current_names
        
        # ONLY send alert if there are actual changes
        if new_stocks or removed_stocks:
            timestamp = datetime.now(self.ist).strftime("%d-%m-%Y %H:%M:%S IST")
            
            message = f"🚨 <b>STOCK ALERT - Scanner Change Detected!</b>\n"
            message += f"📅 {timestamp}\n\n"
            
            if new_stocks:
                message += f"🟢 <b>NEW STOCKS APPEARED ({len(new_stocks)}):</b>\n"
                for stock in sorted(new_stocks):
                    price = current_stocks[stock]
                    message += f"• <b>{stock}</b> - ₹{price:.2f}\n"
                message += "\n"
            
            if removed_stocks:
                message += f"🔴 <b>STOCKS DISAPPEARED ({len(removed_stocks)}):</b>\n"
                for stock in sorted(removed_stocks):
                    price = self.previous_stocks[stock]
                    message += f"• <b>{stock}</b> - ₹{price:.2f}\n"
                message += "\n"
            
            if new_stocks:
                message += f"💡 <i>New stocks may be due to repainting (historical data update) or live market movement!</i>"
            
            # Send notifications
            if self.send_telegram_message(message):
                logging.info(f"🚨 ALERT SENT: {len(new_stocks)} new, {len(removed_stocks)} removed")
            
            # Send email
            email_subject = f"🚨 URGENT: Chartink Alert - {len(new_stocks)} New Stocks!"
            email_body = message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', '').replace('🚨', '').replace('📅', '').replace('🟢', '').replace('🔴', '').replace('💡', '').replace('•', '-')
            
            if self.send_email(email_subject, email_body):
                logging.info("Email alert sent")
        
        # Update previous stocks
        self.previous_stocks = current_stocks

def run_monitor():
    """Run continuous monitoring system"""
    monitor = ChartinkMonitor()
    
    # Send one-time startup message
    startup_msg = f"🎯 <b>Continuous Scanner Monitor STARTED</b>\n\n"
    startup_msg += f"⚡ <b>Mode:</b> Continuous monitoring\n"
    startup_msg += f"🔍 <b>Check Frequency:</b> Every 30 seconds during market hours\n"
    startup_msg += f"⏰ <b>Market Hours:</b> Mon-Fri, 9:15 AM - 3:15 PM IST\n"
    startup_msg += f"🚨 <b>Alerts:</b> ONLY when stocks appear/disappear\n"
    startup_msg += f"🎯 <b>Purpose:</b> Catch repainting & live changes\n\n"
    startup_msg += f"✅ <b>Status:</b> Monitoring your scanner silently...\n"
    startup_msg += f"📴 <b>No routine updates</b> - only real alerts!"
    
    monitor.send_telegram_message(startup_msg)
    
    logging.info("🎯 Continuous Chartink Monitor Started!")
    logging.info("⚡ Mode: Continuous monitoring every 30 seconds")
    logging.info("🚨 Alerts: ONLY on actual stock changes")
    
    check_counter = 0
    
    while True:
        try:
            # Check for changes
            monitor.check_for_changes()
            check_counter += 1
            
            # Log status every 100 checks (for debugging)
            if check_counter % 100 == 0:
                if monitor.is_market_hours():
                    logging.info(f"✅ Completed {check_counter} checks. Last: {monitor.last_check_time.strftime('%H:%M:%S') if monitor.last_check_time else 'N/A'}")
                else:
                    logging.info(f"⏰ Outside market hours. Checks completed: {check_counter}")
            
            # Wait 30 seconds before next check
            time.sleep(30)
            
        except KeyboardInterrupt:
            logging.info("Monitor stopped by user")
            break
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            time.sleep(60)  # Wait 1 minute on error

if __name__ == "__main__":
    run_monitor()
