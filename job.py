import html
import logging
import math
import re
from datetime import datetime
from threading import Event

import tweepy
from telegram.error import TelegramError
from telegram.ext import Job, CallbackContext

from models import TwitterUser, Tweet, Subscription, db, TelegramChat

INFO_CLEANUP = {
    'NOTFOUND': "Your subscription to @{} was removed because that profile doesn't exist anymore. Maybe the account's name changed?",
    'PROTECTED': "Your subscription to @{} was removed because that profile is protected and can't be fetched.",
}

def FetchAndSendTweetsJob(context_in: CallbackContext) -> None:
    job = context_in.job
    bot = context_in.bot
    job.repeat = True
    job.context = None
    job.name = "FetchAndSendTweetsJob"
    job._remove = Event()
    job._enabled = Event()
    job._enabled.set()
    job.logger = logging.getLogger(job.name)
    job.logger.debug("Fetching tweets...")
    tweet_rows = []
    # fetch the tw users' tweets
    tw_users = list((TwitterUser.select()
                        .join(Subscription)
                        .group_by(TwitterUser)
                        .order_by(TwitterUser.last_fetched)))
    updated_tw_users = []
    users_to_cleanup = []

    for tw_user in tw_users:
        try:
            if tw_user.last_tweet_id == 0:
                # get just the latest tweet
                job.logger.debug(
                    "Fetching latest tweet by {}".format(tw_user.screen_name))
                tweets = bot.tw.user_timeline(
                    screen_name=tw_user.screen_name,
                    count=1,
                    tweet_mode='extended')
            else:
                # get the fresh tweets
                job.logger.debug(
                    "Fetching new tweets from {}".format(tw_user.screen_name))
                tweets = bot.tw.user_timeline(
                    screen_name=tw_user.screen_name,
                    since_id=tw_user.last_tweet_id,
                    tweet_mode='extended')
            updated_tw_users.append(tw_user)
        except tweepy.error.TweepError as e:
            sc = e.response.status_code
            if sc == 429:
                job.logger.debug("- Hit ratelimit, breaking.")
                break

            if sc == 401:
                users_to_cleanup.append((tw_user, 'PROTECTED'))
                job.logger.debug("- Protected tweets here. Cleaning up this user")
                continue

            if sc == 404:
                users_to_cleanup.append((tw_user, 'NOTFOUND'))
                job.logger.debug("- 404? Maybe screen name changed? Cleaning up this user")
                continue

            job.logger.debug(
                "- Unknown exception, Status code {}".format(sc))
            continue

        for tweet in tweets:
            job.logger.debug("- Got tweet: {}".format(tweet.full_text))

            # Check if tweet contains media, else check if it contains a link to an image
            extensions = ('.jpg', '.jpeg', '.png', '.gif')
            pattern = '[(%s)]$' % ')('.join(extensions)
            photo_url = []
            tweet_text = html.unescape(tweet.full_text)
            if 'media' in tweet.entities:
                for imgs in tweet.extended_entities['media']:
                    photo_url.append(imgs['media_url_https'])
                #photo_url = tweet.entities['media'][0]['media_url_https']
            else:
                for url_entity in tweet.entities['urls']:
                    expanded_url = url_entity['expanded_url']
                    if re.search(pattern, expanded_url):
                        photo_url.append(expanded_url)
                        break
            if len(photo_url) != 0:
                job.logger.debug("- - Found media URL in tweet: " + photo_url[0])

            for url_entity in tweet.entities['urls']:
                expanded_url = url_entity['expanded_url']
                indices = url_entity['indices']
                display_url = tweet.full_text[indices[0]:indices[1]]
                tweet_text = tweet_text.replace(display_url, expanded_url)

            tw_data = {
                'tw_id': tweet.id,
                'text': tweet_text,
                'created_at': tweet.created_at,
                'twitter_user': tw_user,
                'photo_url': photo_url,
            }
            try:
                t = Tweet.get(Tweet.tw_id == tweet.id)
                job.logger.warning("Got duplicated tw_id on this tweet:")
                job.logger.warning(str(tw_data))
            except Tweet.DoesNotExist:
                tweet_rows.append(tw_data)

            if len(tweet_rows) >= 100:
                Tweet.insert_many(tweet_rows).execute()
                tweet_rows = []

    TwitterUser.update(last_fetched=datetime.now()) \
        .where(TwitterUser.id << [tw.id for tw in updated_tw_users]).execute()

    if not updated_tw_users:
        return

    if tweet_rows:
        Tweet.insert_many(tweet_rows).execute()

    # send the new tweets to subscribers
    subscriptions = list(Subscription.select()
                            .where(Subscription.tw_user << updated_tw_users))
    for s in subscriptions:
        # are there new tweets? send em all!
        job.logger.debug(
            "Checking subscription {} {}".format(s.tg_chat.chat_id, s.tw_user.screen_name))

        if s.last_tweet_id == 0:  # didn't receive any tweet yet
            try:
                tw = s.tw_user.tweets.select() \
                    .order_by(Tweet.tw_id.desc()) \
                    .first()
                if tw is None:
                    job.logger.warning("Something fishy is going on here...")
                else:
                    bot.send_tweet(s.tg_chat, tw, s.sub_kind)
                    # save the latest tweet sent on this subscription
                    s.last_tweet_id = tw.tw_id
                    s.save()
            except IndexError:
                job.logger.debug("- No tweets available yet on {}".format(s.tw_user.screen_name))

            continue

        if s.tw_user.last_tweet_id > s.last_tweet_id:
            job.logger.debug("- Some fresh tweets here!")
            for tw in (s.tw_user.tweets.select()
                                .where(Tweet.tw_id > s.last_tweet_id)
                                .order_by(Tweet.tw_id.asc())
                        ):
                bot.send_tweet(s.tg_chat, tw, s.sub_kind)

            # save the latest tweet sent on this subscription
            s.last_tweet_id = s.tw_user.last_tweet_id
            s.save()
            continue

        job.logger.debug("- No new tweets here.")


    job.logger.debug("Starting tw_user cleanup")
    if not users_to_cleanup:
        job.logger.debug("- Nothing to cleanup")
    else:
        for tw_user, reason in users_to_cleanup:
            job.logger.debug("- Cleaning up subs on user @{}, {}".format(tw_user.screen_name, reason))
            message = INFO_CLEANUP[reason].format(tw_user.screen_name)
            subs = list(tw_user.subscriptions)
            for s in subs:
                chat = s.tg_chat
                if chat.delete_soon:
                    job.logger.debug ("- - skipping because of delete_soon chatid={}".format(chat_id))
                    continue
                chat_id = chat.chat_id
                job.logger.debug ("- - bye on chatid={}".format(chat_id))
                s.delete_instance()

                try:
                    bot.sendMessage(chat_id=chat_id, text=message)
                except TelegramError as e:
                    job.logger.info("Couldn't send unsubscription notice of {} to chat {}: {}".format(
                        tw_user.screen_name, chat_id, e.message
                    ))

                    delet_this = None

                    if e.message == 'Bad Request: group chat was migrated to a supergroup chat':
                        delet_this = True

                    if e.message == "Unauthorized":
                        delet_this = True

                    if delet_this:
                        job.logger.info("Marking chat for deletion")
                        chat.delete_soon = True
                        chat.save()

        job.logger.debug("- Cleaning up TwitterUser @{}".format(tw_user.screen_name, reason))
        tw_user.delete_instance()

        job.logger.debug ("- Cleanup finished")

    job.logger.debug("Cleaning up TelegramChats marked for deletion")
    for chat in TelegramChat.select().where(TelegramChat.delete_soon == True):
        chat.delete_instance(recursive=True)
        job.logger.debug("Deleting chat {}".format(chat.chat_id))
