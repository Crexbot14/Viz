import discord
import asyncio
from pymongo import MongoClient
import requests
from datetime import datetime
import os
from urllib.parse import urlparse
import time
import threading
import aiohttp
from aiohttp import MultipartWriter
import uuid
from pathlib import Path
from aiohttp import FormData

bot = discord.Bot()
TOKEN = '.'

user_running_states = {}
user_client_managers = {}

mongo_client = MongoClient('mongodb+srv://AutoEconomy:0921229784653120@autoeconomy.uf1wywq.mongodb.net/')
db = mongo_client['AutoEconomy']
auto_chat_collection = db["AutoData"]
from discord.ext import commands
from discord.ui import Button, View


class AccountButtonControl(discord.ui.Button['AccountButtonControl']):
    def __init__(self, author, account_index):
        super().__init__(style=discord.ButtonStyle.secondary, label=f"Account {account_index + 1}", custom_id=f"account-{account_index}")
        self.author = author
        self.account_index = account_index

    async def callback(self, interaction: discord.Interaction):
        # Defer the interaction response immediately
        await interaction.response.defer()

        if interaction.user != self.author:
            await interaction.followup.send("You are not authorized to select this account.", ephemeral=True)
        else:
            # Fetch the user data again to get the latest status
            user_id = str(self.author.id)
            user_data = auto_chat_collection.find_one({"_id": user_id})

            if user_data is None:
                await interaction.followup.send("User data not found. Please set up your user data first.")
                return

            # Create a new embed message
            embed = discord.Embed(title="Control Panel", description=f"Select which account to start or stop for user <@{user_id}>", color=discord.Color.blue())

            # Create the "Run" and "Stop" buttons for the selected account
            view = ControlButtonView(interaction.user, self.account_index)
            config = user_data['configs'][self.account_index]
            status = "Running" if config['is_running'] else "Offline"
            embed.add_field(name=f"Account {self.account_index + 1}", value=status, inline=False)

            if len(view.children) == 0:  # Only add the buttons if they haven't been added yet
                run_button = discord.ui.Button(style=discord.ButtonStyle.green, label="Run", custom_id=f"run-{self.account_index}")
                stop_button = discord.ui.Button(style=discord.ButtonStyle.red, label="Stop", custom_id=f"stop-{self.account_index}")

                view.add_item(run_button)
                view.add_item(stop_button)

            # Edit the original message with the new embed and buttons
            await interaction.edit_original_response(embed=embed, view=view)

class ControlButtonView(discord.ui.View):
    def __init__(self, user: discord.User, account_index: int):
        super().__init__()
        self.user = user
        self.account_index = account_index

    @discord.ui.button(label="Run", custom_id="run-button", style=discord.ButtonStyle.green)
    async def button_callback(self, button, interaction):
        if interaction.custom_id != "run-button":
            await interaction.response.defer()
            return

        try:
            await interaction.response.defer(ephemeral=True)
            user_id = str(interaction.user.id)

            user_data = auto_chat_collection.find_one({"_id": user_id})

            if user_data is None:
                await interaction.followup.send(content="User data not found. Please set up your user data first.")
                return

            if user_data['configs'][self.account_index]['is_running']:
                await interaction.followup.send(content="The bot is already running!")
                return

            auto_chat_collection.update_one({"_id": user_id}, {"$set": {f"configs.{self.account_index}.is_running": True}})

            token = user_data['configs'][self.account_index]['token']
            if token:
                # Check if a UserClientManager already exists for this user and account
                if (user_id, self.account_index) in user_client_managers:
                    user_client_manager = user_client_managers[(user_id, self.account_index)]
                else:
                    user_client_manager = UserClientManager(user_id, db, self.account_index)
                    user_client_managers[(user_id, self.account_index)] = user_client_manager

                asyncio.create_task(user_client_manager.start())
                embed = discord.Embed(title="Bot Status", color=discord.Color.green())
                embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
                embed.add_field(name="Account", value=self.account_index + 1, inline=True)  # Add 1 to the account index
                embed.add_field(name="Status", value="Running", inline=True)
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(content="Token not found. Please set your token first.")

        except Exception as e:
            print(f"An error occurred: {e}")
            await interaction.followup.send(content=f"An error occurred: {e}")

    @discord.ui.button(label="Stop", custom_id="stop-button", style=discord.ButtonStyle.red)
    async def stop_button_callback(self, button, interaction):
        try:
            await interaction.response.defer()
            user_id = str(interaction.user.id)

            user_data = auto_chat_collection.find_one({"_id": user_id})

            if user_data is None:
                await interaction.followup.send("User data not found. Please set up your user data first.")
                return

            if not user_data['configs'][self.account_index]['is_running']:
                await interaction.followup.send("The bot is not running!")
                return

            auto_chat_collection.update_one({"_id": user_id}, {"$set": {f"configs.{self.account_index}.is_running": False}})
            await interaction.followup.send("Bot stopped. Thanks For Using AutoChatter!")

        except Exception as e:
            print(f"An error occurred: {e}")
            await interaction.followup.send(f"An error occurred: {e}")

    async def start_bot(self, user_id, token, interaction):
        try:
            db = mongo_client['AutoEconomy']
            autob = AutoBotClient(user_id, db, token, self.account_index)

            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(None, autob.start)
            thread = await future

            await interaction.edit_original_message(content="Bot started. Thanks For Using AutoChatter!")
        except Exception as e:
            print(f"An error occurred when starting the bot: {e}")
            await interaction.edit_original_message(content=f"An error occurred: {e}")

