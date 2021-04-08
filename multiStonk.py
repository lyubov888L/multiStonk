#Steven Williams (2021)
#Stock trading program to use multiple algorithms/strategies as defined in the config file and present in the algos directory to perform low frequency shortterm trades
# https://www.investopedia.com/ask/answers/042115/whats-best-investing-strategy-have-during-recession.asp



print("\nStarting up...")

import otherfxns as o
import alpacafxns as a
import random, time, json, sys, os
from glob import glob
from operator import eq
import datetime as dt
from colorama import init as colorinit

colorinit() #allow coloring in Windows terminals



#parse args and get the config file
configFile="./configs/multi.config"
if(len(sys.argv)>1): #if there's an argument present
  for arg in sys.argv[1:]:
    if(arg.lower()=='-h'): #if there's an argument regarding the config file
      print(("\nStockbot\n"
            "Uses multiple algorithms to trade stocks based on the functions specified in the config file and present in the algos directory.\n"
            "\nSyntax:\n"
            "[ -h | path/to/file.config ]\n"
            "-h\t: displays this help menu\n"
            "path\t: point to the config file containing all settings required to run the program (defaults to "+configFile+")\n"
            ))
      exit()
    elif(os.path.isfile(arg) and arg.lower().endswith(".config")): #check that the arg is a valid file and ends with .config
      configFile = arg
    #if we want to pass more arguments, we can specify them here (also make sure to include them in the help menu)
    else:
      raise ValueError("Invalid argument. Make sure config file is present or use '-h' for help.")


#set the multi config file
c = o.configparser.ConfigParser()
c.read(configFile)

print(f"Config file {configFile}")
print(f"Key file {c['file locations']['keyFile']}\n")

#init the alpaca functions
a.init(c['file locations']['keyFile'],int(c['account params']['isPaper']))

#add the algos dir
sys.path.append(c['file locations']['algosDir'])

#list of algorithms to be used and their corresponding stock lists to be bought (init with none)
algoList = c['allAlgos']['algoList'].replace(" ","").split(',') #var comes in as a string, remove spaces, and turn into comma separated list
algoList = {e:[] for e in algoList}

#import all algos that are in algoList (they require an up-to-date posList, so must be imported after it's updated)
for algo in algoList:
  exec(f"import {algo}")


#change display text color
class bcolor:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


#init some gobal vars
listsUpdatedToday = False #tell everyone whether the list has been updated yet today or not
closeTime = o.closeTime(estOffset=-1) #get the time in datetime format of when the market closes (reference this when looking at time till close)


