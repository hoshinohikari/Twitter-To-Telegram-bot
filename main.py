import logging
import math

import tweepy
from telegram.ext import CommandHandler
from telegram.ext import Updater
from telegram.ext.messagehandler import MessageHandler, Filters

from bot import TwitterForwarderBot
from commands import *
from job import FetchAndSendTweetsJob
from models import TwitterUser

try:
    from secrets import env
except ImportError:
    print("""
    CONFIGURATION ERROR: missing secrets.py!

    Make sure you have copied secrets.example.py into secrets.py and completed it!
    See README.md for extra info.
""")
    exit(42)


if __name__ == '__main__':

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.WARNING)

    logging.getLogger(TwitterForwarderBot.__name__).setLevel(logging.INFO)
    logging.getLogger(FetchAndSendTweetsJob.__name__).setLevel(logging.INFO)

    # initialize Twitter API
    try:
        auth = tweepy.AppAuthHandler(env['TWITTER_CONSUMER_KEY'], env['TWITTER_CONSUMER_SECRET'])
    except KeyError as exc:
        var = exc.args[0]
        print("use OAuth 2 failed")
        print(("The required configuration variable {} is missing. "
              "Please review secrets.py.").format(var))
        try:
            auth = tweepy.OAuthHandler(env['TWITTER_CONSUMER_KEY'], env['TWITTER_CONSUMER_SECRET'])
        except KeyError as exc:
            var = exc.args[0]
            print(("The required configuration variable {} is missing. "
                   "Please review secrets.py.").format(var))
            exit(123)

        try:
            auth.set_access_token(env['TWITTER_ACCESS_TOKEN'], env['TWITTER_ACCESS_TOKEN_SECRET'])
        except KeyError as exc:
            var = exc.args[0]
            print(("The optional configuration variable {} is missing. "
                   "Tweepy will be initialized in 'app-only' mode.").format(var))

    twapi = tweepy.API(auth, wait_on_rate_limit=True)

    # initialize telegram API
    token = env['TELEGRAM_BOT_TOKEN']
    bot = TwitterForwarderBot(token, twapi)
    updater = Updater(bot=bot)
    dispatcher = updater.dispatcher

    # set commands
    dispatcher.add_handler(CommandHandler('start', cmd_start))
    dispatcher.add_handler(CommandHandler('help', cmd_help))
    dispatcher.add_handler(CommandHandler('ping', cmd_ping))
    dispatcher.add_handler(CommandHandler('sub', cmd_sub, pass_args=True))
    dispatcher.add_handler(CommandHandler('mediasub', cmd_mediasub, pass_args=True))
    dispatcher.add_handler(CommandHandler('sub_no_rt', cmd_sub_no_rt, pass_args=True))
    dispatcher.add_handler(CommandHandler('sub_no_reply', cmd_sub_no_reply, pass_args=True))
    dispatcher.add_handler(CommandHandler('unsub', cmd_unsub, pass_args=True))
    dispatcher.add_handler(CommandHandler('list', cmd_list))
    dispatcher.add_handler(CommandHandler('export', cmd_export))
    dispatcher.add_handler(CommandHandler('all', cmd_all))
    dispatcher.add_handler(CommandHandler('wipe', cmd_wipe))
    dispatcher.add_handler(CommandHandler('source', cmd_source))
    dispatcher.add_handler(CommandHandler('auth', cmd_get_auth_url))
    dispatcher.add_handler(CommandHandler('verify', cmd_verify, pass_args=True))
    dispatcher.add_handler(CommandHandler('export_friends', cmd_export_friends))
    dispatcher.add_handler(CommandHandler('export_followers', cmd_export_followers))
    dispatcher.add_handler(CommandHandler('set_timezone', cmd_set_timezone, pass_args=True))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_chat))

    # Twitter API rate limit parameters
    LIMIT_WINDOW = 15 * 60
    LIMIT_COUNT = 900
    MIN_INTERVAL = 30
    TWEET_BATCH_INSERT_COUNT = 100
    tw_count = (TwitterUser.select()
                .join(Subscription)
                .group_by(TwitterUser)
                .count())
    res = math.ceil(tw_count * LIMIT_WINDOW / LIMIT_COUNT)
    res_max = max(MIN_INTERVAL, res)

    # put job
    queue = updater.job_queue
    #queue.put(FetchAndSendTweetsJob(), next_t=0)
    #queue.run_once(FetchAndSendTweetsJob, 2)
    queue.run_repeating(FetchAndSendTweetsJob, interval=res_max, first=1)

    # poll
    updater.start_polling()

    updater.idle()
