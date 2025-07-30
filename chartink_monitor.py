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

class SimpleYesterdayMonitor:
    def __init__(self):
        self.known_stocks = set()  # Stocks we've already seen
        self.session = requests.Session()
        self.ist = pytz.timezone('Asia/Kolkata')
        self.first_run = True
        
        # Calculate yesterday's date (skip weekends)
        yesterday = datetime.now(self.ist) - timedelta(days=1)
        while yesterday.weekday() >= 5:
            yesterday -= timedelta(days=1)
        self.yesterday_date = yesterday.strftime('%d-%m-%Y')
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_scanner_stocks(self):
        """Get current stocks from scanner"""
        try:
            # Get CSRF token
            response = self.session.get(SCANNER_URL)
            soup = BeautifulSoup(response.content, 'html.parser')
            token = soup.find('meta', {'name': 'csrf-token'})
            if not token:
                return {}
            
            # Post to scanner
            headers = {
                'X-CSRF-TOKEN': token['content'],
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': SCANNER_URL,
            }
            
            data = {'scan_clause': YOUR_SCAN_CLAUSE}
            response = self.session.post('https://chartink.com/screener/process', 
                                       headers=headers, data=data)
            
            if response.status_code == 200:
                result = response.json()
                stocks = {}
                
                if 'data' in result and result['data']:
                    for stock in result['data']:
                        name = stock.get('name', 'Unknown')
                        price = stock.get('close', 0)
                        stocks[name] = price
                
                return stocks
            
            return {}
            
        except Exception as e:
            logging.error(f"Error getting stocks: {e}")
            return {}
    
    def send_alert(self, new_stocks):
        """Send alert for yesterday's stocks only"""
        timestamp = datetime.now(self.ist).strftime("%d-%m-%Y %H:%M:%S IST")
        
        # Telegram message
        message = f"🎯 <b>YESTERDAY STOCK ALERT!</b>\n\n"
        message += f"📅 <b>Stocks appeared for:</b> {self.yesterday_date}\n"
        message += f"⏰ <b>Detected at:</b> {timestamp}\n\n"
        message += f"📈 <b>NEW YESTERDAY STOCKS ({len(new_stocks)}):</b>\n\n"
        
        for stock, price in sorted(new_stocks.items()):
            message += f"• <b>{stock}</b> - ₹{price:.2f}\n"
        
        message += f"\n💡 <b>These stocks appeared for {self.yesterday_date} due to repainting!</b>"
        
        # Send Telegram
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {
                'chat_id': CHAT_ID,
                'text': message,
                'parse_mode': 'HTML'
            }
            requests.post(url, data=data, timeout=10)
            logging.info(f"✅ YESTERDAY ALERT SENT: {len(new_stocks)} stocks")
        except Exception as e:
            logging.error(f"Telegram error: {e}")
        
        # Send Email
        try:
            email_msg = email.mime.multipart.MIMEMultipart()
            email_msg["From"] = SENDER_EMAIL
            email_msg["To"] = EMAIL
            email_msg["Subject"] = f"🎯 YESTERDAY STOCKS: {len(new_stocks)} for {self.yesterday_date}"
            
            email_body = message.replace('<b>', '').replace('</b>', '').replace('🎯', '').replace('📅', '').replace('⏰', '').replace('📈', '').replace('💡', '').replace('•', '-')
            email_msg.attach(email.mime.text.MIMEText(email_body, "plain"))
            
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(email_msg)
            server.quit()
            logging.info("✅ Yesterday email sent")
        except Exception as e:
            logging.error(f"Email error: {e}")
    
    def monitor(self):
        """Main monitoring function"""
        current_stocks = self.get_scanner_stocks()
        
        if self.first_run:
            # First run - just store current stocks silently
            self.known_stocks = set(current_stocks.keys())
            self.first_run = False
            
            # Send startup message
            startup_msg = f"🎯 <b>YESTERDAY-ONLY Monitor Started</b>\n\n"
            startup_msg += f"📅 <b>Watching for stocks appearing for:</b> {self.yesterday_date}\n"
            startup_msg += f"📊 <b>Current baseline:</b> {len(self.known_stocks)} stocks\n"
            startup_msg += f"🚨 <b>Will alert ONLY for YESTERDAY stocks</b>\n"
            startup_msg += f"❌ <b>Will IGNORE today's stocks</b>"
            
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                data = {'chat_id': CHAT_ID, 'text': startup_msg, 'parse_mode': 'HTML'}
                requests.post(url, data=data, timeout=10)
            except:
                pass
            
            logging.info(f"Started monitoring for {self.yesterday_date} - baseline: {len(self.known_stocks)} stocks")
            return
        
        # Find NEW stocks (these are likely for yesterday)
        current_stock_names = set(current_stocks.keys())
        new_stock_names = current_stock_names - self.known_stocks
        
        if new_stock_names:
            # Get prices for new stocks
            new_stocks = {name: current_stocks[name] for name in new_stock_names}
            
            # Send alert for yesterday's stocks
            self.send_alert(new_stocks)
            
            # Update known stocks
            self.known_stocks = current_stock_names
        
        # Update known stocks even if no new ones (for next comparison)
        self.known_stocks = current_stock_names

def main():
    """Run the monitor"""
    monitor = SimpleYesterdayMonitor()
    
    logging.info("🎯 Simple Yesterday Monitor Started")
    logging.info(f"📅 Monitoring for stocks appearing for: {monitor.yesterday_date}")
    
    check_count = 0
    
    while True:
        try:
            # Only check during extended hours (9 AM - 6 PM IST) on weekdays
            now = datetime.now(monitor.ist)
            if now.weekday() < 5 and 9 <= now.hour <= 18:
                monitor.monitor()
                check_count += 1
                
                if check_count % 60 == 0:  # Log every hour
                    logging.info(f"Completed {check_count} checks for {monitor.yesterday_date}")
            
            time.sleep(60)  # Check every minute
            
        except KeyboardInterrupt:
            logging.info("Monitor stopped")
            break
        except Exception as e:
            logging.error(f"Error: {e}")
            time.sleep(120)

if __name__ == "__main__":
    main()
        
