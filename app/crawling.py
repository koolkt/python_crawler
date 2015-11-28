import asyncio
import cgi
from collections import namedtuple
import logging
import re
import time
import urllib.parse
import aiohttp
from asyncio import Queue
import asyncio_redis
import json
import sys
import os
sys.path.append(os.path.dirname(__file__)+'../app')
try:
    import app.verify as verify
except:
    import verify
from lxml import html

LOGGER = logging.getLogger(__name__)

def lenient_host(host):
    parts = host.split('.')[-2:]
    return ''.join(parts)

FetchStatistic = namedtuple('FetchStatistic',
                            ['url',
                             'next_url',
                             'status',
                             'exception',
                             'size',
                             'content_type',
                             'encoding',
                             'num_urls',
                             'num_new_urls'])

def is_redirect(response):
    return response.status in (300, 301, 302, 303, 307)

def get_content_type_and_encoding(response):
    _content_type = None
    _url = response.url
    _content_type = response.headers.get('content-type')
    pdict = {}
    if _content_type:
        _content_type, pdict = cgi.parse_header(_content_type)
    _encoding = pdict.get('charset', 'utf-8')
    return (_url, _content_type, _encoding)

class Crawler(object):
    """Crawl a set of URLs.

    This manages two sets of URLs: 'urls' and 'done'.  'urls' is a set of
    URLs seen, and 'done' is a list of FetchStatistics.
    """
    def __init__(self, roots, scraper= None, data_handler=None,
                 exclude=None, strict=True,  # What to crawl.
                 max_redirect=5, max_tries=10,  # Per-url limits.
                 max_tasks=10, max_connections_per_host=3,*, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.roots = roots
        self.max_connections_per_host = max_connections_per_host
        self.scraper = scraper
        self.data_handler = data_handler
        self.exclude = exclude
        self.strict = strict
        self.max_redirect = max_redirect
        self.max_tries = max_tries
        self.max_tasks = max_tasks
        self.q = Queue(loop=self.loop)
        self.seen_urls = set()
        self.done = []
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.root_domains = set()
        for root in roots:
            parts = urllib.parse.urlparse(root)
            host, port = urllib.parse.splitport(parts.netloc)
            if not host:
                continue
            if re.match(r'\A[\d\.]*\Z', host):
                self.root_domains.add(host)
            else:
                host = host.lower()
                if self.strict:
                    self.root_domains.add(host)
                else:
                    self.root_domains.add(lenient_host(host))
        for root in roots:
            self.add_urls(root)
        self.t0 = time.time()
        self.t1 = None

    def record_statistic(self, url=None,
                         next_url=None,
                         status=None,
                         exception=None,
                         content_type=None,
                         encoding=None,
                         num_urls=0,
                         num_new_urls=0):
        """Record the FetchStatistic for completed / failed URL."""
        fetch_statistic = FetchStatistic(url=url,
                                         next_url=next_url,
                                         status=status,
                                         size=0,
                                         exception=exception,
                                         content_type=content_type,
                                         encoding=encoding,
                                         num_urls=num_urls,
                                         num_new_urls=num_new_urls)
        self.done.append(fetch_statistic)

    
    def extract_data(self,root_url, html):
        raise NotImplementedError('You need to define a extract_data method!')

    def close(self):
        """Close resources."""
        LOGGER.debug("closing resources")
        self.session.close()

    @asyncio.coroutine
    def parse_links(self, web_page_html, base_url, _content_type, _encoding):
        """Return a list of links."""
        links = set()
        tree = html.fromstring(web_page_html)
        tree.make_links_absolute(base_url)
        urls = [link[2] for link in tree.iterlinks()]
        for url in urls:
            defragmented, frag = urllib.parse.urldefrag(url)
            if verify.url_allowed(defragmented,self.root_domains,exclude=self.exclude): # Select Valid links, testing against regexp and root_domains
                links.add(defragmented)
        if urls:
            LOGGER.info('got %r urls from %r new links: %i visited: %i',
                        len(urls), base_url,
                        len(links - self.seen_urls), len(self.seen_urls))
        new_links = [link for link in links.difference(self.seen_urls)]

        self.record_statistic(
            url=base_url,
            content_type=_content_type,
            encoding=_encoding,
            num_urls=len(links),
            num_new_urls=len(links - self.seen_urls))
        return new_links

    def handle_redirect(self, response, url, max_redirect):
        location = response.headers['location']
        next_url = urllib.parse.urljoin(url, location)
        self.record_statistic(url=url,
                              next_url=next_url,
                              status=response.status)
        if next_url in self.seen_urls:
            return
        if max_redirect > 0:
            LOGGER.info('redirect to %r from %r max_redir: %i', 
                        next_url, url, max_redirect - 1)
            self.add_urls(next_url, max_redirect - 1)
        else:
            LOGGER.error('redirect limit reached for %r from %r',
                         next_url, url)
        return

    @asyncio.coroutine
    def fetch(self, url, max_redirect, sem):
        """Fetch one URL."""
        tries = 0
        web_page = None
        exception = None
        _url = None
        _encoding = None
        _content_type = None
        sleep_time = 0
        while tries < self.max_tries:
            try:
                with (yield from sem):
                    response = yield from asyncio.wait_for(
                        self.session.get(url, allow_redirects=False), 10,loop=self.loop)
                if tries > 1:
                    LOGGER.debug('try %r for %r success', tries, url)
                break
            except Exception as client_error:
                sleep_time += 5
                yield from asyncio.sleep(sleep_time)
                LOGGER.error('try %r for %r raised %r', tries, url, client_error)
                exception = client_error
            tries += 1
        else:
            # We never broke out of the loop: all tries failed.
            LOGGER.error('%r failed after %r tries',
                         url, self.max_tries)
            self.record_statistic(url=url, exception=exception)
            return (web_page, _url, _content_type, _encoding)
        try:
            _url, _content_type, _encoding = get_content_type_and_encoding(response)
            if is_redirect(response):
                self.handle_redirect(response, url, max_redirect)
                web_page = 'redirect'
            elif response.status == 200 and _content_type in ('text/html', 'application/xml'):
                web_page = yield from response.text()
            else:
                self.record_statistic(url=response.url, status=response.status, 
                                      content_type=_content_type, encoding=_encoding)
        except Exception as e:
            print('*******error**********')
        finally:
            yield from response.release()
        return (web_page, _url, _content_type, _encoding)

    def add_urls(self, urls, max_redirect=None):
        """Add a URL to the queue if not seen before."""
        if max_redirect is None:
            max_redirect = self.max_redirect
        if not isinstance(urls, str):
            urls = set(urls)
            for link in urls.difference(self.seen_urls):
                self.q.put_nowait((link, max_redirect))
            self.seen_urls.update(urls)
        elif urls not in self.seen_urls: 
            self.q.put_nowait((urls, max_redirect))
            self.seen_urls.add(urls)

    @asyncio.coroutine
    def work(self,sem):
        """Process queue items forever."""
        try:
            while True:
                url, max_redirect = yield from self.q.get()
                #assert url in self.seen_urls
                web_page,url,content_type,encoding = yield from self.fetch(url, max_redirect, sem)
                if web_page and web_page != 'redirect':
                    new_links = yield from self.parse_links(web_page,url,content_type,encoding)
                    if self.scraper:
                        data = self.scraper.scrape(url,web_page)
                    if self.data_handler:
                        self.data_handler.handle(data)
                    self.add_urls(new_links)
                self.q.task_done()
        except (asyncio.CancelledError,):
            print('error')

    @asyncio.coroutine
    def crawl(self):
        sem = asyncio.Semaphore(value=self.max_connections_per_host,loop=self.loop)
        """Run the crawler until all finished."""
        LOGGER.info('Starting crawl...')
        workers = [asyncio.Task(self.work(sem), loop=self.loop)
                   for _ in range(self.max_tasks)]
        self.t0 = time.time()
        yield from self.q.join()
        self.t1 = time.time()
        for w in workers:
            w.cancel()