#TODO: in algos, also change from getPrice to getPrices to go faster for goodBuy/goodSell to goodBuy/goodSells (make fewer api calls)
#TODO: need to utilize the note field for storing important info (like pmt date for div, and init jump date for dj, then reference that field instead of pulling from api every minute)
#TODO: display needs to happen faster (might be goodSell appears to be too slow. That'll have to change per algo I think)
#TODO: make check2buy its own thread?
#TODO: add sentiment analysis to newsScrape
def main(verbose=True):
  global algoList, posList, listsUpdatedToday, closeTime
  portHist = a.getProfileHistory(str(dt.date.today()),'1M')['equity'] #get the closing prices of the portfolio over the last month
  maxPortVal=max([e for e in portHist if e is not None]) #get the max portfolio value over the last month and remove blank entries
  cashMargin = float(c['account params']['cashMargin']) #extra cash to hold above hold value
  if(cashMargin<1): #cashMargin MUST BE GREATER THAN 1 in order for it to work correctly
    raise ValueError("Error: withdrawable funds margin is less than 1. Multiplier must be >=1")
  cash2hold = float(c['account params']['cash2hold'])
  acct = a.getAcct() #initialize the acct var
  
  
  #make sure we're still above the threshold to trade
  while float(acct['portfolio_value'])>=maxPortVal*float(c['account params']['portStopLoss']):
    
    acct = a.getAcct() #get account info
    pos = a.getPos() #get all held positions (no algo assigned)
    
    totalCash = float(acct['cash'])
    if(totalCash>=cash2hold*cashMargin): #if we have more buying power than the min plus some leeway, then reduce it to hold onto that buy pow
      # print(f"Can safely withdrawl ${round(cash2hold,2)}")
      totalCash = totalCash-cash2hold*cashMargin #subtract the cash2hold plus the margin
    elif(totalCash>cash2hold and totalCash<cash2hold*cashMargin):
      totalCash = 0 #stop trading if we've started to eat into the margin, that way we don't overshoot
      
    if(o.marketIsOpen()):
      print(f"\nPortfolio Value: ${acct['portfolio_value']}, total cash: ${totalCash}, {len(posList)} algos")
      #update the lists if not updated yet and that it's not currently updating
      if(not listsUpdatedToday and len([t.getName() for t in o.threading.enumerate() if t.getName().startswith('update')])==0):
        updateListsThread = o.threading.Thread(target=updateLists) #init the thread - note locking is required here
        updateListsThread.setName('updateLists') #set the name to the stock symb
        updateListsThread.start() #start the thread

      print("algo\tshares\tsymb \tcng frm buy\tcng frm cls\tnotes")
      print("----\t------\t-----\t-----------\t-----------\t-----")
      #look to sell things
      for algo in algoList:
        check2sell(algo,pos) #only look at the ones currently held
      
      if((closeTime-dt.datetime.now()).total_seconds()<=60*float(c['time params']['buyTime']) and sum([t.getName().startswith('update') for t in o.threading.enumerate()])==0):
        #TODO: move cash adjustment from here to above
        tradableCash = totalCash if totalCash<float(c['account params']['cash2hold']) else max(totalCash-float(c['account params']['cash2hold'])*float(c['account params']['cashMargin']),0) #account for withholding a certain amount of cash+margin
        cashPerAlgo = tradableCash/len(algoList) #evenly split available cash across all algos
        #start buying things
        for algo in algoList:
          buyThread = o.threading.Thread(target=check2buy, args=(algo,cashPerAlgo, algoList[algo])) #init the thread - note locking is required here
          buyThread.setName(algo) #set the name to the stock symb
          buyThread.start() #start the thread
    
      time.sleep(60)
    
    else: #market is closed
      #display the total p/l % of each algo
      print("Algo ROI's:")
      for algo in posList:
        curPrices = o.getPrices([e+"|stocks" for e in posList[algo]]) #get the current prices of all the stocks in a given algo
        
        algoCurVal = sum([posList[algo][s]['sharesHeld']*curPrices[s+"|stocks".upper()]['price'] for s in posList[algo] if s+"|stocks".upper() in curPrices]) #get the total value of the stocks in a given algo
        algoBuyVal = sum([posList[algo][s]['sharesHeld']*posList[algo][s]['buyPrice'] for s in posList[algo]]) #get the total amount initially invested in a given algo
        roi = round(algoCurVal/algoBuyVal,2)
        print(f"{algo} - {bcolor.FAIL if roi<1 else bcolor.OKGREEN}{roi}{bcolor.ENDC}") #display the ROI
      
      #update the max port val
      portHist = a.getProfileHistory(str(dt.date.today()),'1M')['equity']
      maxPortVal=max([e for e in portHist if e is not None])
      print(f"\nMax portfolio value from last month: ${maxPortVal}")
      print(f"Current portfolio value: ${portHist[-1]}\n")

      syncPosList() #sync up posList to live data

      if(o.dt.date.today().weekday()==4 and o.dt.datetime.now().time()>o.dt.time(12)): #if it's friday afternoon
        #delete all csv files in stockDataDir
        print("Removing saved csv files")
        for f in glob(o.c['file locations']['stockDataDir']+"*.csv"):
          try: #placed inside a try statement in the event that the file is removed before being removed here
            o.os.unlink(f)
          except Exception:
            pass
        
      
      # clear all lists in algoList
      print("Clearing buyList")
      algoList = {e:[] for e in algoList}
      
      tto = a.timeTillOpen()
      print(f"Market opens in {round(tto/3600,2)} hours")
      #wait some time before the market opens      
      if(tto>60*float(c['time params']['updateLists'])):
        print(f"Updating stock lists in {round((tto-60*float(c['time params']['updateLists']))/3600,2)} hours")
        time.sleep(tto-60*float(c['time params']['updateLists']))
      #update stock lists
      print("Updating buyList")
      updateListsThread = o.threading.Thread(target=updateLists) #init the thread - note locking is required here
      updateListsThread.setName('updateLists') #set the name to the stock symb
      updateListsThread.start() #start the thread

      closeTime = o.closeTime(estOffset=-1) #get the next closing time
      time.sleep(a.timeTillOpen())
      
  print(f"Portfolio value of ${acct['portfolio_value']} is less than {c['account params']['portStopLoss']} times the max portfolio value of ${maxPortVal}. Selling all. Program will need to be reinitiated manually.")
  a.sellAll(isManual=not int(c['account params']['autoSellOff'])) #if the portfolio value falls below our stop loss, automatically sell everything

