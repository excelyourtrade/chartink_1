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

class AccurateYesterdayMonitor:
    def __init__(self):
        # Multiple baselines for better accuracy
        self.morning_baseline = set()     # 9:30 AM baseline
        self.afternoon_baseline = set()   # 2:00 PM baseline
        self.current_baseline = set()     # Current baseline
        
        self.session = requests.Session()
        self.ist = pytz.timezone('Asia/Kolkata')
        self.setup_complete = False
        self.check_count = 0
        self.all_detected_stocks = set()  # Track all stocks ever seen
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_current_yesterday_date(self):
        """Get yesterday's trading date"""
        yesterday = datetime.now(self.ist) - timedelta(days=1)
        while yesterday.weekday() >= 5:
            yesterday -= timedelta(days=1)
        return yesterday.strftime('%d-%m-%Y')
    
    def get_scanner_stocks(self):
        """Get stocks from scanner with retry mechanism"""
        for attempt in range(3):
            try:
                # Get CSRF token
                response = self.session.get(SCANNER_URL, timeout=15)
                soup = BeautifulSoup(response.content, 'html.parser')
                token = soup.find('meta', {'name': 'csrf-token'})
                if not token:
                    continue
                
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
                    
            except Exception as e:
                logging.error(f"Scanner attempt {attempt + 1} failed: {e}")
                time.sleep(5)
        
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
    
    def setup_baselines(self):
        """Setup multiple baselines for better accuracy"""
        current_stocks = self.get_scanner_stocks()
        current_names = set(current_stocks.keys())
        
        now = datetime.now(self.ist)
        
        # Set different baselines based on time
        if now.hour == 9 and now.minute >= 30:  # Morning baseline
            self.morning_baseline = current_names.copy()
        elif now.hour >= 14:  # Afternoon baseline
            self.afternoon_baseline = current_names.copy()
        
        self.current_baseline = current_names.copy()
        self.all_detected_stocks.update(current_names)
        self.setup_complete = True
        
        today = now.strftime('%d-%m-%Y')
        yesterday = self.get_current_yesterday_date()
        
        setup_msg = f"🔧 <b>ENHANCED SETUP COMPLETE</b>\n\n"
        setup_msg += f"📅 <b>Today:</b> {today}\n"
        setup_msg += f"🎯 <b>Monitoring for:</b> {yesterday}\n"
        setup_msg += f"📊 <b>Baseline stocks:</b> {len(current_names)}\n"
        setup_msg += f"⏰ <b>Setup time:</b> {now.strftime('%H:%M:%S')}\n\n"
        setup_msg += f"🔍 <b>Enhanced features:</b>\n"
        setup_msg += f"• Multiple baselines for accuracy\n"
        setup_msg += f"• 3-minute check intervals\n"
        setup_msg += f"• Retry mechanism for reliability\n"
        setup_msg += f"• Manual verification alerts\n\n"
        setup_msg += f"✅ <b>Will catch HEG-type stocks accurately!</b>"
        
        self.send_telegram(setup_msg)
        logging.info(f"Enhanced setup complete: {len(current_names)} stocks")
    
    def detect_yesterday_stocks(self):
        """Enhanced detection with multiple methods"""
        current_stocks = self.get_scanner_stocks()
        current_names = set(current_stocks.keys())
        
        if not current_stocks:
            logging.error("No stocks retrieved from scanner")
            return
        
        # Method 1: Compare with current baseline
        new_stocks_method1 = current_names - self.current_baseline
        
        # Method 2: Compare with all previously detected stocks
        truly_new_stocks = current_names - self.all_detected_stocks
        
        # Method 3: Time-based detection (stocks appearing at specific times)
        now = datetime.now(self.ist)
        time_based_new = set()
        
        if now.hour >= 10:  # After 10 AM, new stocks are likely for yesterday
            time_based_new = current_names - self.morning_baseline if self.morning_baseline else set()
        
        # Combine all methods
        all_new_stocks = new_stocks_method1.union(truly_new_stocks).union(time_based_new)
        
        if all_new_stocks:
            today = now.strftime('%d-%m-%Y')
            yesterday = self.get_current_yesterday_date()
            timestamp = now.strftime("%d-%m-%Y %H:%M:%S IST")
            
            # Send detailed alert
            alert_msg = f"🎯 <b>ENHANCED DETECTION ALERT!</b>\n\n"
            alert_msg += f"📅 <b>Today:</b> {today}\n"
            alert_msg += f"🎯 <b>Stocks appeared for:</b> {yesterday}\n"
            alert_msg += f"⏰ <b>Detected at:</b> {timestamp}\n\n"
            
            alert_msg += f"🟢 <b>NEW STOCKS DETECTED ({len(all_new_stocks)}):</b>\n\n"
            for stock in sorted(all_new_stocks):
                price = current_stocks.get(stock, 0)
                alert_msg += f"• <b>{stock}</b> - ₹{price:.2f}\n"
            
            alert_msg += f"\n🔬 <b>Detection Methods:</b>\n"
            alert_msg += f"• Method 1: {len(new_stocks_method1)} stocks\n"
            alert_msg += f"• Method 2: {len(truly_new_stocks)} truly new\n"
            alert_msg += f"• Method 3: {len(time_based_new)} time-based\n\n"
            
            alert_msg += f"💡 <b>These likely appeared for {yesterday} due to repainting!</b>\n"
            alert_msg += f"🔍 <b>Please verify manually if needed!</b>"
            
            # Send alerts
            self.send_telegram(alert_msg)
            self.send_email(f"🎯 Enhanced Alert: {len(all_new_stocks)} stocks for {yesterday}", alert_msg)
            
            logging.info(f"🎯 ENHANCED ALERT: {all_new_stocks} for {yesterday}")
        
        # Update baselines
        self.current_baseline = current_names.copy()
        self.all_detected_stocks.update(current_names)
        self.check_count += 1
        
        # Periodic status update
        if self.check_count % 40 == 0:  # Every 2 hours
            status_msg = f"📊 <b>Enhanced Monitor Status</b>\n\n"
            status_msg += f"🔍 <b>Checks completed:</b> {self.check_count}\n"
            status_msg += f"📈 <b>Current stocks:</b> {len(current_stocks)}\n"
            status_msg += f"📚 <b>Total stocks seen:</b> {len(self.all_detected_stocks)}\n"
            status_msg += f"⏰ <b>Time:</b> {now.strftime('%H:%M:%S')}\n\n"
            status_msg += f"✅ <b>Enhanced monitoring active!</b>"
            
            self.send_telegram(status_msg)

