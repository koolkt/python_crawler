import asyncio
import cgi
from collections import namedtuple
import logging
import re
import time
import urllib.parse
from bs4 import BeautifulSoup
import aiohttp
from asyncio import Queue
from pyquery import PyQuery as pq
import asyncio_redis
import json
import app.verify as verify

LOGGER = logging.getLogger(__name__)

def lenient_host(host):
    parts = host.split('.')[-2:]
    return ''.join(parts)

FetchStatistic = namedtuple('FetchStatistic',
                            ['url',
                             'next_url',
                             'status',
                             'exception',
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
    return _url, _content_type, _encoding

class Crawler(object):
    """Crawl a set of URLs.

    This manages two sets of URLs: 'urls' and 'done'.  'urls' is a set of
    URLs seen, and 'done' is a list of FetchStatistics.
    """
    def __init__(self, roots,
                 css_selectors=None,
                 exclude=None, strict=True,  # What to crawl.
                 max_redirect=10, max_tries=4,  # Per-url limits.
                 max_tasks=5, *, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.roots = roots
        #self.seed = [clean(r) for r in roots][0] # For now we only accept one root
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
        self.css_selectors = css_selectors
        self.redis_queue = None
        for root in roots:
            parts = urllib.parse.urlparse(root)
            host, port = urllib.parse.splitport(parts.netloc)
            if not host:
                continue
            if re.match(r'\A[\d\.]*\Z', host):
                self.root_domains.add(host)
                self.seed = host
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
                                         next_url=None,
                                         status=None,
                                         exception=exception,
                                         content_type=None,
                                         encoding=None,
                                         num_urls=0,
                                         num_new_urls=0)
        self.done.append(fetch_statistic)

    def close(self):
        """Close resources."""
        LOGGER.debug("closing resources")
        #yield from self.q.join()
        #data = json.dumps(self.q)
        #yield from self.redis_queue.set(self.seed+':saved_todo_urls', data)
        if (self.redis_queue):
            self.redis_queue.close()
        self.session.close()
        #self.q.task_done()

    @asyncio.coroutine
    def parse_links(self, web_page_html, _url, _content_type, _encoding):
        """Return a FetchStatistic and list of links."""
        links = set()
        pquery = pq(web_page_html)
        urls = set([a.attrib['href'] for a in pquery('a') 
                    if a.attrib.get('href', None)])
        for url in urls:
            normalized = urllib.parse.urljoin(_url, url)
            defragmented, frag = urllib.parse.urldefrag(normalized)
            if verify.url_allowed(defragmented,self.root_domains):
                links.add(defragmented)
        if urls:
            LOGGER.info('got %r distinct urls from %r total: %i new links: %i visited: %i',
                        len(urls), _url, len(links),
                        len(links - self.seen_urls), len(self.seen_urls))
        new_links = [(link, self.max_redirect) 
                     for link in links.difference(self.seen_urls)]

        self.record_statistic(
            url=_url,
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
    def fetch(self, url, max_redirect):
        """Fetch one URL."""
        tries = 0
        web_page = None
        exception = None
        _url = None
        _encoding = None
        _content_type = None
        while tries < self.max_tries:
            try:
                response = yield from self.session.get(
                    url, allow_redirects=False)
                if tries > 1:
                    LOGGER.debug('try %r for %r success', tries, url)
                break
            except aiohttp.ClientError as client_error:
                LOGGER.error('try %r for %r raised %r', tries, url, client_error)
                exception = client_error
            tries += 1
        else:
            # We never broke out of the loop: all tries failed.
            LOGGER.error('%r failed after %r tries',
                         url, self.max_tries)
            self.record_statistic(url=url, exception=exception)
            return
        try:
            _url, _content_type, encoding = get_content_type_and_encoding(response)
            if is_redirect(response):
                self.handle_redirect(response, url, max_redirect)
                web_page = 'redirect'
            elif response.status == 200 and _content_type in ('text/html', 'application/xml'):
                web_page = yield from response.text()
        except Exception as e:
            print(e)
        finally:
            yield from response.release()
            return (web_page, _url, _content_type, _encoding)

    @asyncio.coroutine
    def work(self):
        """Process queue items forever."""
        try:
            while True:
                url, max_redirect = yield from self.q.get()
                assert url in self.seen_urls
                web_page,url,content_type,encoding = yield from self.fetch(url, max_redirect)
                if web_page and web_page != 'redirect':
                    new_links = yield from self.parse_links(web_page,url,content_type,encoding)
                    add_urls(new_links)
                self.q.task_done()
        except asyncio.CancelledError:
            pass

    def add_urls(self, urls, max_redirect=None):
        """Add a URL to the queue if not seen before."""
        if max_redirect is None:
            max_redirect = self.max_redirect
        if not isinstance(urls, str):
            for link in urls.difference(self.seen_urls):
                self.q.put_nowait((link, max_redirect))
            self.seen_urls.update(links)
        elif urls not in self.seen_urls: 
            self.q.put_nowait((urls, max_redirect))
            self.seen_urls.add(urls)

    @asyncio.coroutine
    def crawl(self):
        """Run the crawler until all finished."""
        self.redis_queue = yield from asyncio_redis.Connection.create(
            host='localhost', port=6379, loop=self.loop)
        LOGGER.info('Starting crawl...')
        workers = [asyncio.Task(self.work(), loop=self.loop)
                   for _ in range(self.max_tasks)]
        self.t0 = time.time()
        yield from self.q.join()
        self.t1 = time.time()
        for w in workers:
            w.cancel()