#update all lists to be bought (this should be run as it's own thread)
def updateLists(verbose=False):
  global algoList, listsUpdatedToday
  
  #TODO: check that the buyfile is present and if it was updated today: if it was, then read directly from it, else generate lists
  errored = False
  if(verbose): print("Checking if buyList file is present")
  if(o.os.path.isfile(c['file locations']['buyList'])):
    if(verbose): print("File is present. Checking mod date")
    try:
      modDate = dt.datetime.strptime(time.strftime("%Y-%m-%d",time.localtime(os.stat(c['file locations']['buyList']).st_mtime)),"%Y-%m-%d").date() #if ANYONE knows of a better way to get the modified date into a date format, for the love of god please let me know
    except Exception:
      modDate = dt.date.today()-dt.timedelta(1)
    if(modDate==dt.date.today()):
      try:
        if(verbose): print("Reading from file")
        algoList = json.loads(open(c['file locations']['buyList'],'r').read())
      except Exception:
        if(verbose): print("invalid data in file")
        errored = True
    else:
      if(verbose): print(f"mod date not today - {modDate}")
      errored = True
  else:
    if(verbose): print("file does not exist")
    errored = True
  
  if(errored):
  
    lock = o.threading.Lock()
    revSplits = o.reverseSplitters()
    for e in algoList: #start a thread to update the list for each algorithm
      print(f"updating {e} list")
      updateThread = o.threading.Thread(target=updateList, args=(e,lock,revSplits)) #init the thread - note locking is required here
      updateThread.setName("update-"+e) #set the name to the stock symb
      updateThread.start() #start the thread
        
    #TODO: see the following because the updateList threads currently all access algoList, and the while loop is probably not the best solution
    # https://www.geeksforgeeks.org/multio.threading-in-python-set-2-synchronization/
    while(len([t.getName() for t in o.threading.enumerate() if t.getName().startswith("update-")])>0):
      time.sleep(2)
    
    #save to a file
    if(verbose): print("Writing to buyList file")
    with open(c['file locations']['buyList'],'w') as f:
      f.write(json.dumps(algoList,indent=2))
  
  listsUpdatedToday = True

#update the to-buy list of the given algorithm, and exclude a list of rm stocks
def updateList(algo,lock,rm=[],verbose=False):
  global algoList
  if(verbose): print(f"Updating {algo} list")
  algoBuys = eval(algo+".getList()") #this is probably not safe, but best way I can think of
  algoBuys = [e for e in algoBuys if e not in rm] #remove any stocks that are in the rm list
  lock.acquire() #lock in order to write to the list
  algoList[algo] = algoBuys
  lock.release() #then unlock


#check to sell positions from a given algo (where algo is an aglo name, and pos is the output of a.getPos())
def check2sell(algo, pos):
  for e in pos:
    if(e['symbol'] in posList[algo] and posList[algo][e['symbol']]['sharesHeld']>0):
      #TODO: possibly getPrice with mktCap (and use in display), then if the number of shares held>mktCap/price, then sell the surplus
      print(f"{algo}\t{int(posList[algo][e['symbol']]['sharesHeld'])}\t{e['symbol']}\t{bcolor.FAIL if round(float(e['unrealized_plpc'])+1,2)<1 else bcolor.OKGREEN}{round(float(e['unrealized_plpc'])+1,2)}{bcolor.ENDC}\t\t{bcolor.FAIL if round(float(e['unrealized_intraday_plpc'])+1,2)<1 else bcolor.OKGREEN}{round(float(e['unrealized_intraday_plpc'])+1,2)}{bcolor.ENDC}\t\t{posList[algo][e['symbol']]['note']}")

      if(posList[algo][e['symbol']]['shouldSell']): #if marked to sell, get rid of it immediately
        print(f"{e['symbol']} marked for immediate sale.")
        sell(e['symbol'],algo) #record and everything in the sell function
        
      else:
        #TODO: incorporate goodSells (also need to add goodSells function to each algo (this should speed things up and reduce api calls))
        goodSell = eval(f"{algo}.goodSell('{e['symbol']}')") #TODO: need to add shouldSell checking on held positions
        if(goodSell):
          if(f"{algo}-{e['symbol']}" not in [t.getName() for t in o.threading.enumerate()]): #make sure that the thread isn't already running
            #TODO: look at locking if need be
            triggerThread = o.threading.Thread(target=triggeredUp, args=(e['symbol'],algo)) #init the thread - note locking is required here
            triggerThread.setName(f"{algo}-{e['symbol']}") #set the name to the algo and stock symb
            triggerThread.start() #start the thread