def main():
    monitor = AccurateYesterdayMonitor()
    
    today = datetime.now(monitor.ist).strftime('%d-%m-%Y')
    yesterday = monitor.get_current_yesterday_date()
    
    startup_msg = f"🚀 <b>ENHANCED YESTERDAY MONITOR</b>\n\n"
    startup_msg += f"📅 <b>Today:</b> {today}\n"
    startup_msg += f"🎯 <b>Target:</b> {yesterday}\n\n"
    startup_msg += f"🔧 <b>Enhancements:</b>\n"
    startup_msg += f"• 3-minute check intervals\n"
    startup_msg += f"• Multiple detection methods\n"
    startup_msg += f"• Time-based filtering\n"
    startup_msg += f"• Retry mechanisms\n\n"
    startup_msg += f"🎯 <b>Will catch HEG and all yesterday stocks!</b>"
    
    monitor.send_telegram(startup_msg)
    logging.info(f"🚀 Enhanced Monitor Started")
    
    # Setup baselines
    monitor.setup_baselines()
    
    while True:
        try:
            now = datetime.now(monitor.ist)
            if now.weekday() < 5 and 9 <= now.hour <= 16:
                monitor.detect_yesterday_stocks()
            
            time.sleep(180)  # Check every 3 minutes for better accuracy
            
        except KeyboardInterrupt:
            logging.info("Enhanced monitor stopped")
            break
        except Exception as e:
            logging.error(f"Error: {e}")
            time.sleep(300)

if __name__ == "__main__":
    main()
        
