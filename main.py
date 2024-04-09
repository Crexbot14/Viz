import subprocess
import time
import os
from flask import Flask, render_template
from threading import Thread

app = Flask(__name__)


@app.route('/')
def index():
    return '''<body style="margin: 0; padding: 0;">
    <iframe width="100%" height="100%" src="https://axocoder.vercel.app/" frameborder="0" allowfullscreen></iframe>
  </body>'''


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


keep_alive()
print("Server Running Because of Axo")

# Change the working directory to the directory where this script is located
os.chdir(os.path.dirname(os.path.abspath(__file__)))

bot_process = None

while True:
    if bot_process is not None:
        # If the bot is running, stop it
        bot_process.terminate()
        bot_process.wait()

        # Wait for a few seconds to give the bot time to fully shut down
        time.sleep(15)  # Increase the delay to 60 seconds

    print("Starting ReplyBot.py...")

    # Start the bot script as a subprocess
    bot_process = subprocess.Popen(["python3", "AutoChatter.py"])

    # Wait for 1 minute
    time.sleep(60 * 6 * 30)

    print("Restarting ReplyBot.py...")