#look to buy stocks from the stocks2buy list with the available funds for the algo
def check2buy(algo, cashAvailable, stocks2buy):
  global posList

  random.shuffle(stocks2buy) #shuffle the stocks2buy to avoid front loading
  #calculate the cash to be put towards various stocks in the algo (shouldn't be more than the cash available, but shouldn't be less than than the minDolPerStock (unless mindol > cashAvail))
  cashPerStock = min(cashAvailable,max(float(c['account params']['minDolPerStock']),cashAvailable/len(stocks2buy)))
  
  #TODO: Also other printing should happen rather than printing the actual response
  #TODO: also, this should probably loop forever/until a certain condition is met, and also needs to check that a stock isn't already trying to sell, and that this thread isn't already running

  #loop through the stocks to be bought
  for stock in stocks2buy:
    
    #populate the information about the stock (either from the posList if it's present, else with default info)
    stockInfo = posList[algo][stock] if stock in posList[algo] else {
          "sharesHeld":0,
          "lastTradeDate":"NA",
          "lastTradeType":"NA",
          "buyPrice":0,
          "shouldSell":False,
          "note":""
        }
    
    #get the last date it was traded, if it isn't populated, just set it to yesterday
    try:
      lastTradeDate = dt.datetime.strptime(stockInfo[algo][stock]['lastTradeDate'],"%Y-%m-%d").date()
    except Exception:
      lastTradeDate = dt.date.today()-dt.timedelta(1)
    
    #to avoid day trading, make sure that it either didn't trade yet today, or if it has, that it hasn't sold yet
    if lastTradeDate < dt.date.today() or stockInfo['lastTradeType']!="sell":
      
      [curPrice,mktCap] = o.getPrice(stock,withCap=True) #get the appx price to buy at, and the marketcap (to calculate the most shares we'll be allowed to purchase - some % of outstanding shares (which = mktcap/curprice)
      shares = int(min(cashPerStock/curPrice,(mktCap/curPrice)*float(c['account params']['maxVolPerc']))) #set number of shares to be at most some % of the mktcap, otherwise as many int shares as cash is available
      if(shares>0): #cannot place an order for 0 shares
        isBought = buy(shares,stock,algo,curPrice)
        if(isBought): print(f"Bought {shares} shares of {stock} for {algo} algo at around ${curPrice}/share")
    
#a stock has reached a trigger point and should begin to be checked more often (it will be sold in this function)
def triggeredUp(stock, algo):
  maxPrice = 0.01 #init vars to be slightly above 0
  curPrice = 0.01
  sellUpDn = float(eval(algo+".sellUpDn()"))
  #ensure that current price>0 (getPrice returns 0 if it can't recognize a symbol (eg if a merger happens or a stock is delisted)
  while(curPrice>0 and curPrice>=sellUpDn*maxPrice and (closeTime-dt.datetime.now()).total_seconds()>60):
    curPrice = o.getPrice(stock)
    maxPrice = max(maxPrice,curPrice)
    print(f"{algo}\t{stock}\t{round(curPrice/maxPrice,2)} : {round(sellUpDn,2)}")
    time.sleep(3) #slow it down a little bit
  isSold = sell(stock, algo)
  if(isSold): print(f"Sold all shares of {stock} for {algo} algo")

#basically just a market order for the stock and then record it into an order info file
def sell(stock, algo):
  global posList
  if(posList[algo][stock]['sharesHeld']>0):
    r = a.createOrder("sell",float(posList[algo][stock]['sharesHeld']),stock)
  else:
    print(f"No shares held of {stock}")
    return False
  if(r['status'] == "accepted"): #check that it actually sold
    lock = o.threading.Lock()
    lock.acquire()
    posList[algo][stock] = { #update the entry in posList
        "sharesHeld":0,
        "lastTradeDate":str(dt.date.today()),
        "lastTradeType":"sell",
        "buyPrice":0,
        "shouldSell":False,
        "note":""
      }
    open(c['file locations']['posList'],'w').write(json.dumps(posList,indent=2)) #update the posList file
    lock.release()
    return True
  else:
    print(f"Order to sell {posList[algo][stock]['sharesHeld']} shares of {stock} not accepted")
    return False

