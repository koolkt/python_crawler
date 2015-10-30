#!/usr/bin/env python3

from bs4 import BeautifulSoup
import urllib3

#import redis

'''
Main fucntion

'''

request_headers = {
'User-agent':'Mozilla/5.0 (compatible; prixanbot/0.1)'
}

def main(url):
    http = urllib3.PoolManager(timeout=5.0)
    page = http.urlopen('GET', url, headers=request_headers)
    soup = BeautifulSoup(page)
    soup.prettify()
    for link in soup.find_all('a'):
        print(link.get('href'))

main('http://www.antiagression.com')

#r = redis.StrictRedis(host='localhost', port=6379, db=0)
