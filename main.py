from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, PicklePersistence
import requests
from datetime import datetime, timedelta
from helpers import get_coords, get_travel_time, meetup_time, get_placename, get_placeid
import os
from dotenv import load_dotenv
import re
import pytz

load_dotenv()

TOKEN = os.getenv("TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
SGT = pytz.timezone("Asia/Singapore")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/setpin (google maps link OR location name) : Set meeting location\n"
        "/clear : Clears previous meeting location \n"
        "/mode : Changes your mode of transport \n"
        "/meetup : Check your meet up timings, if any"
        "/setmeetup : Set a date and time to meet up \n"
        "After setting a location, simply send your own location to receive your travel time \n"
        "Reply 'leavetime' after setting a meet up to know what time you should leave"
    )

async def setpin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #check if user sent a link after /setpin
    if not context.args:
        await update.message.reply_text(
            "Usage: /setpin (google maps link)"
        )
        return

    #user has sent something after /setpin -> check if url/valid loc
    input = " ".join(context.args)
    if re.match(r"https?://", input):
        #url checking
        response = requests.get(input, allow_redirects=True)  
        coords = get_coords(response.url)
        placename = get_placename(response.url)
        if not coords:
            await update.message.reply_text("Couldn't find that location.")
            print("error 1")
            return
        #if there is a placename -> search for placeid
        if placename: 
            data = get_placeid(placename)
            if not data:
                await update.message.reply_text("Couldn't find that location.")
                print("error 2")
                return
            context.chat_data["pinned_location"] = {"lat": data["lat"], "long": data["long"], "place_id": data["placeid"], "name": data["name"]}
            await update.message.reply_text(f"Location saved at {data['name']}")
            return
        #else no placename in url
        else:
            context.chat_data["pinned_location"] = {"lat": coords[0], "long": coords[1], "place_id": None, "name": None}
            await update.message.reply_text(f"Location saved at {coords[0]} , {coords[1]}")
            return

    else:
        #is place name --> do placeid search
        data = get_placeid(input)
        if not data:
            await update.message.reply_text("Couldn't find that location.")
            print("error 3")
            return
        context.chat_data["pinned_location"] = {"lat": data["lat"], "long": data["long"], "place_id": data["placeid"], "name": data["name"]}
        url = f"https://www.google.com/maps/search/?api=1&query={data['name']}&query_place_id={data['placeid']}"
        await update.message.reply_text(f"Location saved at {data['name']}",
                                        reply_markup=InlineKeyboardMarkup([[
                                        InlineKeyboardButton("Open in Google Maps", url=url)
                                        ]]))

        return

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /clear (pinned/meetup/all)")
        return
    
    content = context.args[0]
    if content not in ["pinned", "meetup", "all"]:
        await update.message.reply_text("Usage: /clear (pinned/meetup/all)")
        return
    
    if content == "pinned":
        context.chat_data.pop("pinned_location", None)
        await update.message.reply_text("Location deleted!")
        return

    elif content == "meetup":
        context.chat_data.pop("meetup_time", None)
        await update.message.reply_text("Meetup deleted!")
        return
    
    elif content == "all":
        context.chat_data.pop("meetup_time", None)
        context.chat_data.pop("pinned_location", None)
        await update.message.reply_text("All cleared!")

async def setmeetup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "pinned_location" not in context.chat_data:
        await update.message.reply_text("No pinned location. \n"
                                        "Use /setpin to pin a location")
        return
    time = meetup_time("".join(context.args))
    if not time:
        await update.message.reply_text("Invalid date/time format")
        return
    
    context.chat_data["meetup_time"] = time
    await update.message.reply_text(f"Meet up set on {time.strftime("%d %B %Y at %I:%M%p")} \n"
                                    "Reply 'leavetime' to know what time you need to leave!")
    
async def meetup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "meetup_time" not in context.chat_data:
        await update.message.reply_text("No meetup set. \n"
                                        "Use /setmeetup to set a date and time")
        return
    
    meetup = context.chat_data.get("meetup_time")
    location = context.chat_data.get("pinned_location")
    await update.message.reply_venue(latitude=location["lat"], longitude=location["long"], title=location["name"], address=f"Meet on {meetup.strftime("%d %B %Y at %I:%M%p")}")
    
