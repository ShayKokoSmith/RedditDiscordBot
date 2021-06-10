import praw
import time
import urllib
import json
import pyodbc 
from redvid import Downloader
import os
from random import random
import cv2

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
postPullCount = "100" #number of posts to pull per round
roundWaitTime = 30 #seconds to wait in between rounds
apiLimitWaitTime = 5 #seconds to wait for the reddit api to catch up
firstPost = configuration["SUBREDDIT"]["firstpost"] #ID of first post on the subreddit
filepath = configuration["OTHER"]["filepath"] #location of saved files
backlog =('true'==configuration["OTHER"]["backlog"].lower()) #set to true to backlog the subreddit

#reply stuff
linkvid = configuration["OTHER"]["vidlink"]
rarefetchwordchance = configuration["OTHER"]["rarefetchwordchance"]
fetchwordcommon = configuration["OTHER"]["fetchwordcommon"]
fetchwordrare = configuration["OTHER"]["fetchwordrare"]
videoname = configuration["OTHER"]["fetchvidaltname"]

def aquireJson(url):
    response = urllib.request.urlopen(url)
    data = json.loads(response.read())
    return data

#Equivelent to calling u/savevideo on every single MP4 post (not GIF or images)
#randomly generates novelty sentences because the same one every time would get boring.
def vidLink(postID):
    
    post = reddit.submission(id=postID)
    if (random()>rarefetchwordchance):
        randomfetchword = fetchwordcommon[int((random())*len(fetchwordcommon))]
    else:
        randomfetchword = fetchwordrare[int((random())*len(fetchwordrare))]
    
    randomvidword = videoname[int((random())*len(videoname))]
    
    link="https://redditsave.com/info?url=/r/"+subredditName+"/comments/"+ postID #fallback link 
    flag=True
    i=0
    while(flag):
        try:
            data = aquireJson("https://www.reddit.com/"+postID+".json")
            link=data[0]["data"]["children"][0]["data"]["secure_media"]["reddit_video"]["fallback_url"].replace('?source=fallback','')
            flag=False
        except:
            if(i<5):
                i=i+1
                time.sleep(apiLimitWaitTime)
            else:
                flag=False
                print("using the savevideo link. for some reason. sorry.")

    postReply = "[I've " + randomfetchword + " the link to the "+ randomvidword + " for you!](" + link + ")"
    post.reply(postReply)
    print("linked to " + postID)

#adding to database
def databaseAdd(postID,postTitle,posterName,postTime,directURL,postType):
    
    try:
        mycursor.execute("""
        INSERT INTO post (PostID, PostTitle, PosterName, FileType, DirectURL, PostTime) 
        VALUES (?,?,?,?,?,?)""",
        postID, postTitle, posterName, postType, directURL, postTime) 
        cnxn.commit()
        print("added post to database")
        flag=True
        i=0
        while(flag):
            try:
                if(postType=='mp4' and linkvid):
                    vidLink(postID)
                flag=False
            except:
                if i>5:
                    flag=False
                    print("link creation failed")
                else:
                    i=i+1
                    print("link creation failed, waiting to try again")
                    time.sleep(apiLimitWaitTime)
                
    except pyodbc.Error as err:
        print(err)
        
    except:
        print("failed to add post to database")
                
