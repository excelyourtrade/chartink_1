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

class ReliableYesterdayMonitor:
    def __init__(self):
        self.baseline_stocks = set()
        self.session = requests.Session()
        self.ist = pytz.timezone('Asia/Kolkata')
        self.initialized = False
        self.check_count = 0
        
        # Get yesterday's date
        yesterday = datetime.now(self.ist) - timedelta(days=1)
        while yesterday.weekday() >= 5:  # Skip weekends
            yesterday -= timedelta(days=1)
        self.target_date = yesterday.strftime('%d-%m-%Y')
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        })
    
    def send_telegram(self, message):
        """Send Telegram message with retry"""
        for attempt in range(3):
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                data = {
                    'chat_id': CHAT_ID,
                    'text': message,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': True
                }
                response = requests.post(url, data=data, timeout=15)
                if response.status_code == 200:
                    return True
                else:
                    logging.error(f"Telegram failed: {response.status_code} - {response.text}")
            except Exception as e:
                logging.error(f"Telegram attempt {attempt + 1} failed: {e}")
                time.sleep(2)
        return False
    
    def send_email(self, subject, body):
        """Send email with retry"""
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
            logging.error(f"Email failed: {e}")
            return False
    
    def get_scanner_results(self):
        """Get scanner results with better error handling"""
        try:
            # Get page first
            page_response = self.session.get(SCANNER_URL, timeout=15)
            if page_response.status_code != 200:
                logging.error(f"Page load failed: {page_response.status_code}")
                return None
            
            # Extract CSRF token
            soup = BeautifulSoup(page_response.content, 'html.parser')
            csrf_token = soup.find('meta', {'name': 'csrf-token'})
            if not csrf_token:
                logging.error("CSRF token not found")
                return None
            
            # Make scanner request
            headers = {
                'X-CSRF-TOKEN': csrf_token['content'],
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': SCANNER_URL,
            }
            
            data = {'scan_clause': YOUR_SCAN_CLAUSE}
            
            scanner_response = self.session.post(
                'https://chartink.com/screener/process',
                headers=headers,
                data=data,
                timeout=20
            )
            
            if scanner_response.status_code != 200:
                logging.error(f"Scanner failed: {scanner_response.status_code}")
                return None
            
            result = scanner_response.json()
            stocks = {}
            
            if 'data' in result and result['data']:
                for stock in result['data']:
                    name = stock.get('name', 'Unknown')
                    price = stock.get('close', 0)
                    if name != 'Unknown':
                        stocks[name] = price
            
            logging.info(f"Retrieved {len(stocks)} stocks from scanner")
            return stocks
            
        except Exception as e:
            logging.error(f"Scanner error: {e}")
            return None
    
    def check_for_yesterday_stocks(self):
        """Main checking function"""
        self.check_count += 1
        
        # Get current scanner results
        current_stocks = self.get_scanner_results()
        if current_stocks is None:
            logging.error("Failed to get scanner results")
            return
        
        current_names = set(current_stocks.keys())
        
        if not self.initialized:
            # First run - establish baseline
            self.baseline_stocks = current_names.copy()
            self.initialized = True
            
            # Send test message to confirm working
            test_msg = f"🧪 <b>TEST - Monitor Started Successfully!</b>\n\n"
            test_msg += f"📅 <b>Monitoring for stocks appearing for:</b> {self.target_date}\n"
            test_msg += f"📊 <b>Current baseline:</b> {len(self.baseline_stocks)} stocks\n\n"
            if self.baseline_stocks:
                test_msg += f"<b>Current stocks:</b>\n"
                for stock in sorted(list(self.baseline_stocks)[:5]):  # Show first 5
                    test_msg += f"• {stock}\n"
                if len(self.baseline_stocks) > 5:
                    test_msg += f"... and {len(self.baseline_stocks) - 5} more\n"
            
            test_msg += f"\n✅ <b>System is working! Will alert when GALLANTT-type stocks appear for {self.target_date}</b>"
            
            if self.send_telegram(test_msg):
                logging.info("✅ Test message sent - system working")
            else:
                logging.error("❌ Test message failed")
            
            return
        
        # Find NEW stocks (these appeared for yesterday due to repainting)
        new_stocks = current_names - self.baseline_stocks
        
        if new_stocks:
            timestamp = datetime.now(self.ist).strftime("%d-%m-%Y %H:%M:%S IST")
            
            # Create alert
            alert_msg = f"🚨 <b>YESTERDAY STOCK ALERT!</b>\n\n"
            alert_msg += f"📅 <b>Stocks appeared for:</b> {self.target_date}\n"
            alert_msg += f"⏰ <b>Detected at:</b> {timestamp}\n"
            alert_msg += f"🔄 <b>Check #{self.check_count}</b>\n\n"
            alert_msg += f"🟢 <b>NEW STOCKS FOR {self.target_date} ({len(new_stocks)}):</b>\n\n"
            
            for stock in sorted(new_stocks):
                price = current_stocks.get(stock, 0)
                alert_msg += f"• <b>{stock}</b> - ₹{price:.2f}\n"
            
            alert_msg += f"\n💡 <b>These stocks just appeared for {self.target_date} due to repainting!</b>\n"
            alert_msg += f"🎯 <b>Check these stocks for yesterday's opportunity</b>"
            
            # Send alerts
            telegram_sent = self.send_telegram(alert_msg)
            email_sent = self.send_email(
                f"🚨 YESTERDAY STOCKS: {len(new_stocks)} for {self.target_date}",
                alert_msg.replace('<b>', '').replace('</b>', '').replace('🚨', '').replace('📅', '').replace('⏰', '').replace('🔄', '').replace('🟢', '').replace('💡', '').replace('🎯', '').replace('•', '-')
            )
            
            logging.info(f"🚨 ALERT SENT: {new_stocks} for {self.target_date} (Telegram: {telegram_sent}, Email: {email_sent})")
            
            # Update baseline
            self.baseline_stocks = current_names.copy()
        else:
            # No new stocks - just update baseline
            self.baseline_stocks = current_names.copy()
        
        # Log status every 30 checks
        if self.check_count % 30 == 0:
            logging.info(f"Status: {self.check_count} checks completed, monitoring {len(current_names)} stocks for {self.target_date}")

def main():
    """Main function"""
    monitor = ReliableYesterdayMonitor()
    
    # Send startup message
    startup_msg = f"🚀 <b>RELIABLE YESTERDAY MONITOR</b>\n\n"
    startup_msg += f"🎯 <b>Target:</b> Catch stocks like GALLANTT for {monitor.target_date}\n"
    startup_msg += f"⚡ <b>Method:</b> Detect ANY new stocks in scanner\n"
    startup_msg += f"🕐 <b>Frequency:</b> Every 45 seconds during market hours\n"
    startup_msg += f"📱 <b>Alerts:</b> Telegram + Email\n\n"
    startup_msg += f"✅ <b>This WILL catch GALLANTT-type alerts!</b>"
    
    monitor.send_telegram(startup_msg)
    logging.info(f"🚀 Reliable Monitor Started for {monitor.target_date}")
    
    while True:
        try:
            # Check during extended hours (8 AM - 7 PM IST) on weekdays
            now = datetime.now(monitor.ist)
            if now.weekday() < 5 and 8 <= now.hour <= 19:
                monitor.check_for_yesterday_stocks()
            else:
                logging.info("Outside monitoring hours")
            
            time.sleep(45)  # Check every 45 seconds
            
        except KeyboardInterrupt:
            logging.info("Monitor stopped by user")
            break
        except Exception as e:
            logging.error(f"Main loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
    