#basically just a market buy of this many shares of this stock for this algo
def buy(shares, stock, algo, buyPrice):
  r = a.createOrder("buy",shares,stock) #this needs to happen first so that it can be as accurate as possible
  global posList

  if(r['status'] == "accepted"): #check to make sure that it actually bought
    lock = o.threading.Lock()
    lock.acquire()
    posList[algo][stock] = { #update the entry in posList
        "sharesHeld":float(posList[algo][stock]['sharesHeld'])+float(r['qty']) if stock in posList[algo] else float(r['qty']),
        "lastTradeDate":str(dt.date.today()),
        "lastTradeType":"buy",
        #running avg = (prevAvg*n+newVals)/(n+m)
        "buyPrice":(posList[algo][stock]['buyPrice']*posList[algo][stock]['sharesHeld']+buyPrice)/(posList[algo][stock]['sharesHeld']+float(r['qty'])) if stock in posList[algo] else buyPrice,
        "shouldSell":False,
        "note":""
      }
    open(c['file locations']['posList'],'w').write(json.dumps(posList,indent=2)) #update posList file
    lock.release()
    return True
  else: #it didn't actually buy
    print(f"Order to buy {shares} shares of {stock} not accepted")
    return False


#set up the position list and do some error checking to make sure it's correct (take list of algos as arg in the event the pos list needs to be populated)
def setPosList(algoList, verbose=True):
  posList={}
  #if the posList file doesn't exist
  if(not os.path.isfile(c['file locations']['posList'])):
    if(verbose): print("File is missing. Creating and adding blank lists...")
    lock = o.threading.Lock()
    lock.acquire()
    with open(c['file locations']['posList'],'w') as f:
      f.write(json.dumps({e:{} for e in algoList}))
    posList = json.loads(open(c['file locations']['posList'],'r').read())
    lock.release()
  else: #if it does exist
    try: #try reading any json data from it
      lock = o.threading.Lock()
      lock.acquire()
      with open(c['file locations']['posList'],'r') as f:
        posList = json.loads(f.read())
      missingAlgos = [algo for algo in algoList if algo not in posList]
      if(verbose and len(missingAlgos)>0): print(f"Adding {len(missingAlgos)} algo{'s' if len(missingAlgos)>1 else ''} to posList")
      for algo in missingAlgos:
        posList[algo] = {}
      lock.release()  
        
      #write the missing algos to the file
      lock = o.threading.Lock()
      lock.acquire()
      with open(c['file locations']['posList'],'w') as f:
        f.write(json.dumps(posList))
      lock.release()
      
    except Exception: #if it fails, then just write the empty algoList to the file
      #TODO: this is dangerous! This could potentially overwrite all saved position data if there's any error above. Make this more robust
      if(verbose): print("Something went wrong. Overwriting file")
      lock = o.threading.Lock()
      lock.acquire()
      with open(c['file locations']['posList'],'w') as f:
        f.write(json.dumps({e:{} for e in algoList}))
      posList = json.loads(open(c['file locations']['posList'],'r').read())
      lock.release()
      
  return posList



