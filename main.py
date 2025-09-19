from __future__ import annotations

import random
import json
from datetime import datetime

import discord
import pycountry
import requests
from bs4 import BeautifulSoup
from discord import app_commands

from chatbot import EnhancedConversation

ALIASES = ["speeb"]
WAKE_UP = ["hi", "hey", "heya", "good *", "whats up", "yo", "hello", "happy *"]

DISCLAIMER = ("-# I am a bot, and this message was produced using the help of Google's Gemini AI. "
              "Some of the info that I say may be inaccurate, and the opinions that it portrays may not be shared with "
              "the creator of this bot.")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client=client)

conversations: dict[int, list[EnhancedConversation]] = {}

# Accessing API keys from keys.json
with open("keys.json", "r") as keys:
    api_keys = json.load(keys)
    weather_api_key = api_keys["weather_api_key"]
    main_bot_token = api_keys["main_bot_token"]


@tree.command(name="wikipedia", description="Search something up on wikipedia!")
async def wiki_search(inter: discord.Interaction, search: str):
    local_disclaimer = "-# I am a bot, and this action was performed automatically."

    # Fine, I'll do it myself.
    PARAMS = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": search
    }

    response = requests.get("https://en.wikipedia.org/w/api.php", params=PARAMS).json()

    PARAMS = {
        "action": "parse",
        "pageid": response['query']['search'][0]['pageid'],
        "format": "json",
        'contentmodel': 'wikitext'
    }

    response = requests.get("https://en.wikipedia.org/w/api.php", params=PARAMS)
    new_html = BeautifulSoup(response.json()['parse']['text']['*'], features='lxml')
    all_paragraphs = new_html.find_all('p')
    summary = None
    for p in all_paragraphs:
        if p.text != '\n':
            summary = p.get_text().rstrip('\n')
            break

    if summary is None:
        await inter.response.send_message(f"I apologize, but I could not find that page on Wikipedia.\n"
                                          + local_disclaimer, ephemeral=True)
        return

    while '\n' in summary:
        summary = summary.replace('\n', '<placeholder>> ')

    while '<placeholder>' in summary:
        summary = summary.replace('<placeholder>', '\n ')

    await inter.response.send_message(f"According to **Wikipedia:**\n> {summary}\n" + local_disclaimer)


# Generalized commands! Little to no AI usage for the below.
# First, let's be friendly.

greetings = ["Sure", "No problem", "Of course", "Definitely"]


@tree.command(name="currency", description="check the current exchange rate for two currencies")
async def exchange_rate(inter: discord.Interaction, convert_to: str,
                        convert_from: str = "USD", amount: int = 1):
    # use the API lookup
    api_url = (f"https://api.fxratesapi.com/latest?base={convert_from}&currencies={convert_to}&"
               f"amount={amount}&places=2&format=json")
    conversion = requests.get(api_url).json()

    url = "https://api.fxratesapi.com/currencies"
    response = requests.get(url).json()

    embed = discord.Embed(title=f"Currency Exchange", description="(via fxratesapi.com)", url="https://fxratesapi.com/",
                          color=0xfab9ff)
    embed.set_author(name=client.user.name, icon_url=client.user.avatar.url)

    base_currency_name = response[convert_from]['name'] if amount == 1 else response[convert_from]['name_plural']
    embed.add_field(name=f"{amount} {convert_from} is equal to:", value=base_currency_name, inline=True)

    check_currency_name = response[convert_to]['name'] if conversion['rates'][convert_to] == 1 else \
        response[convert_to]['name_plural']
    embed.add_field(name=f"{conversion['rates'][convert_to]} {convert_to}", value=check_currency_name,
                    inline=True)

    embed.set_footer(text="I am a bot, and this action was performed automatically.")

    await inter.response.send_message(f"{random.choice(greetings)}! **{amount} {base_currency_name}** is equivalent to "
                                      f"**{conversion['rates'][convert_to]} {check_currency_name}**.", embed=embed)


