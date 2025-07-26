
import pandas as pd
pd.set_option('display.max_columns', None)
import requests
from datetime import datetime
from datetime import timedelta  
import json
import time
import telegram
import schedule

start_time = time.time()
fromdate = datetime.strftime(datetime.today(),'%d-%m-%Y')
todate =  datetime.today() - timedelta(days=7)  
enddate = datetime.strftime(todate,'%d-%m-%Y')
head = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36', "Upgrade-Insecure-Requests": "1","DNT": "1","Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language": "en-US,en;q=0.9","Accept-Encoding": "gzip, deflate, br"}
URL1 = "https://www.nseindia.com/companies-listing/corporate-filings-insider-trading"
d1 = requests.get(URL1,headers=head)

URL = 'https://www.nseindia.com/api/corporates-pit?index=equities&from_date='+ enddate+ '&to_date=' + fromdate
print(URL)
d = requests.get(URL,headers=head,cookies =d1.cookies ).json()
df = pd.DataFrame(d['data'])
df["secVal"].replace({"-": 0}, inplace=True)
df["secVal"] = pd.to_numeric(df["secVal"])
df["secAcq"] = pd.to_numeric(df["secAcq"])

personCat = ['Promoters','Promoter Group']
df = df[df['acqMode'] == 'Market Purchase']
df = df[df['personCategory'].isin(personCat) ]
df['acqfromDt'] = pd.to_datetime(df['acqfromDt'], format='%d-%b-%Y',errors='ignore')

df1 = df.groupby(['symbol']).agg({'secVal':'sum','secAcq':'sum','acqfromDt':'max'}).reset_index()
df1['BuyValue'] = round(df1['secVal']/df1['secAcq'],2)
df1 = df1[df1['secVal']  > 10000]
df1.sort_values(by = 'acqfromDt',ascending = False)
print(df1)

#def run_script():
Alertbot = 'https://api.telegram.org/bot5762212585:AAFoWYM3qdGDRfPkDyDhOMU3CiwHa4biIuo'
chatid = '-855310893'
AlertText = "Symbol\t\tDate\n"
for index, row in df1.iterrows():
    AlertText += f"{row['symbol']}\t\t{row['acqfromDt'].strftime('%d-%m-%Y')}\n"
parameters = {"chat_id" : chatid, "text" : AlertText}
res = requests.get(Alertbot + "/sendMessage", data=parameters)
print(f'[Response] - {res}')


# Schedule the function to run at 7 PM every day
#schedule.every().day.at("19:00").do(run_script)

# Run the scheduler loop
#while True:
    #schedule.run_pending()
    #time.sleep(1)

