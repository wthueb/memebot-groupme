import json
import logging
from os import environ
from random import choice
from time import sleep

import praw
import requests
import schedule

from secrets import *


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_meme() -> (praw.models.Submission, bytes):
    logging.info('getting meme image...')

    reddit = praw.Reddit(client_id=REDDIT_CLIENT_ID,
                         client_secret=REDDIT_CLIENT_SECRET,
                         user_agent='memebot-groupme by /u/wilhueb')

    subreddits = [s.strip() for s in open('subs.txt', 'r').readlines()]

    potentials = []

    for s in subreddits:
        logging.info(f'gathering top 3 posts from /r/{s}...')

        try:
            sub = reddit.subreddit(s)

            top3 = sub.top('day', limit=3)

            for post in top3:
                if not post.is_self and not post.is_video and not post.stickied:
                    potentials.append(post)
        except Exception as e:
            logging.error(f'got exception: {e}\nwhile trying to access /r/{s}. may be private/banned. continuing')

            continue

    img = None

    while not img:
        post = choice(potentials)

        try:
            r = requests.get(post.url, allow_redirects=True)
        except Exception as e:
            logging.error(f'got exception: {e}\nwhile trying to access {post.shortlink}, skipping')

            continue

        if r.headers['Content-Type'] not in ('image/gif', 'image/jpeg', 'image/png'):
            continue

        logging.info(f'got post: {post.shortlink}')

        img = r.content

    return post, img


def send_message(post, img) -> None:
    headers = {'x-access-token': GM_ACCESS_TOKEN, 'content-type': 'image/jpeg'}

    try:
        r = requests.post('https://image.groupme.com/pictures', headers=headers, data=img)
    except Exception as e:
        logging.error(f'got exception: {e}\nwhile trying to upload image to groupme, skipping')

        return

    url = r.json()['payload']['url']

    headers = {'content-type': 'application/json'}
    payload = {'bot_id': GM_BOT_ID}

    payload['text'] = f'post from: /r/{post.subreddit}, upvotes: {post.ups}, ' \
                            f'url: {post.shortlink}'

    payload['attachments'] = [{'type': 'image', 'url': url}]

    r = requests.post('https://api.groupme.com/v3/bots/post', headers=headers,
            data=json.dumps(payload))

    logging.info(f'sending message: {payload}')
    logging.info(f'http response: {r.status_code}')


def run() -> None:
    logging.info('running...')
    
    post, img = get_meme()

    send_message(post, img)

def main() -> None:
    if 'DEBUG' in environ and environ['DEBUG']:
        logging.info('DEBUG environment variable set to 1, running')

        run()

    schedule.every().day.at('12:00').do(run)
    
    logging.info('initialized, running loop...')
    
    while True:
        schedule.run_pending()

        sleep(1)

if __name__ == '__main__':
    main()