#sync what we have recorded and what's actually going on in the account
def syncPosList(verbose=False):
  global posList
  lock = o.threading.Lock() #locking is needed to write to the file and edit the posList var (will have to see how threads and globals work with each other)
  print("Syncing posList...")
  
  #check if an algo in the posList is removed from the algoList
  for inactiveAlgo in [algo for algo in posList if algo not in algoList]:
    #stocks that are in a removed algo should be moved to an active algo that has it, if none do, then move it to the active algo with the highest loss
    for symb in posList[inactiveAlgo]: #stocks in the removed algo
      #get all active algos that contain it
      activeAlgosWithStock = [e for e in posList if(e in algoList and symb in e)]
      maxAlgo = ['x',0] #algo and the max gain of the stock
      #get the algo with the max gain for this stock
      if(len(activeAlgosWithStock)>0): #if there's at least 1 active algo that contains it
        for activeAlgo in activeAlgosWithStock: #look thru each algo that could hold the stock
          sellUp = eval(f"{activeAlgo}.sellUp('{symb}')") #find the sell up of that algo
          maxAlgo = [activeAlgo,sellUp] if sellUp>maxAlgo[1] else maxAlgo #get the greater of the two algos
      else: #if there are not active algos that contain it
        for activeAlgo in algoList: #then loop through all active algos
          sellUp = eval(f"{activeAlgo}.sellUp('{symb}')") #find the sell up of that algo
          maxAlgo = [activeAlgo,sellUp] if sellUp>maxAlgo[1] else maxAlgo #get the greater of the two algos

      if(verbose): print(f"{inactiveAlgo} algo is inactive. Moving {symb} from {inactiveAlgo} to {maxAlgo[0]}")
      
      lock.acquire()
      try: #this should evaluate if the symb is already present in the active algo
        posList[maxAlgo[0]][symb]['sharesHeld'] += posList[inactiveAlgo][symb]['sharesHeld'] #only transfer over the shares active algo data is more important
      except Exception: #this should evaluate if the symb is not already present in the active algo
        posList[maxAlgo[0]][symb] = { #transfer over all data from the inactive one
                                  'sharesHeld':posList[inactiveAlgo][symb]['sharesHeld'],
                                  'lastTradeDate':posList[inactiveAlgo][symb]['lastTradeDate'],
                                  'lastTradeType':posList[inactiveAlgo][symb]['lastTradeType'],
                                  'buyPrice':posList[inactiveAlgo][symb]['buyPrice'],
                                  'shouldSell':posList[inactiveAlgo][symb]['shouldSell'],
                                  'note':posList[inactiveAlgo][symb]['note']
                                }
        
      posList[inactiveAlgo][symb]['sharesHeld'] = 0 #remove the shares fromt he inactive algo
      lock.release()
        
  
  
  if(verbose): print("getting actually held positions")
  p = a.getPos()
  heldPos = {e['symbol']:float(e['qty']) for e in p} #actually held positions
  heldBuyPrices = {e['symbol']:float(e['avg_entry_price']) for e in p} #TODO: combine this into heldPos and either rework recPos or change some conditionals to account for the addition <-- this might be done already, double check


  if(verbose): print("Adding any missing fields to current records")
  for algo in posList:
    for symb in posList[algo]:
      lock.acquire()      
      if('sharesHeld' not in posList[algo][symb]):
        if(verbose): print(f"{algo} {symb} missing sharesHeld")
        posList[algo][symb]['sharesHeld'] = 0
      if('lastTradeDate' not in posList[algo][symb]):
        if(verbose): print(f"{algo} {symb} missing lastTradeDate")
        posList[algo][symb]['lastTradeDate'] = "NA"
      if('lastTradeType' not in posList[algo][symb]):
        if(verbose): print(f"{algo} {symb} missing lastTradeType")
        posList[algo][symb]['lastTradeType'] = "NA"
      if('buyPrice' not in posList[algo][symb]):
        if(verbose): print(f"{algo} {symb} missing buyPrice")
        posList[algo][symb]['buyPrice'] = heldBuyPrices[symb] if symb in heldBuyPrices else 0
      if('shouldSell' not in posList[algo][symb]):
        if(verbose): print(f"{algo} {symb} missing shouldSell")
        posList[algo][symb]['shouldSell'] = False
      if('note' not in posList[algo][symb]):
        if(verbose): print(f"{algo} {symb} missing note")
        posList[algo][symb]['note'] = ""
      lock.release()
  
  #total stocks in posList
  if(verbose): print("getting recorded positions...")
  recPos = {} #recorded positions
  for algo in posList: #for every algo in the posList
    if(len(posList)>0):
      for stock in posList[algo]: #for every stock in that algo
        if stock not in recPos: #if that stock isn't already in the recorded positions
          recPos[stock] = float(posList[algo][stock]['sharesHeld']) #add it
        else:
          recPos[stock] += float(posList[algo][stock]['sharesHeld']) #add the shares held
  
  
  if(not eq(recPos,heldPos)):
    if(verbose): print("discrepency found between records and actuals")
    #if there are any stocks recorded that aren't in the heldPos, remove them
    #if there are an excess of shares in the recPos than the heldPos, look for any in the algos that match the disparity, and remove them from that algo
      #if none match (i.e. heldPos and recPos both have a stock, but there's an unknown amount extra in recPos), then just sell it all
  
    #if there are any stocks in heldPos that aren't recorded, then compare to algoList
      #if it's in algolist, assign to all algos that have it, else assign to algo with the smallest gain to offload it asap
    #if there are an excess of shares in the heldPos than the recPos, then add the excess to the algo with the highest gain to increase gains as much as possible
    
    #compare recPos to heldPos
    
    #if there are any stocks recorded that aren't in the heldPos, remove them
    for symb in [s for s in recPos if s not in heldPos]: #for all stocks in recorded and not in heldPos
      for algo in posList: #check every algo
        if(verbose): print(f"{symb} not found in actuals. Removing from {algo} records")
        lock.acquire()
        posList[algo].pop(symb,None) #remove from posList
        lock.release()
      recPos.pop(symb,None) #remove from recorded
    
    #for each stock, if there are an excess of shares in the recPos than the heldPos, look for any in the algos that match the disparity, and remove them from that algo
      #if none match (i.e. heldPos and recPos both have a stock, but there's an unknown amount extra in recPos), then trim off the amount extra from the algo that has the most above the disparity
        #if no algo has any above it: then sell the whole lot TODO: this should probably be handled differently, but it's some complexity that can be saved for later
    for symb in [s for s in recPos if recPos[s]>heldPos[s]]: #for all stocks where the recorded is greater than the held
      for algo in posList: #for every algo
        #remove any that may be exact matches
        if float(posList[algo][symb]['sharesHeld'])==recPos[symb]-heldPos[symb]:
          if(verbose): print(f"Removing {float(posList[algo][symb]['sharesHeld'])} shares of {symb} from {algo} records")
          recPos[symb] -= float(posList[algo][symb]['sharesHeld'])
          if(recPos[symb]==0):
            recPos.pop(symb,None)
          lock.acquire()
          posList[algo].pop(symb,None)
          lock.release()
          
          
      #if there's still a discrepency (ie. there is not an exact difference)
      if(recPos[symb]>heldPos[symb]): #if the recorded still has more than the held
        #get algos with the symbol and the number of shares of that symbol
        if(verbose): print(f"more shares of {symb} in records than actuals")
        algosWithStock = {e:float(posList[e][symb]['sharesHeld']) for e in posList if symb in posList[e]} #get the number of shares per algo if the algo has the stock
        for algo in algosWithStock:
          #TODO: this should probably be changed to spread out over multiple algos rather than just 1
          if(algosWithStock[algo]>=recPos[symb]-heldPos[symb]): #if an algo has more than the disparity
            if(verbose): print(f"{algo} has {algosWithStock[algo]} shares of {symb}. Removing {recPos[symb]-heldPos[symb]} shares")
            lock.acquire()
            posList[algo][symb]['sharesHeld'] -= recPos[symb]-heldPos[symb] #remove the disparity
            lock.release()
            recPos[symb] -= recPos[symb]-heldPos[symb]
            break

        if(recPos[symb]>heldPos[symb]): #if the disparity wasn't caught, then just sell the lot
          print(f"Could not find a suitable sync for {symb}. Selling the lot.")
          for algo in [algo for algo in posList if symb in posList[algo]]:
            sell(symb, algo)



    #compare heldPos to recPos

    #ensure algoList is up to date
  if(not eq(recPos, heldPos)): #compare again after the initial comparison
    #if the lists aren't currently updating and haven't already updated today, then update
    if(not listsUpdatedToday and len([t for t in o.threading.enumerate() if t.getName().startswith('update')])==0):
      updateListsThread = o.threading.Thread(target=updateLists) #init the thread - note locking is required here
      updateListsThread.setName('updateLists') #set the name to the stock symb
      updateListsThread.start() #start the thread

    if(verbose): print("Waiting for stock lists to finish updating...")
    while(not listsUpdatedToday or len([t for t in o.threading.enumerate() if t.getName().startswith('update')])>0): #wait for the lists to finish updating
      # print([t.getName() for t in o.threading.enumerate() if t.getName().startswith('update')])
      time.sleep(2)
    if(verbose): print("lists done updating for syncPosList")

    #check that symb is somewhere in algoList
    #if it is, then add it to the algo that has it with the highest gain
    #else append it to the algo with the smallest gain
    for symb in [s for s in heldPos if s not in recPos]: #for all stocks actually held and not recorded

      algosWithStock = [e for e in algoList if symb in algoList[e]] #try and find a home for a stock by looking in the stocks to be bought (get all algos that may have it)
      if(len(algosWithStock)>0): #if an algo has it
        maxAlgo = ['x',0] #algo and the max gain of the stock
        #get the algo with the max gain for this stock
        for algo in algosWithStock: #look thru each algo that could hold the stock
          sellUp = eval(f"{algo}.sellUp('{symb}')") #find the sell up of that algo
          maxAlgo = [algo,sellUp] if sellUp>maxAlgo[1] else maxAlgo #get the greater of the two algos
        if(verbose): print(f"Adding {heldPos[symb]} shares of {symb} to {maxAlgo[0]}.")
        lock.acquire()
        posList[maxAlgo[0]][symb] = {'lastTradeDate':'NA',
                                     'lastTradeType':'NA',
                                     'sharesHeld':heldPos[symb],
                                     'shouldSell':False,
                                     'buyPrice':heldBuyPrices[symb],
                                     'note':''
                                    }
        lock.release()
        recPos[symb]=heldPos[symb] #also add the stock to the recPos temp var
        
      else: #if no algo has it
        minAlgo = ['x',100000] #algo and the min gain of the stock
        for algo in algoList: #for every algo that'll potentially gain
          sellDn = eval(f"{algo}.sellDn('{symb}')") #get the sell dn of each algo
          #TODO: figure out the logic here if it shoud be < or >, and what we value more (least loss, or highest variance)
          minAlgo = [algo,sellDn] if sellDn<minAlgo[1] else minAlgo #get the greater of the the two algos
        #add to the algo with the least loss (to minimize risk)
        if(verbose): print(f"No algo found to have {symb}. Adding {heldPos[symb]} shares to {minAlgo[0]}.")
        lock.acquire()
        posList[minAlgo[0]][symb] = {'lastTradeDate':'NA',
                                     'lastTradeType':'NA',
                                     'sharesHeld':heldPos[symb],
                                     'buyPrice':heldBuyPrices[symb],
                                     'shouldSell':False,
                                     'note':''
                                    }
        lock.release()
        recPos[symb]=heldPos[symb] #also add the stock to the recPos temp var

    #find symbols that have more actual shares than recorded shares
    #add the shares to the algo with the highest gain
    for symb in [s for s in heldPos if heldPos[s]>recPos[s]]: #for all stocks where the actual is greater than the recorded
      algosWithStock = [e for e in posList if symb in posList[e]] #get all algos holding the stock
      
      maxAlgo = algosWithStock[0] #init maxAlgo to the first algo in the list
      for algo in algosWithStock[1:]: #get the algo with the max gain potential and ensure that the symb is in the algo (skip the first one since it's the init value - save a loop)
        maxAlgo = algo if eval(f"{algo}.sellUp(symb)")>eval(f"{maxAlgo}.sellUp('{symb}')") else maxAlgo #get the algo with the largest sellUp value
      
      lock.acquire()
      posList[maxAlgo][symb]['sharesHeld'] += heldPos[symb]-recPos[symb] #add in the disparity
      lock.release()
      
  #remove any symbs that have 0 shares, remove any algos that have 0 symbs
  if(verbose): print("Removing blanks")
  for algo in list(posList):
    for symb in list(posList[algo]): #must be cast as list in order to not change dict size (this makes a copy)
      if(posList[algo][symb]['sharesHeld']==0):
        lock.acquire()
        posList[algo].pop(symb,None)
        lock.release()
    if(len(posList[algo])==0): #remove any algos that have 0 symbs
      lock.acquire()
      posList.pop(algo,None)
      lock.release()
  
  if(verbose): print("Marking to be sold")
  revSplits = o.reverseSplitters()
  for algo in posList:
    for symb in posList[algo]:
      if(symb in revSplits):
        if(verbose): print(f"{algo} - {symb} marked for sale")
        lock.acquire()
        posList[algo][symb]['shouldSell'] = True
        lock.release()
  
  #write to the file
  lock.acquire()
  with open(c['file locations']['posList'],'w') as f:
    if(verbose): print("Writing to posList file")
    f.write(json.dumps(posList,indent=2))
  lock.release()
  print("Done syncing posList")



