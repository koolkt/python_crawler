import sys
import os
import time
import asyncio
from contextlib import contextmanager
import io
import logging
import socket
import unittest
from aiohttp import ClientError, web
sys.path.append(os.path.dirname(__file__)+'../app')
from app.scraper import Scraper
import json

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

def get_file_handle(filename):
    f = open(os.path.dirname(__file__)+'/resources/'+filename, 'r')
    return (f, f.read())

class TestDataExtractor(unittest.TestCase):

    def setUp(self):
        self.pages = {'lenarguile' : get_file_handle('le-narguile.com.json'),
                      'royaledeco' : get_file_handle('royaledeco.com.json'),
                      '10k00nt' : get_file_handle('10k00nt.com.json')}

        data = [(None, value[1].encode()) for key,value in self.pages.items()]
        roots, scrape_data = init_data(data)
        self.s = Scraper(scrape_data)
        
    def tearDown(self):
        for name,f in self.pages.items():
            f[0].close()

    def _assert_data(self, data, price, img_link, name, bc):
        self.assertTrue(data.get('error', True))
        if  hasattr(data['prix_css'], '__iter__'):
            self.assertTrue(price in data['prix_css'])
        else:
            self.assertTrue(price == data['prix_css'])
            
        if  hasattr(data['image_css'], '__iter__'):
            self.assertTrue(img_link in data['image_css'])
        else:
            self.assertTrue(img_link == data['image_css'])

        if  hasattr(data['nom_css'], '__iter__'):
            self.assertTrue(name in data['nom_css'])
        else:
            self.assertTrue(name == data['nom_css'])

        if  hasattr(data['breadcrumb_css'], '__iter__'):
            self.assertTrue(bc in data['breadcrumb_css'])
        else:
            self.assertTrue(bc == data['breadcrumb_css'])

    def test_file_opened(self):
        self.assertTrue(self.pages['lenarguile'][0])

    def test_scrape_no_data_in_html(self):
        html = '<html></html>'
        url = 'www.ex.com'
        for f,data in self.pages.items():
            css_selectors = json.loads(data[1])['selectors']
            data = self.s.scrape(url, html)
            for key,value in data.items():
                self.assertFalse(value)

    def test_scrape_valid_data_in_le_narguile(self):
        f = get_file_handle('le-narguile.html')
        html = f[1]
        f[0].close()
        url = 'http://www.le-narguile.com/media/catalog/product/cache/6/image/'
        data = self.s.scrape(url, html)
        img_link = 'http://www.le-narguile.com/media/catalog/product/cache/6/image/350x350/9df78eab33525d08d6e5fb8d27136e95/p/i/picture_2013_1.jpg'
        price = '99,00\xa0€'
        name = 'Narguilé syrien Star argenté de 79 cm'
        bc = None
        self._assert_data(data, price, img_link, name, bc)
    
    def test_scrape_valid_data_in_royaldeco(self):
        f = get_file_handle('royaledeco.html')
        html = f[1]
        url = 'http://www.royaledeco.com/67686-mainpict/'
        data = self.s.scrape(url, html)
        f[0].close()
        img_link = 'http://www.royaledeco.com/67686-mainpict/fauteuil-galaxy-blanc.jpg'
        price = '129,00 € TTC'
        name = 'Fauteuil Galaxy blanc'
        bc = None
        self._assert_data(data, price, img_link, name, bc)
