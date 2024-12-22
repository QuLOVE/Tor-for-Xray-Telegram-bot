## Tor control Telegram Bot

# Overview

## This bot provides control over Tor for a Vless proxy on a VDS. You can manage Tor exit nodes, rotate identities, and enforce restrictions via Telegram commands. Dont forget to set up correct inbound through proxy on VDS.

# Running
## Run using pyenv and screen
`python3 -m venv torenv`

`source torenv/bin/activate`

Also dont forget to setup yor torrc:

`ControlPort 9051`

`HashedControlPassword YOUR_HASHED_PASSWORD`

To generate password you can use
`tor --hash-password YOUR_PASSWORD`

Start is very human so you dont need to be fucking smart as @es3n1n or any HK student with PhD at 16's:

`screen -S cuminme`

`python3 torbot.py`

# Commands

`/start` Initializes the bot

`/auth <password>` Authenticate user to use another commands

`/update` Rotates Tor identify

`/setcountry <code>` Set preferred country for Tor exit nodes (e.g. /setcountry US)

`/reset` Reset preferred country and rotates Tor identity

`/countries` Lists allowed countries for Tor exit nodes

`/help` Shows available commands


## Easter Egg 
EXIST!

## Logs
Yes, bot logs some things in log file...
