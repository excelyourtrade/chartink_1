import requests
from bs4 import BeautifulSoup
import json
import time
import smtplib
import email.mime.text
import email.mime.multipart
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

# Your ACTUAL scan clause
YOUR_SCAN_CLAUSE = """( {cash} ( ( {cash} ( quarterly gross sales > 1 quarter ago gross sales and quarterly foreign institutional investors percentage > 1 quarter ago foreign institutional investors percentage and net profit[yearly] > 0 and weekly cci( 34 ) > 100 and weekly high > 1.10 * latest close and 1 week ago high < 1.20 * yearly close and latest rsi( 14 ) >= 50 and market cap > 500 and latest ema( latest close , 50 ) > latest ema( latest close , 200 ) and latest ema( latest close , 10 ) > latest ema( latest close , 20 ) and latest ema( latest close , 20 ) > latest ema( latest close , 89 ) and latest ema( latest close , 89 ) > latest ema( latest close , 200 ) and latest close > 50 and latest close > latest ema( latest close , 10 ) ) ) ) )"""

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ChartinkMonitor:
    def __init__(self):
        self.previous_stocks = {}
        self.session = requests.Session()
        self.ist = pytz.timezone('Asia/Kolkata')
        self.scan_clause_sent = False  # Flag to send scan clause info once
        
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
            
            # Send scan clause info once for confirmation
            if not self.scan_clause_sent:
                clause_msg = f"✅ <b>Using YOUR Scan Clause:</b>\n"
                clause_msg += f"📊 <b>Criteria:</b> Cash stocks with:\n"
                clause_msg += f"• Growing quarterly sales & FII %\n"
                clause_msg += f"• Positive yearly net profit\n"
                clause_msg += f"• Weekly CCI > 100\n"
                clause_msg += f"• RSI ≥ 50\n"
                clause_msg += f"• EMA alignment (10>20>89>200)\n"
                clause_msg += f"• Market cap > 500 cr\n"
                clause_msg += f"• Price > 50 & above EMA(10)\n\n"
                clause_msg += f"🎯 <b>This will now show your ACTUAL scanner results!</b>"
                self.send_telegram_message(clause_msg)
                self.scan_clause_sent = True
            
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
                
                logging.info(f"Fetched {len(stocks_data)} stocks from YOUR scanner")
                return stocks_data
            else:
                logging.error(f"Scanner request failed: {response.status_code} - {response.text}")
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
        """Main monitoring function"""
        if not self.is_market_hours():
            logging.info("Outside market hours, skipping check")
            return
        
        current_stocks = self.fetch_scanner_results()
        
        if not self.previous_stocks:
            # First run during market hours
            self.previous_stocks = current_stocks
            
            # Send initialization message
            init_msg = f"🚀 <b>Scanner Initialized</b>\n"
            init_msg += f"📅 {datetime.now(self.ist).strftime('%d-%m-%Y %H:%M:%S IST')}\n"
            init_msg += f"📊 Found {len(current_stocks)} stocks currently in scanner\n\n"
            
            if current_stocks:
                init_msg += f"<b>Current Stocks:</b>\n"
                for i, (stock, price) in enumerate(sorted(current_stocks.items())[:10]):  # Show first 10
                    init_msg += f"• {stock}: ₹{price:.2f}\n"
                if len(current_stocks) > 10:
                    init_msg += f"... and {len(current_stocks) - 10} more stocks\n"
            else:
                init_msg += f"ℹ️ No stocks currently meet your scanner criteria\n"
                init_msg += f"📈 Will alert when stocks appear due to repainting!"
            
            self.send_telegram_message(init_msg)
            logging.info(f"Initialized with {len(current_stocks)} stocks")
            return
        
        # Find new and removed stocks (repainting detection)
        current_names = set(current_stocks.keys())
        previous_names = set(self.previous_stocks.keys())
        
        new_stocks = current_names - previous_names
        removed_stocks = previous_names - current_names
        
        if new_stocks or removed_stocks:
            timestamp = datetime.now(self.ist).strftime("%d-%m-%Y %H:%M:%S IST")
            
            message = f"🎯 <b>Scanner Repainting Detected!</b>\n"
            message += f"📅 {timestamp}\n\n"
            
            if new_stocks:
                message += f"✅ <b>New Stocks Appeared ({len(new_stocks)}):</b>\n"
                for stock in sorted(new_stocks):
                    price = current_stocks[stock]
                    message += f"• <b>{stock}</b>: ₹{price:.2f}\n"
                message += "\n"
            
            if removed_stocks:
                message += f"❌ <b>Stocks Removed ({len(removed_stocks)}):</b>\n"
                for stock in sorted(removed_stocks):
                    price = self.previous_stocks[stock]
                    message += f"• <b>{stock}</b>: ₹{price:.2f}\n"
            
            message += f"\n💡 <i>These changes are due to scanner repainting - historical data updates!</i>"
            
            # Send notifications
            if self.send_telegram_message(message):
                logging.info(f"Alert sent: {len(new_stocks)} new, {len(removed_stocks)} removed")
            
            # Send email
            email_subject = f"Chartink Repainting Alert: {len(new_stocks)} New, {len(removed_stocks)} Removed"
            email_body = message.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', '').replace('🎯', '').replace('📅', '').replace('✅', '').replace('❌', '').replace('💡', '').replace('•', '-')
            
            if self.send_email(email_subject, email_body):
                logging.info("Email alert sent successfully")
        else:
            # No changes - log quietly
            logging.info(f"No changes detected. Current stocks: {len(current_stocks)}")
        
        # Update previous stocks
        self.previous_stocks = current_stocks

def run_monitor():
    """Run the monitoring system"""
    monitor = ChartinkMonitor()
    
    # Check every 3 minutes during market hours
    schedule.every(3).minutes.do(monitor.check_for_changes)
    
    # Send startup message
    startup_msg = f"🚀 <b>Chartink Scanner Monitor Started!</b>\n\n"
    startup_msg += f"📊 <b>Your Scanner:</b> CP Swing Trade\n"
    startup_msg += f"⏰ <b>Monitoring:</b> Mon-Fri, 9:15 AM - 3:15 PM IST\n"
    startup_msg += f"🔄 <b>Check Interval:</b> Every 3 minutes\n"
    startup_msg += f"🎯 <b>Purpose:</b> Detect repainting stocks\n\n"
    startup_msg += f"✅ Now using YOUR actual scan criteria!"
    
    monitor.send_telegram_message(startup_msg)
    
    logging.info("🚀 Chartink Scanner Monitor Started!")
    logging.info("⏰ Monitoring: Monday-Friday, 9:15 AM - 3:15 PM IST")
    logging.info("🔄 Check Interval: Every 3 minutes")
    logging.info("📊 Using YOUR actual scan clause")
    
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
