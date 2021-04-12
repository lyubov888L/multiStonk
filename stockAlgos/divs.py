#this file contains functions specifically for the div algo
#what changes when a stock has a dividend?
#https://www.investopedia.com/articles/stocks/11/dividend-capture-strategy.asp

import otherfxns as o

algo = 'divs' #name of the algo

def init(configFile):
  global c
  #set the multi config file
  c = o.configparser.ConfigParser()
  c.read(configFile)
  
  #stocks held by this algo according to the records
  lock = o.threading.Lock()
  lock.acquire()
  posList = o.json.loads(open(c['file locations']['posList'],'r').read())[algo]
  lock.release()

def getList(verbose=True):
  
  #perform checks to see which one ones will gain
  #check history of the stocks. Look for pattern that denotes a gain after the initial div date (could possibly look like a buy low. Stock gains to div, div processes, dips, then gains again. Sell at that gain)
  
  #if today < ex div date, then buy

  if(verbose): print(f"getting unsorted list for {algo}")
  symbs = getUnsortedList()
  if(verbose): print(f"finding stocks for {algo}")
  symbs = [s+"|stocks" for s in symbs] #add the assetclass
  prices = o.getPrices(symbs,withVol=True) #get the current price and volume
  goodBuys = [s.split("|")[0] for s in prices if float(c[algo]['minPrice'])<=prices[s]['price']<=float(c[algo]['maxPrice']) and prices[s]['vol']>=float(c[algo]['minVol'])]
  if(verbose): print(f"{len(goodBuys)} found for {algo}")
  return goodBuys
  

#return whether symb is a good sell or not
#if div is collected and price > buyPrice+div, then sell
def goodSell(symb):
  lock = o.threading.Lock()
  lock.acquire()
  posList = o.json.loads(open(c['file locations']['posList'],'r').read())[algo]
  lock.release()
  
  dates = getDivDates(symb)
  if(symb not in posList):
    print(f"{symb} not found in {algo}")
    return True
  if(len(dates)>0): #make sure that the dates were populated
    curPrice = o.getInfo(symb)['price']
    if(curPrice/posList[symb]['buyPrice']<sellDn(symb)): #if change since buy has dropped below condition
      return True
    elif(str(o.dt.date.today())>dates['payment'] and
         curPrice/posList[symb]['buyPrice']>=sellUp(symb)): #if past the payment date and price has reached the sellUp point
      return True
    else:
      return False
  else:
    return False


#get a list of stocks to be sifted through
def getUnsortedList():
  while True:
    try:
      #get the stocks whose exdivdate is the next trade date (buy before it drops to the dropped price)
      r = o.json.loads(o.requests.get(f"https://api.nasdaq.com/api/calendar/dividends?date={o.nextTradeDate()}",headers={"user-agent":"-"}, timeout=5).text)['data']['calendar']['rows']
      break
    except Exception:
      print("Error in getting unsorted list for divs algo. Trying again...")
      o.time.sleep(3)
      pass
  
  r = [e['symbol'] for e in r]
  
  return r

#get the latest 4 div dates for a stock (announced, ex div, record, payment)
def getDivDates(symb,maxTries=3):
  tries = 0
  while tries<maxTries:
    try:
      #
      r = o.json.loads(o.requests.get(f"https://api.nasdaq.com/api/quote/{symb}/dividends?assetclass=stocks&limit=1",headers={"user-agent":"-"}, timeout=5).text)['data']['dividends']['rows'][0]
      break
    except Exception:
      print(f"Error in getting div dates for {symb}. Trying again...")
      tries+=1
      o.time.sleep(3)
      pass
  if(tries<maxTries):
    r = {}
    #TODO: see if there can be some kind of error handling within strptim to catch, or use regex or something to ensure strings are in the right format
    try:
      r['announcement'] = str(o.dt.datetime.strptime(r['declarationDate'],"%m/%d/%Y").date())
    except Exception:
      r['announcement'] = ''
    try:
      r['ex'] = str(o.dt.datetime.strptime(r['exOrEffDate'],"%m/%d/%Y").date())
    except Exception:
      r['ex'] = ''
    try:
      r['record'] = str(o.dt.datetime.strptime(r['recordDate'],"%m/%d/%Y").date())
    except Exception:
      r['record'] = ''
    try:
      r['payment'] = str(o.dt.datetime.strptime(r['paymentDate'],"%m/%d/%Y").date())
    except Exception:
      r['payment'] = ''
    '''
    r = {
          'announcement':str(o.dt.datetime.strptime(r['declarationDate'] if r['declarationDate'],"%m/%d/%Y").date()),
          'ex':str(o.dt.datetime.strptime(r['exOrEffDate'],"%m/%d/%Y").date()),
          'record':str(o.dt.datetime.strptime(r['recordDate'],"%m/%d/%Y").date()),
          'payment':str(o.dt.datetime.strptime(r['paymentDate'],"%m/%d/%Y").date())
        }
    '''
  else:
    print(f"Failed to get div dates for {symb}")
    r = {}
  return r



#TODO: this should also account for squeezing
def sellUp(symb=""):
  lock = o.threading.Lock()
  lock.acquire()
  posList = o.json.loads(open(c['file locations']['posList'],'r').read())[algo]
  lock.release()
  
  mainSellUp = float(c[algo]['sellUp'])
  if(symb in posList):
    #TODO: add exit condition (see it in getList)
    sellUp = mainSellUp #TODO: account for squeeze here
  else:
    sellUp = mainSellUp
  return sellUp

#TODO: this should also account for squeezing
def sellDn(symb=""):
  lock = o.threading.Lock()
  lock.acquire()
  posList = o.json.loads(open(c['file locations']['posList'],'r').read())[algo]
  lock.release()
  
  mainSellDn = float(c[algo]['sellDn'])
  if(symb in posList):
    sellDn = mainSellDn #TODO: account for squeeze here
  else:
    sellDn = mainSellDn
  return sellDn

def sellUpDn():
  
  return float(c[algo]['sellUpDn'])