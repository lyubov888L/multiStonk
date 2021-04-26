#this file contains functions specifically for the earnings
#what happens to a stock after various earnings calls?

# https://tradingreviews.net/why-stock-prices-fall-after-good-earnings-announcements
# https://www.marketwatch.com/story/heres-how-to-trade-a-stock-after-an-earnings-surprise-2016-08-18
# https://finance.zacks.com/impact-earnings-announcements-stock-prices-4265.html
# https://www.investopedia.com/terms/e/earningssurprise.asp


import otherfxns as o

algo = o.os.path.basename(__file__).split('.')[0] #name of the algo based on the file name

def init(configFile):
  global posList,c
  #set the multi config file
  c = o.configparser.ConfigParser()
  c.read(configFile)
  
  #stocks held by this algo according to the records
  lock = o.threading.Lock()
  lock.acquire()
  posList = o.json.loads(open(c['file locations']['posList'],'r').read())[algo]
  lock.release()


#TODO: alt idea: look for earnings happening next week, of those look for ones with the min num of analysts, of those look for prices that have been increasing, of those look for ones in our price range and volume range

'''
1. Stock price action in the most recent weeks.
If stock moved steadily higher for month leading to announcement, particularly for last week, expectations might be escalating. Conversely, if stock moved lower leading to the announcement, expectations might be low and stock might move higher even if the company merely matches analyst estimates.

2. Whisper numbers vs. analyst estimates.
If whisper numbers are significantly higher than analyst estimates, expectations are high. There is a challenge here to check out whisper numbers from a reliable source (there is wide range of reliability from various sources).

3. Recent post-earnings price changes compared to earnings results (is there a pattern for that company)?
Some companies display remarkably consistent patterns of meeting or beating estimates, and subsequent stock price changes. For example, JPM beat estimates handily for four consecutive quarters but the stock fell half the time after they reported results, and CRM crushed estimates every time and the stock rose every time (by an average of 6.6%). Some of these patterns can be counted on to persist.
Another pattern has been companies whose stock price didn't fluctuate very much regardless of whether they met, fell short of, or exceeded estimates. These companies seem perfectly suited for calendar spread strategies or buy-write strategies (benefiting from the escalated implied volatility of the weekly options).

4. Current RSI levels.
If a company in "very overbought" condition leading up to announcement, it might be an indication of extremely high expectations, although overbought readings have not been as reliable as oversold conditions that demonstrate that expectations are unusually low.

5. Overwhelming positive (or negative) comments on various blog posts.

I always check out recent articles on the company published by Seeking Alpha and especially the comments at the end of the articles, as well as blog posts on other financial forums. For the most part, I consider this commentary as contrary indicators. The people who seem to be the most impassioned about loving or hating a company also seem to be wrong most of the time.

In addition, I check out recent hedge fund activity (are hedge funds buying or selling the stock?) to get a better handle on whether the stock is likely to rise or fall after the announcement. While hedge funds are not always right, they can be counted on to have conducted some serious due-diligence work before making a decision to commit or divest, and they have far more resources at their disposals than any individual could hope to have. It seems to be a good idea to piggy-back on their work, and to join them in their assessment of the company.

I have found that actual hedge fund cash commitments is a much better indicator of future stock performance than anything the analysts say. For example, for the last four quarters, analysts who publish estimates for SalesForce.com (NYSE:CRM) have been off by an average of ten times earnings per share for the past four quarters (e.g., they estimated an average of $.03 and actual earnings were over $.30). It is hard to give the analysts any credence when they can consistently be this far off base.

One shortcoming of the model is that it doesn't always provide predictive value. In one article I reviewed the expectation levels for eight reporting companies and concluded that none of them displayed unusually high or low expectation levels so that my model could not help in predicting the post-earnings stock price move -- Predicting The Direction Of Next Week's Earnings-Reporting Companies
'''



def getList(verbose=True):
  #perform checks to see which one ones will gain
  maxPrice = float(c[algo]['maxPrice']) #max price point
  minPrice = float(c[algo]['minPrice']) #min price point
  minEsts = int(c[algo]['minEsts']) #min number of analyst estimates
  
  

#https://seekingalpha.com/article/1445911-a-remarkably-reliable-way-to-predict-post-earnings-price-moves
  
  return goodBuys #return dict of {symb:note}
  

#get a list of stocks to be sifted through
def getUnsortedList(maxTries=3):
  tries=0
  while tries<maxTries:
    try:
      date = o.nextTradeDate() if tries>1 else str(o.dt.date.today()) #try getting the data at least twice, then if it still doesn't work, then try looking at the next trade date (this should take care of earnings not being announced on the weekends or holidays)
      r = o.json.loads(o.requests.get(f"https://api.nasdaq.com/api/calendar/earnings?date={date}",headers={"user-agent":"-"}, timeout=5))['data']['rows']
      break
    except Exception:
      print(f"Error in getting unsorted list for {algo} algo. Trying again...")
      o.time.sleep(3)
      tries+=1
      pass
  return {'date':date,'inf':r}

#TODO: this should also account for squeezing
def sellUp(symb=""):
  mainSellUp = float(o.c[algo]['sellUp'])
  if(symb in stockList):
    sellUp = mainSellUp #TODO: account for squeeze here
  else:
    sellUp = mainSellUp
  return sellUp

#TODO: this should also account for squeezing
def sellDn(symb=""):
  mainSellDn = float(o.c[algo]['sellDn'])
  if(symb in stockList):
    sellDn = mainSellDn #TODO: account for squeeze here
  else:
    sellDn = mainSellDn
  return sellDn

def sellUpDn():
  return float(o.c[algo]['sellUpDn'])