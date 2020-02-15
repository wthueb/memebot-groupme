import json
import logging
import logging.config
from os import environ
from random import choice
import sys
from time import sleep

import praw
import requests
import schedule

import config

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'brief': {
            'format': '%(asctime)s: %(message)s'
        },

        'precise': {
            'format': '%(asctime)s %(name)-10s %(levelname)-7s %(message)s'
        }
    },

    'handlers': {
        'stdout': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
            'level': 'INFO',
            'formatter': 'brief'
        },

        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'log/memebot.log',
            'maxBytes': 2*1024*1024, # 2 MiB
            'backupCount': 10,
            'level': 'DEBUG',
            'formatter': 'precise'
        }
    },

    'root': {
        'level': 'DEBUG',
        'handlers': ['stdout', 'file']
    }
})

logger = logging.getLogger('memebot')

NUM_POSTS_PER_SUBREDDIT = 3
NUM_MEMES = 1


def get_memes() -> list:
    logger.info('getting meme images...')

    reddit = praw.Reddit(client_id=config.REDDIT_CLIENT_ID,
                         client_secret=config.REDDIT_CLIENT_SECRET,
                         user_agent='memebot-groupme by /u/wilhueb')

    subreddits = [s.strip() for s in open('subs.txt', 'r').readlines()]

    potentials = []

    for s in subreddits:
        logger.info(f'getting top {NUM_POSTS_PER_SUBREDDIT} posts from /r/{s}...')

        try:
            sub = reddit.subreddit(s)

            count = 0

            for post in sub.top('day', limit=20):
                if not post.is_self and not post.is_video and not post.stickied:
                    potentials.append(post)

                    count += 1

                    if count >= NUM_POSTS_PER_SUBREDDIT:
                        continue
        except Exception as e:
            logger.error((f'got exception: {e}\n'
                           f'while trying to access /r/{s}. may be private/banned. continuing'))

            continue

    memes = []

    while len(memes) < NUM_MEMES:
        post = choice(potentials)

        try:
            r = requests.get(post.url, allow_redirects=True)
        except Exception as e:
            logger.error((f'got exception: {e}\n'
                           f'while trying to access {post.shortlink}, skipping'))

            continue

        if r.headers['Content-Type'] not in ('image/gif', 'image/jpeg', 'image/png'):
            continue

        logger.info(f'got meme: {post.shortlink} from /r/{post.subreddit}')

        memes.append(r.content)

    return memes


def send_message(memes) -> None:
    headers = {'x-access-token': config.GM_ACCESS_TOKEN, 'content-type': 'image/jpeg'}

    urls = []

    for img in memes:
        try:
            r = requests.post('https://image.groupme.com/pictures', headers=headers, data=img)
        except Exception as e:
            logger.error((f'got exception: {e}\n'
                           f'while trying to upload image to groupme, skipping'))

            return

        urls.append(r.json()['payload']['url'])

    headers = {'content-type': 'application/json'}
    payload = {'bot_id': config.GM_BOT_ID}

    payload['text'] = 'meme of the day'

    payload['attachments'] = [{'type': 'image', 'url': url} for url in urls]

    r = requests.post('https://api.groupme.com/v3/bots/post', headers=headers,
                      data=json.dumps(payload))

    logger.info(f'sending message: {payload}')
    logger.info(f'http status: {r.status_code}')

    if r.status_code < 200 or r.status_code > 299:
        logger.error(f'reponse: {r.text}')


def run() -> None:
    logger.info('running...')
    
    memes = get_memes()

    send_message(memes)


def main() -> None:
    if 'DEBUG' in environ and environ['DEBUG']:
        logger.info('DEBUG environment variable set to 1, running')

        run()

        exit()

    schedule.every().day.at('12:00').do(run)
    
    logger.info('initialized, running loop...')
    
    while True:
        schedule.run_pending()

        sleep(1)

if __name__ == '__main__':
    main()