@tree.command(name="weather", description="Look up the weather for a certain city")
@app_commands.choices(units=[
    app_commands.Choice(name="Metric (km/°C)", value="metric"),
    app_commands.Choice(name="Imperial (mi/°F)", value="imperial")
])
async def weather_lookup(inter: discord.Interaction, city: str, units: app_commands.Choice[str] = "metric"):
    if not isinstance(units, str):
        units = units.value

    _key = weather_api_key
    response = requests.get(f"https://api.openweathermap.org/data/2.5/weather?q="
                            f"{city}&appid={_key}&units={units}").json()

    try:
        icon_url = f"https://openweathermap.org/img/wn/{response['weather'][0]['icon']}@4x.png"
    except KeyError:
        await inter.response.send_message("I apologize, but I could not find that city.\n"
                                          "-# I am a bot, and this action was performed automatically.", ephemeral=True)

    country = pycountry.countries.get(alpha_2=response['sys']['country'])
    embed = discord.Embed(title=f"Weather Forecast in {response['name']}, {country.name}",
                          url="https://openweathermap.org/",
                          description="Via openweathermap.org", color=0xfab9ff)
    embed.set_author(name=client.user.name, icon_url=client.user.avatar.url)
    embed.set_thumbnail(url=icon_url)

    weather_description = ' '.join(word.capitalize() for word in response['weather'][0]['description'].split(' '))

    embed.add_field(name=weather_description, value="Weather Description", inline=True)
    embed.add_field(name=f"Currently, {round(response['main']['temp'])}°{'C' if units == 'metric' else 'F'}",
                    value="Current temperature", inline=True)

    embed.add_field(name="More Temperature Info 🌡️",
                    value=f"Today, {response['name']} will have a high of {round(response['main']['temp_max'])}"
                          f"°{'C' if units == 'metric' else 'F'} and a low of {round(response['main']['temp_min'])}"
                          f"°{'C' if units == 'metric' else 'F'}. \nOutside, it feels like "
                          f"{round(response['main']['feels_like'])}°{'C' if units == 'metric' else 'F'}.",
                    inline=False)

    sunrise_time = datetime.fromtimestamp(response['sys']['sunrise'] + response['timezone'] + 25200)
    sunrise_time = sunrise_time.strftime('%I:%M %p').lstrip('0')

    sunset_time = datetime.fromtimestamp(response['sys']['sunset'] + response['timezone'] + 25200)
    sunset_time = sunset_time.strftime('%I:%M %p').lstrip('0')

    embed.add_field(name="Sunrise/Sunset ☀️🌙",
                    value=f"Today, sunrise will be at {sunrise_time}, and sunset will be at {sunset_time}.",
                    inline=True)
    embed.set_footer(text="I am a bot, and this action was performed automatically.")

    await inter.response.send_message(f"{random.choice(greetings)}! Currently, in **{response['name']}, "
                                      f"{country.name}**, it is {round(response['main']['temp'])}°"
                                      f"{'C' if units == 'metric' else 'F'} with {response['weather'][0]['description']}"
                                      f".", embed=embed)


@tree.command(name="about", description="A little about myself")
@app_commands.choices(hidden=[app_commands.Choice(name="True", value="True"),
                              app_commands.Choice(name="False", value="False")])
async def about_me(inter: discord.Interaction, hidden: app_commands.Choice[str] = "True"):
    if not isinstance(hidden, str):
        hidden = hidden.value

    about_me_message = """
    ## About me! :sparkles:
Hi! I'm Speebot, and I'm an AI-based pet-project made to bring some life to your discord server.
### How are you generating text?
As you may know, behind my text-based personality is Google Gemini, who is the backbone of the "intelligence" part of my *artificial intelligence* moniker :brain:
*Why Google Gemini instead of ChatGPT?* Great question! And the answer is simple- it's because Google's giving it away for free :face_with_hand_over_mouth:
But, this does come with some pretty important disclaimers, so *read carefully* below.

**Disclaimer:** due to the free-tier of Google's Gemini API, by conversing with this bot your data is being collected and potentially used to further train Google's AI models. There should be no expectation of privacy and you accept the risks associated with this style of interaction.
### What else can you do?
**Now,** that's for you to figure out. Some fun commands that I like are `/weather` :white_sun_rain_cloud: and `/wikipedia` :nerd:.
Sometimes there will be easter eggs involved as well, and those are for you to find. *Hint: when you type `/`, Discord brings up a context menu and shows you some commands :shushing_face:*
-# Made with :two_hearts: by a tired computer science student.
    """

    await inter.response.send_message(about_me_message, ephemeral=bool(hidden))


