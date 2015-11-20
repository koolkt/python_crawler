import sys
import os
import time
sys.path.append(os.path.dirname(__file__)+'../app')
import asyncio
from contextlib import contextmanager
import io
import logging
import socket
import unittest
from aiohttp import ClientError, web
import app.crawling as crawling
import app.verify as verify

class TestBaseCrawling(unittest.TestCase):
    # Jesse gratefully copied some of this from asyncio's and aiohttp's tests.

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

        def close_loop():
            self.loop.stop()
            self.loop.run_forever()
            self.loop.close()
        self.addCleanup(close_loop)

        self.port = self._find_unused_port()
        self.app_url = "http://127.0.0.1:{}".format(self.port)
        self.app = self.loop.run_until_complete(self._create_server())
        self.crawler = None

    def _find_unused_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
        s.close()
        return port

    @asyncio.coroutine
    def _create_server(self):
        app = web.Application(loop=self.loop)
        handler_factory = app.make_handler(debug=True)
        srv = yield from self.loop.create_server(
            handler_factory, '127.0.0.1', self.port)

        # Prevent "Task destroyed but it is pending" warnings.
        self.addCleanup(lambda: self.loop.run_until_complete(
            handler_factory.finish_connections()))

        self.addCleanup(srv.close)
        return app

    def add_handler(self, url, handler):
        self.app.router.add_route('GET', url, handler)

    def add_page(self, url='/', links=None, body=None, content_type=None):
        if not body:
            text = ''.join('<a href="{}"></a>'.format(link)
                           for link in links or [])
            body = text.encode('utf-8')

        if content_type is None:
            content_type = 'text/html; charset=utf-8'

        @asyncio.coroutine
        def handler(req):
            yield from req.read()
            return web.Response(body=body, headers=[
                ('CONTENT-TYPE', content_type)])

        self.add_handler(url, handler)
        return self.app_url + url

    def add_redirect(self, url, link):
        @asyncio.coroutine
        def handler(_):
            raise web.HTTPFound(link)

        self.add_handler(url, handler)
        return self.app_url + url

    def assertDoneCount(self, n):
        self.assertEqual(n, len(self.crawler.done),
                         "Expected {} URLs done, got {}".format(
                             n, len(self.crawler.done)))

    def assertStat(self, stat_index=0, **kwargs):
        stat = self.crawler.done[stat_index]
        for name, value in kwargs.items():
            msg = '{}.{} not equal to {!r}'.format(stat, name, value)
            self.assertEqual(getattr(stat, name), value, msg)

    def create_crawler(self, urls=None, *args, **kwargs):
        if self.crawler:
            self.crawler.close()
        if urls is None:
            urls = [self.app_url]
        self.crawler = crawling.Crawler(urls, *args, loop=self.loop, **kwargs)
        self.addCleanup(self.crawler.close)
        #self.loop.run_until_complete(self.crawler.crawl())

    def crawl(self):
        self.loop.run_until_complete(self.crawler.crawl())

    @asyncio.coroutine
    def send_fetch(self, url, crawler):
        web_page,url,content_type,encoding = yield from crawler.fetch(url, 2)
        return web_page

    def test_fetch(self):
        """ Test the fetch function"""
        loop = self.loop
        self.add_page('/hello', body='<!DOCTYPE html><html><body>Hello test</body></html>'.encode('utf-8'))
        self.create_crawler()
        r = loop.run_until_complete(self.send_fetch(self.app_url+'/hello', self.crawler))
        web_page = r
        self.assertTrue(web_page)
        self.assertIn('html', web_page)

    def test_parse_links(self):
        loop = self.loop
        body='<html><body><a href="/foo"></a></body></html>'
        self.create_crawler()
        r = loop.run_until_complete(self.crawler.parse_links(body, self.app_url +'/', 'text/html', 'utf-8'))
        self.assertTrue(r[0], 'http://127.0.0.1:45862/foo')

    def test_link(self):
        # "/" links to foo, which is missing.
        self.add_page('/', ['/foo'])
        self.create_crawler()
        self.crawl()
        self.assertDoneCount(2)
        self.assertStat(url=self.app_url + '/',
                        num_urls=1,
                        num_new_urls=1)
        self.assertStat(1, url=self.app_url + '/foo', status=404)

if __name__ == '__main__':
    unittest.main()
