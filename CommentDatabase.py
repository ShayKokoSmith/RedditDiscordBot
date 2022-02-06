import asyncpraw
import time
import urllib
import json
import pyodbc
import discord
from discord.ext import commands
import sys

print(str(sys.argv))

if len(sys.argv) > 1:
    configuration=json.load(open(sys.argv[1]))
else:
    configuration=json.load(open('config.json'))

#bot credentials
reddit = asyncpraw.Reddit(
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

#Discord Bot Config
TOKEN = configuration["DISCORD"]["TOKEN"]
bot = commands.Bot(command_prefix='%%%%%%')

#config
subredditName = configuration["SUBREDDIT"]["subreddit"] #subreddit
postPullCount = "100" #number of posts to pull per round [MAX 100]
roundWaitTime = 30 #seconds to wait in between rounds
apiLimitWaitTime = 5 #seconds to wait for the reddit api to catch up
filepath = configuration["OTHER"]["filepath"] #location of saved files
backlog =('true'==configuration["OTHER"]["backlog"].lower()) #set to true to backlog the subreddit
backlogposttime = 0
requestthread = configuration["SUBREDDIT"]["requestthread"]
requestchannelID = configuration["DISCORD"]["requestchannel"]

def aquireJson(url):
    response = urllib.request.urlopen(url)
    data = json.loads(response.read())
    return data
    
def commentPrint(mainComment,i):
    commentID=mainComment['data']['id']
    postID=mainComment['data']['link_id'][3:]
    commenter=mainComment['data']['author']
    commentTime=mainComment['data']['created_utc']
    body=mainComment['data']['body']
    if (mainComment['data']['parent_id'][1]!='3'):
        parentID=mainComment['data']['parent_id'][3:]
    else:
        parentID=""
    print(commentID)
    print(postID)
    print(commenter)
    print(commentTime)
    print(parentID)
    print(body)
    
    i=i+1
    mycursor.execute("SELECT CommentID FROM comment WHERE CommentID='"+commentID+"'")
    if (mycursor.rowcount == 0):
        if (mainComment['data']['parent_id'][1]!='3'):
            mycursor.execute("""
            INSERT INTO comment (CommentID, PostID, ParentComment, CommentTime, CommenterName, Body) 
            VALUES (?,?,?,?,?,?)""",
            commentID, postID, parentID, commentTime, commenter, body) 
        else:
            mycursor.execute("""
            INSERT INTO comment (CommentID, PostID, CommentTime, CommenterName, Body) 
            VALUES (?,?,?,?,?)""",
            commentID, postID, commentTime, commenter, body) 
        cnxn.commit()
        print("added comment to database")
    else:
        print("Already in database")
    try:
        for comment in mainComment['data']['replies']['data']['children']:
            i=commentPrint(comment,i)
    except:
        i=i+0
    print('------')
    return i  
    
async def commentStream():
    subreddit = await reddit.subreddit(subredditName)
    while(True):
        try:
            print("Starting Comment stream")
            async for comment in subreddit.stream.comments():
                print("-------")
                commentID=comment.id
                postID=comment.link_id[3:]
                commenter=str(comment.author)
                commentTime=comment.created_utc
                body=comment.body
                if (comment.parent_id[1]!='3'):
                    parentID=comment.parent_id[3:]
                else:
                    parentID=""
                print(commentID)
                print(postID)
                print(commenter)
                print(commentTime)
                print(parentID)
                print(body)
                
                mycursor.execute("SELECT CommentID FROM comment WHERE CommentID='"+commentID+"'")
                if (mycursor.rowcount == 0):
                    try:
                        if (comment.parent_id[1]!='3'):
                            mycursor.execute("""
                            INSERT INTO comment (CommentID, PostID, ParentComment, CommentTime, CommenterName, Body) 
                            VALUES (?,?,?,?,?,?)""",
                            commentID, postID, parentID, commentTime, commenter, body) 
                        else:
                            mycursor.execute("""
                            INSERT INTO comment (CommentID, PostID, CommentTime, CommenterName, Body) 
                            VALUES (?,?,?,?,?)""",
                            commentID, postID, commentTime, commenter, body) 
                            if (postID == requestthread):
                                requestchannel = bot.get_channel(requestchannelID)
                                embed = discord.Embed(title="Request", url = ("https://www.reddit.com/comments/" + requestthread + "/requests/" + commentID + "/"))
                                embed.add_field(name="Username: ", value=commenter, inline=False)
                                embed.add_field(name="Comment: ", value=body, inline=False)
                                await requestchannel.send(embed=embed)
                                print("message sent")
                        cnxn.commit()
                        print("added comment to database")
                    except:
                        print('error adding to database')
                      
                else: 
                    print("Comment in database")
        except Exception as e:
            print("oopies i did a bit of a crash")
            print(e)

            
    await print("stopped for some reason")

@bot.event            
async def on_ready():
    await commentStream()
    
#START

print("Grab a partner and begin")
if(backlog):
    mycursor.execute("SELECT * FROM post WHERE PostTime > ?", backlogposttime)
    sqloutput = mycursor.fetchall()
    for row in sqloutput:
        print("-------------------------------------------------------")
        print(row.PostID + " " + row.PostTitle)
        print("")
        flag=True
        while(flag):
            try:
                data=aquireJson('https://www.reddit.com/'+row.PostID+'/.json')
                flag=False
            except:
                print("API LIMIT HIT")
                time.sleep(apiLimitWaitTime)
        i=0
        for thing in data[1]['data']['children']:
            i=commentPrint(thing,i)
            
            
            
        print(i)
print("-------------------------------------------------------")
print("Initializing Phase II")
print("-------------------------------------------------------")



bot.run(TOKEN)