def fileDownload(postID,postType,directURL):
    #download zone
    if (postType != "text"): #check if text
        if(os.path.exists(filepath + postID + '.' + postType)): #check if exists
            print("File already downloaded")
        else:
            if(postType == "mp4"): #mp4 download zone
                flag = True
                i=0
                while(flag):
                    try:
                        vidurl = directURL[18:]
                        redditvid = Downloader(max_q=True)
                        redditvid.url = "https://v.redd.it/" + vidurl
                        redditvid.path = filepath
                        redditvid.download()
                        print(filepath + vidurl + "-DASH_.mp4")
                        resolutions = ["1080", "720", "480", "360", "240", "96"]
                        for x in resolutions:
                            if (os.path.exists(filepath + vidurl + "-DASH_" + x + ".mp4")):
                                print(filepath + vidurl + "-DASH_" + x + ".mp4 has been found")
                                os.rename(filepath + vidurl + "-DASH_" + x + ".mp4", filepath + postID + ".mp4")
                        print("video downloaded")
                        flag = False
                    except:
                        if i>5:
                            flag=False
                            print("video download failed")
                        else:
                            i=i+1
                            print("link creation failed, waiting to try again")
                            time.sleep(apiLimitWaitTime)
            else: #picture download zone
                try:
                    urllib.request.urlretrieve(directURL, filepath + postID + "." + postType)
                    print("image downloaded")
                except:
                    print("image download failed")
            try:
                vid = cv2.VideoCapture( filepath+postID+'.'+postType)
                height = int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT)) # always 0 in Linux python3
                width  = int(vid.get(cv2.CAP_PROP_FRAME_WIDTH))  # always 0 in Linux python3
                print ("opencv: height:{} width:{}".format( int(height), int(width)))
                mycursor.execute("""UPDATE post SET HorizontalRes = ?, VerticalRes=? WHERE PostID = ?""",width,height, postID) 
                cnxn.commit()
            except:
                print("dimension add failed")
    else:
        print("text posts dont need downloading")

#derived values
subreddit = reddit.subreddit(subredditName)
url = "http://www.reddit.com/r/" + subredditName + "/new.json?&limit="+ postPullCount
tempSTR = ""
last=""
i=0
#start
if backlog: #BACKLOG SECTION
    while last != firstPost:
        
        #loop until the json can be acquired from the reddit
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
            postTitle = post['data']['title']       #Post Title
            posterName = post['data']['author']     #Poster Name
            postTime = post['data']['created_utc']  #Timestamp of when it was posted
            directURL = post['data']['url']         #URL to the image/video/text
            
            #determine filetype
            if directURL[8] == 'v': #why does reddit not just have an mp4?
                postType = "mp4" 
            elif directURL[8] == 'i':
                postType = directURL.split('.')[-1] #last dot
            else:
                postType = "text"
            
            #prints out the ID and everything
            print(postID)
            print(postTitle)
            print(posterName)
            print(postTime)
            print(directURL)
            print(postType)
            
            #checks if is in the database
            mycursor.execute("SELECT PostID FROM post WHERE PostID='"+postID+"'")
            if (mycursor.rowcount == 0):
                databaseAdd()
            else:
                print("Already in database")
            fileDownload()
            print("---------------------------------")
            i=i+1
            last=postID
        #grab a fresh one.
        url="http://www.reddit.com/r/" + subredditName + "/new.json?&limit="+ postPullCount + "&after=t3_" + last
        print("waiting for a bit")
        print(i)
        print("---------------------------------")
        time.sleep(roundWaitTime)

#streamwatch
print("aight, I've commandeered the entire subreddit. Initiating Phase II")
print("---------------------------------")

for submission in subreddit.stream.submissions():

    postID=submission.name[3:]         #Post ID
    postTitle = submission.title    #Post Title
    posterName = str(submission.author)    #Poster Name
    postTime = submission.created_utc #Timestamp of when it was posted
    directURL = submission.url        #URL to the image/video/text
    
    #determine filetype
    if directURL[8] == 'v': #why does reddit not just have an mp4?
        postType = "mp4" 
    elif directURL[8] == 'i':
        postType = directURL.split('.')[-1] #last dot
    else:
        postType = "text"
        
    #printout    
    print(postID)
    print(postTitle)
    print(posterName)
    print(postTime)
    print(directURL)
    print(postType)
    
    #checks if is in the database
    mycursor.execute("SELECT PostID FROM post WHERE PostID='"+postID+"'")
    if (mycursor.rowcount == 0):
        databaseAdd(postID,postTitle,posterName,postTime,directURL,postType)
    else:
        print("Already in database")
    fileDownload(postID,postType,directURL)
    print("------------------------------------------")