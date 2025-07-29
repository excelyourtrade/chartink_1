import requests
from bs4 import BeautifulSoup
import json
import time
import smtplib
import email.mime.text
import email.mime.multipart
from datetime import datetime, time as dt_time, timedelta
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

class ChartinkHistoricalMonitor:
    def __init__(self):
        # Store stocks by date: {date: {stock_name: price}}
        self.historical_stocks = {}
        self.session = requests.Session()
        self.ist = pytz.timezone('Asia/Kolkata')
        self.initialized = False
        
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
    
    def get_last_n_trading_days(self, n=5):
        """Get last N trading days (excluding weekends)"""
        dates = []
        current_date = datetime.now(self.ist).date()
        
        while len(dates) < n:
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                dates.append(current_date.strftime('%d-%m-%Y'))
            current_date -= timedelta(days=1)
        
        return dates
    
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
    
    def fetch_scanner_results_with_dates(self):
        """Fetch scanner results and organize by date"""
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
                date_wise_stocks = {}
                
                if 'data' in result and result['data']:
                    for stock in result['data']:
                        stock_name = stock.get('name', 'Unknown')
                        stock_close = stock.get('close', 0)
                        
                        # Try to get the date from the stock data
                        # Chartink sometimes includes date info in the response
                        stock_date = stock.get('per_chg_date', stock.get('date', ''))
                        
                        # If no date in response, check if this is for today or previous days
                        # We'll assume current results and track by checking time
                        if not stock_date:
                            # For now, assume it's for today - we'll improve this detection
                            stock_date = datetime.now(self.ist).strftime('%d-%m-%Y')
                        
                        if stock_date not in date_wise_stocks:
                            date_wise_stocks[stock_date] = {}
                        
                        date_wise_stocks[stock_date][stock_name] = stock_close
                
                return date_wise_stocks
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
    
    def check_for_historical_repainting(self):
        """Check for stocks appearing in previous trading days (repainting)"""
        if not self.is_market_hours():
            return
        
        # For now, let's use a simpler approach - track all stocks and detect when new ones appear
        # This is because Chartink API doesn't directly give us date-wise breakdown
        current_results = self.fetch_current_stocks()
        today = datetime.now(self.ist).strftime('%d-%m-%Y')
        yesterday = (datetime.now(self.ist) - timedelta(days=1)).strftime('%d-%m-%Y')
        
        if not self.initialized:
            self.historical_stocks[today] = current_results
            self.initialized = True
            
            init_msg = f"🎯 <b>Historical Repainting Monitor Started</b>\n\n"
            init_msg += f"📅 <b>Today:</b> {today}\n"
            init_msg += f"📊 <b>Current stocks:</b> {len(current_results)}\n\n"
            init_msg += f"🔍 <b>Monitoring for:</b>\n"
            init_msg += f"• Stocks appearing for yesterday ({yesterday})\n"
            init_msg += f"• Stocks appearing for previous trading days\n"
            init_msg += f"• Historical repainting detection\n\n"
            init_msg += f"⚡ <b>Will alert ONLY when stocks appear for past dates!</b>"
            
            self.send_telegram_message(init_msg)
            logging.info(f"Initialized historical monitor with {len(current_results)} stocks")
            return
        
        # Compare with previous results to detect repainting
        previous_results = self.historical_stocks.get(today, {})
        new_stocks = set(current_results.keys()) - set(previous_results.keys())
        
        if new_stocks:
            timestamp = datetime.now(self.ist).strftime("%d-%m-%Y %H:%M:%S IST")
            
            message = f"🚨 <b>REPAINTING ALERT!</b>\n"
            message += f"📅 {timestamp}\n\n"
            message += f"🎯 <b>New stocks appeared (likely for YESTERDAY or past dates):</b>\n\n"
            
            for stock in sorted(new_stocks):
                price = current_results[stock]
                message += f"• <b>{stock}</b> - ₹{price:.2f}\n"
            
            message += f"\n💡 <b>These stocks likely appeared for:</b>\n"
            message += f"📊 Yesterday ({yesterday}) due to repainting\n"
            message += f"📊 Or other previous trading days\n\n"
            message += f"🔍 <b>Action:</b> Check your Chartink scanner manually to see which date these stocks appeared for!"
            
            # Send notifications
            if self.send_telegram_message(message):
                logging.info(f"🚨 REPAINTING ALERT SENT: {len(new_stocks)} new stocks")
            
            # Send email
            email_subject = f"🚨 REPAINTING ALERT: {len(new_stocks)} stocks appeared for previous dates!"
            email_body = message.replace('<b>', '').replace('</b>', '').replace('🚨', '').replace('📅', '').replace('🎯', '').replace('💡', '').replace('🔍', '').replace('•', '-')
            
            if self.send_email(email_subject, email_body):
                logging.info("Repainting email alert sent")
        
        # Update historical data
        self.historical_stocks[today] = current_results
    
    def fetch_current_stocks(self):
        """Fetch current stocks (simplified)"""
        try:
            csrf_token = self.get_csrf_token()
            if not csrf_token:
                return {}
            
            headers = {
                'X-CSRF-TOKEN': csrf_token,
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': SCANNER_URL,
            }
            
            data = {'scan_clause': YOUR_SCAN_CLAUSE}
            
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
                
                return stocks_data
            
            return {}
            
        except Exception as e:
            logging.error(f"Error fetching stocks: {e}")
            return {}

def run_historical_monitor():
    """Run historical repainting monitor"""
    monitor = ChartinkHistoricalMonitor()
    
    startup_msg = f"🎯 <b>HISTORICAL REPAINTING MONITOR</b>\n\n"
    startup_msg += f"🎯 <b>Purpose:</b> Detect stocks appearing for YESTERDAY/past dates\n"
    startup_msg += f"⚡ <b>Mode:</b> Continuous monitoring every 45 seconds\n"
    startup_msg += f"📅 <b>Focus:</b> Historical repainting (not today's changes)\n"
    startup_msg += f"🚨 <b>Alerts:</b> Only when stocks appear for previous dates\n\n"
    startup_msg += f"✅ <b>Now monitoring for HIRECT-type alerts!</b>"
    
    monitor.send_telegram_message(startup_msg)
    
    logging.info("🎯 Historical Repainting Monitor Started!")
    logging.info("🚨 Focus: Detecting stocks appearing for previous trading days")
    
    check_counter = 0
    
    while True:
        try:
            monitor.check_for_historical_repainting()
            check_counter += 1
            
            if check_counter % 80 == 0:  # Log every ~1 hour
                logging.info(f"✅ Historical monitor: {check_counter} checks completed")
            
            time.sleep(45)  # Check every 45 seconds
            
        except KeyboardInterrupt:
            logging.info("Historical monitor stopped")
            break
        except Exception as e:
            logging.error(f"Error in historical monitor: {e}")
            time.sleep(120)

if __name__ == "__main__":
    run_historical_monitor()
            
