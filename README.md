# Twitter-To-Telegram-bot

****
|Author|HoshinoKun|
|---|---
|E-mail|hoshinokun@346pro.club
****

Hello! This projects aims to make a [Telegram](https://telegram.org) bot that forwards [Twitter](https://twitter.com/) updates to people, groups, channels, or whatever Telegram comes up with!

## Credit where credit is due

This is based on former work:
- [telegram-twitter-forwarder-bot](https://github.com/franciscod/telegram-twitter-forwarder-bot)
- [python-telegram-bot](https://github.com/leandrotoledo/python-telegram-bot)
- [tweepy](https://github.com/tweepy/tweepy)
- [peewee](https://github.com/coleifer/peewee)
- also, python, pip, the internets, and so on

So, big thanks to anyone who contributed on these projects! :D

## What it can do
It can retweet tweets sent by your subscribed Twitter users to the telegram.  
You can choose to subscribe to all tweets, to no retweets or replies, or to only media.  
The media will be forwarded to the telegram as images, including jpeg and gif formats.
### TODO
forward the video from tweets

## How do I run this?

1. clone this thing
2. copy `example-secrets.py` to `secrets.py` and fill it
3. `pip install -r requirements.txt`
4. run it! `python main.py`

## secrets.py?? what is that?

This bot requires a few tokens that identify it both on Twitter and Telegram. This configuration should be present on the `secrets.py` file.

There's a skeleton of that on `example-secrets.py`, start by copying it to `secrets.py`. The second one is the one you should change.

First, you'll need a Telegram Bot Token, you can get it via BotFather ([more info here](https://core.telegram.org/bots)).

Also, setting this up will need an Application-only authentication token from Twitter ([more info here](https://dev.twitter.com/oauth/application-only)). Optionally, you can provide a user access token and secret.

You can get this by creating a Twitter App [here](https://apps.twitter.com/).

Bear in mind that if you don't have added a mobile phone to your Twitter account you'll get this:

>You must add your mobile phone to your Twitter profile before creating an application. Please read https://support.twitter.com/articles/110250-adding-your-mobile-number-to-your-account-via-web for more information.

Get a consumer key, consumer secret, access token and access token secret (the latter two are optional), fill in your `secrets.py`, and then run the bot!