@bot.slash_command()
async def control(ctx):
    user_id = str(ctx.author.id)

    # Use the 'AutoData' collection
    data = auto_chat_collection.find_one({'_id': user_id})
    if data is None:
        embed = discord.Embed(title="Error", description="No data found for this user.", color=0xff0000)
        await ctx.respond(embed=embed)
    else:
        view = discord.ui.View()
        for i in range(len(data['configs'])):
            view.add_item(AccountButtonControl(ctx.author, i))

        # Respond to the interaction with a button that opens the modal
        await ctx.respond("Select an account to control", view=view)
        
class MyButton(discord.ui.View): # Create a class called MyView that subclasses discord.ui.View
    @discord.ui.button(label="Click me!", style=discord.ButtonStyle.primary, emoji="😎") # Create a button with the label "😎 Click me!" with color Blurple
    async def button_callback(self, button, interaction):
        await interaction.response.send_message("You clicked the button!") # Send a message when the button is clicked

@bot.slash_command() # Create a slash command
async def button(ctx):
    await ctx.respond("This is a button!", view=MyButton())




class AutoBotClient:
    def __init__(self, user_id, db, config):
        self.user_id = user_id
        self.db = db
        self.config = config
        self.token = config['token']
        self.headers = {"Authorization": self.token}
        self.base_url = "https://discord.com/api/v9"
        self.last_message_id = {}
        self.initial_log_done = False
        self.channel_ids = config['channel_ids'].split(',')  # Initialize channel_ids from config
        self.slowmode_delays = {}  # Initialize slowmode_delays as an empty dictionary
        self.unique_users_thresholds = config['unique_users_thresholds']  # Initialize unique_users_thresholds from config
        self.specific_messages = config['specific_messages']  # Initialize specific_messages from config
        self.specific_images = config['specific_images']  # Initialize specific_images from config
        self.session = aiohttp.ClientSession()   # Create a new aiohttp session

    async def start(self):
        await self.on_ready()
        while True:
            config = auto_chat_collection.find_one({"_id": self.user_id})
            if self.config and 'is_running' in self.config and self.config['is_running']:
                await self.check_and_send_messages()
            await asyncio.sleep(3)

    async def close(self):
        await self.session.close()

    async def on_ready(self):
        print(f"AutoBotClient for user {self.user_id} is ready and initializing.")
        try:
            # Check if the token is valid
            async with self.session.get(
                f"{self.base_url}/users/@me",
                headers=self.headers
            ) as response:
                if response.status != 200:
                    print("Invalid token")
                    return

                user_info = await response.json()
                print(f"{user_info['username']} - valid token")

            config = auto_chat_collection.find_one({"_id": self.user_id})
            if config:
                if not self.initial_log_done:
                    print(f"{self.user_id} - Working")
                    self.initial_log_done = True

                # Fetch the user's token from the database
                self.token = self.config['token']

                self.channel_ids = self.config['channel_ids'].split(',')
                self.messages = self.config['messages']
                self.message_counter = self.config['message_counter']
                self.ignored_user_id = self.config['ignored_user_id']
                self.specific_messages = self.config['specific_messages']
                self.specific_images = self.config['specific_images']

                user_running_states[self.user_id] = user_running_states.get(self.user_id, {})
                user_running_states[self.user_id]['normal'] = True

                # Fetch the slowmode delay for each channel
                for channel_id in self.channel_ids:
                    async with self.session.get(
                        f"{self.base_url}/channels/{channel_id}",
                        headers=self.headers
                    ) as response:
                        response.raise_for_status()
                        channel_info = await response.json()
                        self.slowmode_delays[channel_id] = channel_info['rate_limit_per_user']

        except Exception as e:
            print(f"An error occurred in AutoBotClient for user {self.user_id}: {e}")

    async def check_and_send_messages(self):
        # Check if is_running is set to True for the user
        for channel_id in self.channel_ids:
            await self.perform_message_check(channel_id)
        config = auto_chat_collection.find_one({"_id": self.user_id})
        if self.config and 'is_running' in self.config and self.config['is_running']:
            # rest of the code
            for channel_id in self.channel_ids:
                await self.perform_message_check(channel_id)

    async def on_message(self, message):
        if message.author.id == self.user.id:
            return

        # Update the total_messages, active_hours, and most_used_words fields in the database
        auto_chat_collection.update_one(
            {"user_id": message.author.id},
            {"$inc": {"total_messages": 1},
             "$push": {"active_hours": datetime.now().hour},
             "$addToSet": {"most_used_words": {"$each": message.content.split()}}
            }
        )

    async def perform_message_check(self, channel_id):
        # Get the last message in the channel
        async with self.session.get(
            f"{self.base_url}/channels/{channel_id}/messages",
            headers=self.headers,
            params={"limit": 50}
        ) as response:
            response.raise_for_status()
            messages = await response.json()
            user_messages = [msg for msg in messages if (self.ignored_user_id is None or msg['author']['id'] != self.ignored_user_id) and int(msg['id']) > self.last_message_id.get(channel_id, 0)]
            unique_users = set(msg['author']['id'] for msg in user_messages)

            # Get the unique users threshold for the channel
            unique_users_threshold = self.unique_users_thresholds.get(channel_id, 2)

            if len(unique_users) >= unique_users_threshold and self.messages:
                # Get the next message
                message_content = self.specific_messages.get(channel_id, self.messages[self.message_counter])
                image_url = self.specific_images.get(channel_id, None)
                await self.send_message(channel_id, message_content, image_url)

                # Update the message counter
                self.message_counter = (self.message_counter + 1) % len(self.messages)

                auto_chat_collection.update_one(
                    {"_id": self.user_id},
                    {"$set": {"message_counter": self.message_counter}}
                )

            # Wait for the slowmode delay before the next message
            await asyncio.sleep(self.slowmode_delays.get(channel_id, 0))

    async def send_message(self, channel_id, message_content, image_url=None):
        # Send a message to the channel
        data = FormData()
        data.add_field('content', message_content)
        if image_url:
            async with self.session.get(image_url) as image_response:
                image_response.raise_for_status()
                parsed_url = urlparse(image_url)
                image_name = os.path.basename(parsed_url.path)  # Use only the path part of the URL
                ext = os.path.splitext(image_name)[1]  # Get the file extension from the filename
                image_name = f"{uuid.uuid4()}{ext}"  # Generate a unique filename with the same extension
                with open(image_name, 'wb') as image_file:
                    async for chunk in image_response.content.iter_any():
                        if chunk:  # filter out keep-alive new chunks
                            image_file.write(chunk)
                data.add_field('file', open(image_name, 'rb'), filename=image_name)
        async with self.session.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": self.token},
            data=data
        ) as response:
            response.raise_for_status()
            sent_message = await response.json()
            self.last_message_id[channel_id] = int(sent_message['id'])
            if image_url:
                os.remove(image_name)  # remove the image file after sending

