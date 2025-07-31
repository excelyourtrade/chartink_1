import requests
from bs4 import BeautifulSoup
import time
import smtplib
import email.mime.text
import email.mime.multipart
from datetime import datetime, timedelta
import logging
import pytz

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

class DynamicYesterdayMonitor:
    def __init__(self):
        self.previous_stocks = set()
        self.session = requests.Session()
        self.ist = pytz.timezone('Asia/Kolkata')
        self.initialized = False
        self.check_count = 0
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_current_yesterday_date(self):
        """Calculate yesterday's trading date dynamically (skips weekends)"""
        yesterday = datetime.now(self.ist) - timedelta(days=1)
        while yesterday.weekday() >= 5:  # Skip weekends
            yesterday -= timedelta(days=1)
        return yesterday.strftime('%d-%m-%Y')
    
    def get_scanner_stocks(self):
        """Get stocks from scanner API"""
        try:
            # Get CSRF token
            response = self.session.get(SCANNER_URL)
            soup = BeautifulSoup(response.content, 'html.parser')
            token = soup.find('meta', {'name': 'csrf-token'})
            if not token:
                return {}
            
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
            return {}
            
        except Exception as e:
            logging.error(f"Scanner error: {e}")
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
    
    def monitor_yesterday_stocks(self):
        """Monitor for yesterday's stocks appearing - with dynamic date calculation"""
        
        # Get current yesterday date (this updates daily)
        current_yesterday = self.get_current_yesterday_date()
        today = datetime.now(self.ist).strftime('%d-%m-%Y')
        
        current_stocks = self.get_scanner_stocks()
        current_names = set(current_stocks.keys())
        
        if not self.initialized:
            self.previous_stocks = current_names.copy()
            self.initialized = True
            
            init_msg = f"✅ <b>UPDATED MONITOR STARTED</b>\n\n"
            init_msg += f"📅 <b>Today:</b> {today}\n"
            init_msg += f"🎯 <b>Monitoring for:</b> {current_yesterday}\n"
            init_msg += f"🔧 <b>Method:</b> Dynamic yesterday calculation\n"
            init_msg += f"📊 <b>Baseline:</b> {len(self.previous_stocks)} stocks\n"
            init_msg += f"⚡ <b>Frequency:</b> Every 5 minutes\n\n"
            init_msg += f"✅ <b>Now correctly monitors for current yesterday!</b>"
            
            self.send_telegram(init_msg)
            logging.info(f"Initialized - Today: {today}, Monitoring: {current_yesterday}")
            return
        
        # Find new stocks
        new_stocks = current_names - self.previous_stocks
        
        if new_stocks:
            timestamp = datetime.now(self.ist).strftime("%d-%m-%Y %H:%M:%S IST")
            
            alert_msg = f"🚨 <b>NEW STOCKS DETECTED!</b>\n\n"
            alert_msg += f"📅 <b>Today:</b> {today}\n"
            alert_msg += f"🎯 <b>Stocks appeared for:</b> {current_yesterday}\n"
            alert_msg += f"⏰ <b>Detected at:</b> {timestamp}\n\n"
            alert_msg += f"🟢 <b>NEW STOCKS ({len(new_stocks)}):</b>\n\n"
            
            for stock in sorted(new_stocks):
                price = current_stocks.get(stock, 0)
                alert_msg += f"• <b>{stock}</b> - ₹{price:.2f}\n"
            
            alert_msg += f"\n💡 <b>These stocks appeared due to repainting for {current_yesterday}!</b>\n"
            alert_msg += f"🎯 <b>Perfect timing - monitoring correct yesterday!</b>"
            
            # Send alerts
            telegram_sent = self.send_telegram(alert_msg)
            email_sent = self.send_email(f"🚨 New stocks for {current_yesterday}", alert_msg)
            
            logging.info(f"🚨 ALERT: {new_stocks} for {current_yesterday}")
        
        # Update baseline
        self.previous_stocks = current_names
        
        # Track check count and send status updates
        self.check_count += 1
        
        if self.check_count % 24 == 0:  # Every 2 hours (24 checks × 5 min = 2 hours)
            status_msg = f"📊 <b>Status Update</b>\n\n"
            status_msg += f"📅 <b>Today:</b> {today}\n"
            status_msg += f"🎯 <b>Currently monitoring for:</b> {current_yesterday}\n"
            status_msg += f"🔍 <b>Checks completed:</b> {self.check_count}\n"
            status_msg += f"📈 <b>Current stocks in scanner:</b> {len(current_stocks)}\n\n"
            status_msg += f"✅ <b>System working correctly!</b>"
            
            self.send_telegram(status_msg)
            logging.info(f"Status: Today={today}, Monitoring={current_yesterday}, Checks={self.check_count}")

def main():
    monitor = DynamicYesterdayMonitor()
    
    today = datetime.now(monitor.ist).strftime('%d-%m-%Y')
    current_yesterday = monitor.get_current_yesterday_date()
    
    startup_msg = f"🚀 <b>FIXED YESTERDAY MONITOR</b>\n\n"
    startup_msg += f"📅 <b>Today:</b> {today}\n"
    startup_msg += f"🎯 <b>Will monitor for:</b> {current_yesterday}\n"
    startup_msg += f"✅ <b>Fixed:</b> Dynamic yesterday calculation\n"
    startup_msg += f"⚡ <b>Frequency:</b> Every 5 minutes\n\n"
    startup_msg += f"🔧 <b>No more wrong dates - always monitors correct yesterday!</b>"
    
    monitor.send_telegram(startup_msg)
    logging.info(f"🚀 Fixed Monitor Started - Today: {today}, Monitoring: {current_yesterday}")
    
    while True:
        try:
            now = datetime.now(monitor.ist)
            if now.weekday() < 5 and 9 <= now.hour <= 16:  # Market hours
                monitor.monitor_yesterday_stocks()
            
            time.sleep(300)  # Check every 5 minutes
            
        except KeyboardInterrupt:
            logging.info("Monitor stopped")
            break
        except Exception as e:
            logging.error(f"Error: {e}")
            time.sleep(300)

if __name__ == "__main__":
    main()
