import os
import time
import subprocess

# Change the working directory to the directory where this script is located
os.chdir(os.path.dirname(os.path.abspath(__file__)))

bot_process = None

while True:
    if bot_process is not None:
        # If the bot is running, stop it
        bot_process.terminate()
        bot_process.wait()

        # Wait for a few seconds to give the bot time to fully shut down
        time.sleep(60)  # Increase the delay to 60 seconds

    print("Starting AutoBot.py...")
    
    # Start the bot script as a subprocess
    bot_process = subprocess.Popen(["python3", "AutoChatter.py"])
    
    # Wait for 1 minute
    time.sleep(100)

    print("Restarting AutoBot.py...")