#run the main function
if __name__ == '__main__':
  global posList
  
  a.checkValidKeys(int(c['account params']['isPaper'])) #check that the keys being used are valid
  if(len(a.getPos())==0): #if the trader doesn't have any stocks (i.e. they've not used this algo yet), then give them a little more info
    print("Will start buying "+str(c['time params']['buyTime'])+" minutes before next close")
  
  posList = setPosList(algoList) #initiate/populate the list of positions by algo
  
  #init the algos
  for algo in algoList:
    exec(f"{algo}.init('{configFile}')")

  #tell the user what algos are being tested
  print("\nUsing the algos: ",end="")
  print(*list(algoList),sep=", ",end="\n\n")
  
  syncPosList() #in the event that something changed during the last run, this should catch it
  print("\n") #leave a space between startup and main sequence
  
  main() #start running the program


'''
how to do due diligence:
https://www.investopedia.com/articles/stocks/08/due-diligence.asp
https://ourthinklab.com/finance/how-to-do-due-diligence-dd-buying-stock/


check mktcap
check revenue, profit, margin trends for past 2 years.
find competitors
compare p/e ratios between the target company and its competitors
management (founders, or new management? How long have they been in office?)
review balance sheet (good cash balances and looking at amount of debt based on company's business model, industry, and age (r&d))
how long have the shares been trading?
10-Q and 10-k reports (ptions, expenctions for future prices)
revenue/profit expectations for the next 2-3 years, trends affecting industry, company specific details (partnerships, joint ventures, IP, prudcts, etc)
risks (legal, industry, regulatory, environmentally friendly, etc)
'''
