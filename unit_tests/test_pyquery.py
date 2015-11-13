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
import requests
import redis
import json

product_url = 'http://www.10k00nt.com/blague-a-tabac/1861-blague-a-tabac-en-cuir-facon-python.html'

def search_selectors(selectors, d):
    return d(selectors)

def get_data(text, css_selectors):
    data = []
    print("getting data...")
    for rule in css_selectors:
        for key, value in rule.items():
            d = pq(text)
            print(value[0].split()[0].strip(),value[0].strip().replace('  ', ' ').replace(' ', '>'))
            info = d(value[0])#self.search_selectors(value,d)
            if (key != 'image_css'):
                info  = [a.text() for a in info.items()]
            else:
                info  = [a.attr['src'] for a in info.items()]
            print("FOUND: %s" % (info))
            data.append({key : info})
    print(data)
    exit()
    return data
                

def main():
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    data = r.blpop('queue:test')
    data = json.loads(data[1].decode('utf-8'))
    url = data['url']
    selectors = data['selectors']
    r = requests.get(url)
    get_data(r.text, selectors)

if __name__ == '__main__':
    main()