async def user_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "pinned_location" not in context.chat_data:
        await update.message.reply_text("No pinned location. \n"
                                        "Use /setpin to pin a location")
        return
    
    lat = update.message.location.latitude
    long = update.message.location.longitude

    context.user_data["current_location"] = {"lat": lat , "long": long}
    mode = "transit"
    context.user_data["mode"] = mode
    pinned = context.chat_data.get("pinned_location") #read
    if not pinned["place_id"]:
        travel_time = get_travel_time(lat, long, mode, dest_lat=pinned["lat"], dest_lon=pinned["long"])
        url = f"https://www.google.com/maps/dir/?api=1&origin={lat},{long}&destination={pinned['lat']},{pinned['long']}&travelmode={mode}"
    else:
        travel_time = get_travel_time(lat, long, mode, dest_placeid=pinned["place_id"])
        url = f"https://www.google.com/maps/dir/?api=1&origin={lat},{long}&destination={pinned['lat']},{pinned['long']}&destination_place_id={pinned['place_id']}&travelmode={mode}"
    context.user_data["travel_time"] = travel_time
    hrs = int(travel_time / 60)
    mins = travel_time % 60
    if hrs == 0:
        time = f"{mins}mins"
    elif mins == 0:
        time = f"{hrs}hrs"
    else:
        time = f"{hrs}hrs {mins}mins"
    arrival_time = datetime.now(SGT) + timedelta(minutes=travel_time)
    await update.message.reply_text(f"You are {time} away and will arrive at {arrival_time.strftime('%H:%M')}",
                                    reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton("Open in Google Maps", url=url)
                                    ]]))

async def changemode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /mode (drive/transit/walk)"
        )
        return
    
    mode = context.args[0]
    mode = mode.lower()

    if mode not in ["drive" , "transit", "walk"]:
        await update.message.reply_text(
            "Usage: /mode (drive/transit/walk)"
        )
        return
    
    context.user_data["mode"] = mode

    if "pinned_location" not in context.chat_data:
        await update.message.reply_text("No pinned location. \n"
                                        "Use /setpin to pin a location")
        return
    if "current_location" not in context.user_data:
        await update.message.reply_text("No user location. \n"
                                        "Use /setpin to pin a location")
        return
    
    current = context.user_data.get("current_location")
    pinned = context.chat_data.get("pinned_location")
    if not pinned["place_id"]:
        travel_time = get_travel_time(current["lat"], current["long"], mode, dest_lat=pinned["lat"], dest_lon=pinned["long"])
    else:
        travel_time = get_travel_time(current["lat"], current["long"], mode, dest_placeid=pinned["place_id"])
    
    if mode == "drive":
        url_mode = "driving"
    elif mode == "walk":
        url_mode = "walking"
    else: url_mode = mode

    context.user_data["travel_time"] = travel_time
    arrival_time = datetime.now(SGT) + timedelta(minutes=travel_time)
    hrs = int(travel_time / 60)
    mins = travel_time % 60
    if hrs == 0:
        time = f"{mins}mins"
    elif mins == 0:
        time = f"{hrs}hrs"
    else:
        time = f"{hrs}hrs {mins}mins"
    url = f"https://www.google.com/maps/dir/?api=1&origin={current['lat']},{current['long']}&destination={pinned['lat']},{pinned['long']}&travelmode={url_mode}"

    await update.message.reply_text(f"You are {time} away and will arrive at {arrival_time.strftime('%H:%M')}",
                                    reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton("Open in Google Maps", url=url)
                                    ]]))

async def leavetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if "leavetime" not in message.lower():
        return
    
    if not message.reply_to_message:
        return
    if message.reply_to_message.from_user.id != context.bot.id:
        return
    
    travel_time = context.user_data.get("travel_time")
    meetup = context.chat_data.get("meetup_time")
    if not meetup or not travel_time:
        await update.message.reply_text("Missing meetup/travel time")
        return
    leave_time = meetup - timedelta(minutes=travel_time)
    await update.message.reply_text(f"You should leave at {leave_time.strftime('%d %B %Y at %I:%M%p')} to reach at {meetup.strftime('%I:%M%p')}")
    

def main():
    persistence = PicklePersistence(filepath="bot_data.pkl")
    app = ApplicationBuilder().token(TOKEN).persistence(persistence).build()
    

    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("setpin", setpin_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("mode", changemode_command))
    app.add_handler(CommandHandler("setmeetup", setmeetup_command))
    app.add_handler(CommandHandler("meetup", meetup_command))
    app.add_handler(MessageHandler(filters.LOCATION, user_loc))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY, leavetime))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":

    main()