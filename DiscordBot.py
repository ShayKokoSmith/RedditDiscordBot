from asyncio.windows_events import NULL
import discord
from discord.ext import commands
import pyodbc
import os
import time
import json
import urllib

configuration=json.load(open('config.json'))

filepath = configuration["OTHER"]["filepath"] #location of saved files
apiLimitWaitTime = 5 #seconds to wait for the reddit api to catch up

#Discord Bot Config
TOKEN = configuration["DISCORD"]["TOKEN"]
bot = commands.Bot(command_prefix=configuration["DISCORD"]["PREFIX"])
elevatedChannels = configuration["DISCORD"]["ELEVATEDCHANNELS"]

#SQL server login
server = configuration["SQLREAD"]["server"]
database = configuration["SQLREAD"]["database"]
username = configuration["SQLREAD"]["username"]
password = configuration["SQLREAD"]["password"]
cnxn = pyodbc.connect('DRIVER={SQL SERVER};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+ password)
mycursor = cnxn.cursor()

def aquireJson(url):
    response = urllib.request.urlopen(url)
    data = json.loads(response.read())
    return data

#fetches the full filename, given a post ID  
def fileNameFetch(postID):
    cmd = "SELECT FileType FROM post WHERE PostID= ?"
    mycursor.execute(cmd, (postID,))
    filetype = mycursor.fetchone()
    path = filepath + postID + '.' + filetype.FileType
    print(path)
    return path

#checks if the channel is in the whitelist of elevated channels
def channelWhitelist(channel):
    inthelist = False
    for x in elevatedChannels:
        if channel.channel.id == int(x):
            inthelist = True
    return inthelist
    
#returns the requested video
@bot.command(name='vidfetch', help = 'fetchs the video file of a given reddit post ID')
async def vidfetch(ctx, *postID):
    print(postID)

    #If its not an elevated channel, they only get a single video
    if (False==channelWhitelist(ctx)):
        postID=[postID[0]]

    for post in postID:
        print(post)
        cmd = "SELECT * FROM post WHERE PostID= ?"
        mycursor.execute(cmd, (post,))
        
        if (mycursor.rowcount == 0):
            await ctx.send('Post doesn\'t exist')
        else:
            sqloutput = mycursor.fetchone()
            message = 'Title: ' + sqloutput.PostTitle + '\n' +'By u/' + sqloutput.PosterName
            path = fileNameFetch(post)

            #checks if its larger than 8MB
            if ((os.stat(path).st_size)> 8388600):

                #check for filetype
                if(sqloutput.FileType=='mp4'):

                    #check if resolution is in the database. If not, fetch from link from reddit, if yes, blindly hope that whats in the database is legit.
                    if(sqloutput.VerticalRes==None):
                        try:
                            data = aquireJson("https://www.reddit.com/"+post+".json")
                            link=data[0]["data"]["children"][0]["data"]["secure_media"]["reddit_video"]["fallback_url"].replace('?source=fallback','') + ' \n sorry it aint going to have audio'
                        except:
                            link="File larger than 8MB, Failed to get link"
                    elif(sqloutput.VerticalRes>=720):
                        link=sqloutput.DirectURL+'/DASH_720.mp4 \n sorry it aint going to have audio'
                    elif(sqloutput.VerticalRes>=480):
                        link=sqloutput.DirectURL+'/DASH_480.mp4 \n sorry it aint going to have audio'
                    elif(sqloutput.VerticalRes>=360):
                        link=sqloutput.DirectURL+'/DASH_360.mp4 \n sorry it aint going to have audio'
                    elif(sqloutput.VerticalRes>=240):
                        link=sqloutput.DirectURL+'/DASH_240.mp4 \n sorry it aint going to have audio'
                    else:
                        link="File larger than 8MB, Failed to get link"
                else:
                    link=sqloutput.DirectURL
                await ctx.send(message + '\n'+link)
            else:
                 await ctx.send(message, file=discord.File(path))
             
#looks for the string and returns the top posts containing a string, up to 1500 characters
@bot.command(name='findthis', help = 'Looks for a string and returns posts containing that string')    
async def findthis(ctx, *args):
    searchString =""
    for word in args:
        if (len(searchString)==0):
            searchString = str(word)
        else:
            searchString = searchString + " " + str(word)
    cmd = "SELECT * FROM post WHERE PostTitle LIKE ? ORDER BY Upvotes DESC"
    param = f'%{searchString}%'
    mycursor.execute(cmd, param)
    sqloutput = mycursor.fetchall()
    outputtext = ''
    excessloop = 0
    for row in sqloutput:
        if (len(outputtext)<1500): #i dont even know if 1500 is the right length. Its probably fine. it doesnt seem like its worth putting in the config
            outputtext = outputtext + '`'+'ID: ' + row.PostID + ' Title: "' + row.PostTitle + '" by: u/' + row.PosterName + '`' + '\n'
        else:
            excessloop = excessloop + 1
        
    if(outputtext==''):
        outputtext='No title containing that string exists'
    elif(excessloop>0):
        outputtext = outputtext + 'and another ' + str(excessloop) + ' more posts'
    await ctx.send(outputtext)

#same deal but the first param being a reddit user
@bot.command(name='findfromuser', help = 'Looks for posts from a user.')    
async def findfromuser(ctx, *args):
    if len(args)==0:
        outputtext="Invalid input.\n Syntax: `%findfromuser user [string]`"
    else: #there has to be a better way of doing this.
        if len(args)==1:
            param2= f'%'
        else:
            param2 = f'%{args[1]}%'
        param = f'%{args[0]}%'
        cmd = "SELECT * FROM post WHERE (PostTitle LIKE ?) AND (PosterName LIKE ?) ORDER BY Upvotes DESC"
        
        mycursor.execute(cmd, param2, param)
        sqloutput = mycursor.fetchall()
        outputtext = ''
        excessloop = 0
        for row in sqloutput:
            if (len(outputtext)<1500):
                outputtext = outputtext + '`'+'ID: ' + row.PostID + ' Title: "' + row.PostTitle + '" by: u/' + row.PosterName + '`' + '\n'
            else:
                excessloop = excessloop + 1
            
        if(outputtext==''):
            outputtext='Nothing from user found.'
        elif(excessloop>0):
            outputtext = outputtext + 'and another ' + str(excessloop) + ' more posts'
    await ctx.send(outputtext)

#ehh same as the help. tbh i dont think this is very uselus but someone really wanted it. 
@bot.command(name='bestof', help = 'Finds the best posts per certain increment in days. Optional second number for number of increments')
async def bestof(ctx, *daynumber):
    timeincrement=int(daynumber[0])*86400
    if len(daynumber)>1:
        maxcount=int(daynumber[1])
    else:
        maxcount=1000000000
    count=0
    time1 = time.time()
    print(time1)
    flag = True
    bestofoutput = ""
    if(timeincrement<1):
        flag= False
        bestofoutput= "Fuck it. It's all good."
    while (flag):
        lowtime=time1-timeincrement
        cmd = "SELECT * FROM post WHERE (PostTime > ?) AND (? > PostTime) ORDER BY UPVOTES DESC"
        mycursor.execute(cmd, (lowtime, time1,))
        sqloutput = mycursor.fetchone()
        print(sqloutput)
        try:
            bestofoutput = bestofoutput + sqloutput.PostID + " "
        except:
            print("nothing good this week")
        time1=time1-timeincrement
        if (time1 < 1570171860):
            flag=False
        count=count+1
        if count==maxcount:
            flag=False
    await ctx.send(bestofoutput)


@bot.command(name='bestofthetime', help= 'finds the top posts from a given number of days ago')
async def bestofthetime(ctx, *args):
    timeagostart=int(args[0])
    if len(args)>1:
        timeagoend=int(args[1])
    else:
        timeagoend=timeagostart+1
    timeagoend = timeagoend*86400
    timeagostart = timeagostart*86400
    if timeagostart>timeagoend:
        temp=timeagostart
        timeagostart=timeagoend
        timeagoend=temp
    timestart = time.time()-timeagostart
    timeend = time.time()-timeagoend
    bestofoutput=""
    cmd = "SELECT * FROM post WHERE (PostTime > ?) AND (? > PostTime) ORDER BY UPVOTES DESC"
    mycursor.execute(cmd, (timeend, timestart,))
    sqloutput = mycursor.fetchall()
    print(sqloutput)
    for x in range(0,3):
        try:
            bestofoutput = bestofoutput + sqloutput[x].PostID + " " + "Title: " + sqloutput[x].PostTitle + "\n"
        except:
            bestofoutput = bestofoutput
    if bestofoutput=="":
        bestofoutput= "Nothing found"
    await ctx.send(bestofoutput)

#straight SQL commands in elevated channels. Hopefully your SQL READ bot only has read access and isnt an admin for some reason.
@bot.command(name = 'sql', hidden = True)
async def sql(ctx, *args):
    msg=""
    for x in args:
        msg = msg + x + " "
    if (channelWhitelist(ctx)):
        mycursor.execute(msg)
        sqloutput = mycursor.fetchall()
        response=""
        for x in sqloutput:
            if((len(response)+len(str(x)))>1999):
                await ctx.send(response)
                response=""
            response=response + "\n \n"+ str(x)
            
        await ctx.send(response)

    




bot.run(TOKEN)