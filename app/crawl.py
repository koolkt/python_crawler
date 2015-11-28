#!/usr/bin/env python3.4

"""A simple web crawler -- main driver program."""

# TODO:
# - Add arguments to specify TLS settings (e.g. cert/key files).

import argparse
import asyncio
import logging
import sys
import redis
import crawling
import reporting
import json
import functools
from scraper import Scraper

ARGS = argparse.ArgumentParser(description="Web crawler")
ARGS.add_argument(
    '--iocp', action='store_true', dest='iocp',
    default=False, help='Use IOCP event loop (Windows only)')
ARGS.add_argument(
    '--select', action='store_true', dest='select',
    default=False, help='Use Select event loop instead of default')
ARGS.add_argument(
    'roots', nargs='*',
    default=[], help='Root URL (may be repeated)')
ARGS.add_argument(
    '--max_redirect', action='store', type=int, metavar='N',
    default=10, help='Limit redirection chains (for 301, 302 etc.)')
ARGS.add_argument(
    '--max_tries', action='store', type=int, metavar='N',
    default=4, help='Limit retries on network errors')
ARGS.add_argument(
    '--max_tasks', action='store', type=int, metavar='N',
    default=100, help='Limit concurrent connections')
ARGS.add_argument(
    '--exclude', action='store', metavar='REGEX',
    help='Exclude matching URLs')
ARGS.add_argument(
    '--strict', action='store_true',
    default=True, help='Strict host matching (default)')
ARGS.add_argument(
    '--lenient', action='store_false', dest='strict',
    default=False, help='Lenient host matching')
ARGS.add_argument(
    '-v', '--verbose', action='count', dest='level',
    default=2, help='Verbose logging (repeat for more verbose)')
ARGS.add_argument(
    '-q', '--quiet', action='store_const', const=0, dest='level',
    default=2, help='Only log errors')

def fix_url(url):
    """Prefix a schema-less URL with http://."""
    if '://' not in url:
        url = 'http://' + url
    return url

def init_data(data_list):
    roots = set()
    scrape_data = {}
    json_data_list = map(lambda d: json.loads(d[1].decode('utf-8')), data_list)
    for d in json_data_list:
        url = fix_url(d['url'])
        roots.add(url)
        scrape_data.update({url:d['selectors']})
    return (roots, scrape_data)

def main():
    """Main program.

    Parse arguments, set up event loop, run crawler, print report.
    """
    args = ARGS.parse_args()
    levels = [logging.ERROR, logging.WARN, logging.INFO, logging.DEBUG]
    logging.basicConfig(level=levels[min(args.level, len(levels)-1)])

    if args.iocp:
        from asyncio.windows_events import ProactorEventLoop
        loop = ProactorEventLoop()
        asyncio.set_event_loop(loop)
    elif args.select:
        loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    if not args.roots:
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        data = [r.blpop('queue:urls_to_crawl')]
        # data.append(r.blpop('queue:urls_to_crawl'))
        # data.append(r.blpop('queue:urls_to_crawl'))
        roots, scrape_data = init_data(data)
        s = None#Scraper(scrape_data)
    else:
        roots = {fix_url(root) for root in args.roots}
        s = None

    crawler = crawling.Crawler(roots,
                               scraper=s,
                               data_handler=None,
                               exclude=args.exclude,
                               strict=args.strict,
                               max_redirect=args.max_redirect,
                               max_tries=args.max_tries,
                               max_tasks=args.max_tasks)
    try:
        loop.run_until_complete(crawler.crawl())  # Crawler gonna crawl.
    except KeyboardInterrupt:
        sys.stderr.flush()
        print('\nInterrupted\n')
    finally:
        reporting.report(crawler) ########## REPORTING
        crawler.close()

        # next two lines are required for actual aiohttp resource cleanup
        loop.stop()
        loop.run_forever()

        loop.close()


if __name__ == '__main__':
    main()
