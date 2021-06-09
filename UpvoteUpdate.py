import praw
import time
import urllib
import json
import pyodbc 


configuration=json.load(open('config.json'))

#bot credentials
reddit = praw.Reddit(
    user_agent=configuration["REDDIT"]["user_agent"],
    client_id=configuration["REDDIT"]["client_id"],
    client_secret=configuration["REDDIT"]["client_secret"],
    username=configuration["REDDIT"]["username"],
    password=configuration["REDDIT"]["password"]
)

#SQL server login
server = configuration["SQLREADWRITE"]["server"]
database = configuration["SQLREADWRITE"]["database"]
username = configuration["SQLREADWRITE"]["username"]
password = configuration["SQLREADWRITE"]["password"]
cnxn = pyodbc.connect('DRIVER={SQL SERVER};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+ password)
mycursor = cnxn.cursor()

#config
subredditName = configuration["SUBREDDIT"]["subreddit"] #subreddit
postPullCount = "100" #number of posts to pull per round. DONT PUT HIGHER THAN 100
roundWaitTime = 10800 #seconds to wait in between rounds
apiLimitWaitTime = 5 #seconds to wait for the reddit api to catch up
firstPost = configuration["SUBREDDIT"]["firstpost"] #ID of first post on the subreddit
filepath = configuration["OTHER"]["filepath"] #location of saved files

#derived values
subreddit = reddit.subreddit(subredditName)
url = "http://www.reddit.com/r/" + subredditName + "/new.json?&limit="+ postPullCount
tempSTR = ""
last=""
i=0

def aquireJson(url):
    response = urllib.request.urlopen(url)
    data = json.loads(response.read())
    return data


while True:
    
    #loop until the json can be aquired from the reddit
    apiLimit=True
    while apiLimit:
        try:
            postlist = aquireJson(url)
            apiLimit=False #take the gold and run  
        except: #fuck me sideways
            print("API LIMIT HIT, WAITING")
            time.sleep(apiLimitWaitTime)
        
    for post in postlist['data']['children']: #we cutting up jason
        
        postID=post['data']['name'][3:]         #Post ID
        upvoteCount = post['data']['ups']           #post upvotes
        #prints out the ID and everything
        #print(postID)
        #print(upvoteCount)
        
        #updating votecount in database
        try:
            mycursor.execute("""
            UPDATE post SET Upvotes = ? WHERE PostID = ?""",
            upvoteCount, postID) 
            cnxn.commit()
            i=i+1
        except:
            print("failed")
        
    print(str(i) + " posts successfully upvotedated, waiting for a bit")
    i=0
    print("---------------------------------")
    time.sleep(roundWaitTime)