def create_reply(message: discord.Message, conversation: EnhancedConversation) -> (str, discord.Embed | None):
    # first, check which category the message belongs to.
    classification_response = conversation.classify(message.content, message.author).rstrip('\n')
    embed = None

    if " " in classification_response:
        classification = classification_response.split(' ')[0]
    else:
        classification = classification_response

    match classification:
        case "search":
            response = conversation.search(message.content)
            reply = response[0]
            embed = response[1][0]
            embed.set_author(name=client.user.name, icon_url=client.user.avatar.url)

        case "weather":
            response = conversation.weather_prompt(message.content)
            reply = response[0]
            embed = response[1][0]
            embed.set_author(name=client.user.name, icon_url=client.user.avatar.url)

        case "currency":
            response = conversation.currency_exchange(message.content)
            reply = response[0]
            embed = response[1][0]
            embed.set_author(name=client.user.name, icon_url=client.user.avatar.url)

        case "music":
            response = conversation.music_lookup(message.content)
            reply = response[0]
            embed = response[1][0]
            embed.set_author(name=client.user.name, icon_url=client.user.avatar.url)

        case "myself":
            reply = conversation.about_myself(message.content)

        case _:
            reply = conversation.reply(message.content)

    return reply, embed


async def reply_action(message: discord.Message, conversation: EnhancedConversation | None = None):
    """Helper function to make message sending and conversation creation more streamlined"""
    if message.guild.id not in conversations:
        conversations[message.guild.id] = []

    if conversation is None:
        # time to create a new conversation
        conversation = EnhancedConversation()
        conversations[message.guild.id].append(conversation)

    async with message.channel.typing():
        response = create_reply(message, conversation)

        response_content = response[0]
        embed = response[1]
        if response_content.endswith('\n'):
            response_content += DISCLAIMER
        else:
            response_content += '\n' + DISCLAIMER

    if embed is None:
        sent_message = await message.reply(content=response_content)
    else:
        sent_message = await message.reply(content=response_content, embed=embed)

    conversation.append(sent_message.id)


@client.event
async def on_message(message: discord.Message):
    global conversations

    # ignore messages by the bot itself
    if message.author == client.user:
        return

    # continuation of conversations
    if message.reference is not None:
        get_reference_message = await message.channel.fetch_message(message.reference.message_id)

        # fast fail: not replying to bot
        if get_reference_message.author.id != client.user.id:
            return

        try:
            conversation_list = conversations[message.guild.id]

            # check through conversations
            for convo in conversation_list:
                if message.reference.message_id in convo.message_ids:

                    if "wah gwan" in message.content.lower():
                        convo.flags += "You only talk in a Toronto accent. "

                    await reply_action(message, convo)
                    return

            # guild found but conversation wasn't- create new one
            await reply_action(message)
            return

        # fringe case: replying to bot but the message ID is not/ no longer logged (create new convo)
        except KeyError:
            conversations[message.guild.id] = []

        # time to create a new conversation
        new_convo = EnhancedConversation()
        new_convo.manual_add(get_reference_message.content)

        if "wah gwan" in message.content.lower():
            new_convo.flags += "You only talk in a Toronto accent. "

        await reply_action(message, new_convo)

    # create new conversations: first, via wakeup
    if len(message.content.split()) > 1:
        # remove the non-alphanumeric characters, and make all characters lowercase (somehow, this actually works!)
        check_string = ''.join(char.lower() if char.isalnum() or char == ' ' else '' for char in list(message.content))
        check_list = check_string.split(' ')

        # first case: greeting is one word long
        for alias in ALIASES:
            if alias in check_list[1] and check_list[0] in WAKE_UP:
                await reply_action(message)

        # second case: greeting is two words long
        if len(message.content.split()) > 2:
            for alias in ALIASES:
                # SPECIAL CASE: TORONTO SPECIAL (Easter Egg)
                if alias in check_list[2] and ' '.join((check_list[0], check_list[1])) == "wah gwan":

                    # time to create a new conversation
                    new_convo = EnhancedConversation()
                    new_convo.flags += "You only talk in a Toronto accent. "
                    await reply_action(message, new_convo)

                # general case: everything else
                if alias in check_list[2] and (' '.join((check_list[0], check_list[1])) in WAKE_UP or
                                               check_list[0] == "good" or check_list[0] == "happy"):
                    await reply_action(message)

    # second case: via mention
    if f"<@{client.user.id}>" in message.content:
        # time to create a new conversation
        message.content = message.content.replace(f"<@{client.user.id}>", ALIASES[0])
        await reply_action(message)

# DO NOT CHANGE ANY INFORMATION BELOW THIS LINE
# On ready listener-- Ensuring that the commands are synced up n all

@client.event
async def on_ready():
    await tree.sync()
    print("Bot is ready.\n-----")

    game = discord.CustomActivity("Ready to chat 💭")
    await client.change_presence(status=discord.Status.idle, activity=game)


if __name__ == "__main__":
    # Speeb v2.0 Client ID
    client.run(main_bot_token)