import logging
import json

class UserClientManager:
    def __init__(self, user_id, db, account_index):
        self.user_id = user_id
        self.db = db
        self.account_index = account_index
        self.client = None
        user_data = auto_chat_collection.find_one({"_id": user_id})
        logging.info(f'User data for user {user_id}: {user_data}')  # Add this line
        if user_data and 'configs' in user_data:
            config = user_data['configs'][self.account_index]
            if 'is_running' in config and config['is_running']:
                logging.info(f'Creating AutoBotClient for user {user_id} with config {config}')
                self.client = AutoBotClient(user_id, db, config)

    async def start(self):
        if self.client:
            await self.client.start()

    async def close(self):
        if self.client:
            await self.client.close()
            
@bot.event
async def on_shutdown():
    # Close all AutoBotClient sessions
    for user_state in user_running_states.values():
        if 'AutoBotClient' in user_state:
            await user_state['AutoBotClient'].close()
    await bot.close()

@bot.event
async def on_ready():
    await bot.sync_commands() 
    if bot.user is None:
        print("Bot is not connected to Discord.")
    else:
        print(f'We have logged in as {bot.user}')

    try:
        # Load the user_running_states dictionary from the MongoDB database
        MONGO = MongoClient('mongodb+srv://AutoEconomy:0921229784653120@autoeconomy.uf1wywq.mongodb.net/')
        db = MONGO['AutoEconomy']
        user_states = db['AutoData'].find()
        for state in user_states:
            user_id = str(state['_id'])

            if 'configs' in state:
                for account_index, config in enumerate(state['configs']):
                    if 'is_running' in config and config['is_running']:
                        print(f"Starting auto-reply bot for user {user_id} and account {account_index}")
                        manager = UserClientManager(user_id, db, account_index)
                        print(f"UserClientManager initialized for user {user_id} and account {account_index}")
                        asyncio.create_task(manager.start())  # Start the task without waiting for it to complete
                        print(f"AutoChatter started for user {user_id} and account {account_index}")

    except Exception as e:
        print(f"Error fetching user states: {e}")

    print("Finished processing all users.")

bot.run(TOKEN)
