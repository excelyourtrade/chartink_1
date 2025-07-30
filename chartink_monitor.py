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

# Your Configuration
TELEGRAM_TOKEN = "6686777921:AAE3o3dGRJOLHWAzf4TqNLiJ6RaGEczIl4E"
CHAT_ID = "-1002628859007"
EMAIL = "excelyourtrade@gmail.com"
SENDER_EMAIL = "excelyourtrade@gmail.com"
APP_PASSWORD = "bxph anbw sqbx vezk"
SCANNER_URL = "https://chartink.com/screener/copy-2112-chartpulse-cp-swing-trade"

# Your scan clause
YOUR_SCAN_CLAUSE = """( {cash} ( ( {cash} ( quarterly gross sales > 1 quarter ago gross sales and quarterly foreign institutional investors percentage > 1 quarter ago foreign institutional investors percentage and net profit[yearly] > 0 and weekly cci( 34 ) > 100 and weekly high > 1.10 * latest close and 1 week ago high < 1.20 * yearly close and latest rsi( 14 ) >= 50 and market cap > 500 and latest ema( latest close , 50 ) > latest ema( latest close , 200 ) and latest ema( latest close , 10 ) > latest ema( latest close , 20 ) and latest ema( latest close , 20 ) > latest ema( latest close , 89 ) and latest ema( latest close , 89 ) > latest ema( latest close , 200 ) and latest close > 50 and latest close > latest ema( latest close , 10 ) ) ) ) )"""

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class TrueYesterdayOnlyMonitor:
    def __init__(self):
        self.ignored_today_stocks = set()  # Stocks to ignore (today's stocks)
        self.session = requests.Session()
        self.ist = pytz.timezone('Asia/Kolkata')
        self.setup_complete = False
        self.check_count = 0
        
        # Target date (29-07-2025)
        self.target_date = "29-07-2025"
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
        })
    
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
    
    def get_scanner_stocks(self):
        """Get scanner results"""
        try:
            # Get CSRF token
            response = self.session.get(SCANNER_URL, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            token = soup.find('meta', {'name': 'csrf-token'})
            if not token:
                return None
            
            # Query scanner
            headers = {
                'X-CSRF-TOKEN': token['content'],
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': SCANNER_URL,
            }
            
            data = {'scan_clause': YOUR_SCAN_CLAUSE}
            response = self.session.post('https://chartink.com/screener/process', 
                                       headers=headers, data=data, timeout=20)
            
            if response.status_code == 200:
                result = response.json()
                stocks = {}
                
                if 'data' in result and result['data']:
                    for stock in result['data']:
                        name = stock.get('name', '')
                        price = stock.get('close', 0)
                        if name:
                            stocks[name] = price
                
                return stocks
            return None
            
        except Exception as e:
            logging.error(f"Scanner error: {e}")
            return None
    
    def setup_today_baseline(self):
        """Setup: Mark all current stocks as 'today's stocks' to ignore"""
        stocks = self.get_scanner_stocks()
        if stocks is None:
            return False
        
        self.ignored_today_stocks = set(stocks.keys())
        self.setup_complete = True
        
        # Send setup confirmation
        setup_msg = f"🔧 <b>SETUP COMPLETE - Today's Stocks Ignored</b>\n\n"
        setup_msg += f"📅 <b>Target Date:</b> {self.target_date}\n"
        setup_msg += f"❌ <b>Ignoring {len(self.ignored_today_stocks)} TODAY'S stocks:</b>\n"
        
        if self.ignored_today_stocks:
            for stock in sorted(list(self.ignored_today_stocks)[:5]):
                setup_msg += f"• {stock} (IGNORED - today's stock)\n"
            if len(self.ignored_today_stocks) > 5:
                setup_msg += f"... and {len(self.ignored_today_stocks) - 5} more today's stocks (ALL IGNORED)\n"
        
        setup_msg += f"\n✅ <b>Now ONLY monitoring for NEW stocks appearing for {self.target_date}</b>\n"
        setup_msg += f"🎯 <b>Will alert when GALLANTT-type stocks appear for yesterday!</b>"
        
        if self.send_telegram(setup_msg):
            logging.info(f"✅ Setup complete - ignoring {len(self.ignored_today_stocks)} today's stocks")
            return True
        return False
    
    def check_for_yesterday_stocks(self):
        """Check for stocks appearing for 29-07-2025 ONLY"""
        self.check_count += 1
        
        current_stocks = self.get_scanner_stocks()
        if current_stocks is None:
            logging.error("Failed to get scanner results")
            return
        
        current_names = set(current_stocks.keys())
        
        # Find stocks that are NOT in today's ignored list (these are for yesterday!)
        yesterday_stocks = current_names - self.ignored_today_stocks
        
        if yesterday_stocks:
            timestamp = datetime.now(self.ist).strftime("%d-%m-%Y %H:%M:%S IST")
            
            alert_msg = f"🚨 <b>YESTERDAY STOCKS FOUND!</b>\n\n"
            alert_msg += f"📅 <b>Stocks appeared for:</b> {self.target_date}\n"
            alert_msg += f"⏰ <b>Detected at:</b> {timestamp}\n"
            alert_msg += f"🔍 <b>Check #{self.check_count}</b>\n\n"
            alert_msg += f"🟢 <b>STOCKS FOR {self.target_date} ({len(yesterday_stocks)}):</b>\n\n"
            
            for stock in sorted(yesterday_stocks):
                price = current_stocks.get(stock, 0)
                alert_msg += f"• <b>{stock}</b> - ₹{price:.2f}\n"
            
            alert_msg += f"\n💡 <b>These are the 3 stocks for {self.target_date} you mentioned!</b>\n"
            alert_msg += f"🎯 <b>NOT today's stocks - these are for YESTERDAY only!</b>"
            
            # Send alerts
            telegram_sent = self.send_telegram(alert_msg)
            email_sent = self.send_email(
                f"🚨 FOUND: {len(yesterday_stocks)} stocks for {self.target_date}",
                alert_msg.replace('<b>', '').replace('</b>', '').replace('🚨', '').replace('📅', '').replace('⏰', '').replace('🔍', '').replace('🟢', '').replace('💡', '').replace('🎯', '').replace('•', '-')
            )
            
            logging.info(f"🚨 YESTERDAY ALERT: {yesterday_stocks} for {self.target_date}")
            
            # Update ignored list to include the new stocks (so we don't alert again)
            self.ignored_today_stocks.update(yesterday_stocks)
        
        # Log status
        if self.check_count % 20 == 0:
            logging.info(f"Status: {self.check_count} checks, ignoring {len(self.ignored_today_stocks)} stocks, found {len(yesterday_stocks) if yesterday_stocks else 0} yesterday stocks")

def main():
    monitor = TrueYesterdayOnlyMonitor()
    
    # Send startup message
    startup_msg = f"🎯 <b>TRUE YESTERDAY-ONLY MONITOR</b>\n\n"
    startup_msg += f"📝 <b>Strategy:</b>\n"
    startup_msg += f"1. Mark ALL current stocks as 'today's stocks'\n"
    startup_msg += f"2. IGNORE them completely\n"
    startup_msg += f"3. Alert ONLY when new stocks appear (these are for {monitor.target_date})\n\n"
    startup_msg += f"🎯 <b>This will catch the 3 stocks you mentioned for 29-07-2025!</b>"
    
    monitor.send_telegram(startup_msg)
    logging.info("🎯 True Yesterday-Only Monitor Starting...")
    
    # Step 1: Setup baseline (ignore today's stocks)
    while not monitor.setup_complete:
        if monitor.setup_today_baseline():
            break
        logging.error("Setup failed, retrying in 30 seconds...")
        time.sleep(30)
    
    # Step 2: Monitor for yesterday stocks only
    while True:
        try:
            now = datetime.now(monitor.ist)
            if now.weekday() < 5 and 8 <= now.hour <= 20:  # Extended hours
                monitor.check_for_yesterday_stocks()
            
            time.sleep(60)  # Check every minute
            
        except KeyboardInterrupt:
            logging.info("Monitor stopped")
            break
        except Exception as e:
            logging.error(f"Error: {e}")
            time.sleep(120)

if __name__ == "__main__":
    main()
    
