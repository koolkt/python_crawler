#!/usr/bin/env python3

from bs4 import BeautifulSoup
import urllib3

'''
Main fucntion

'''
def main(url):
    http = urllib3.PoolManager(timeout=5.0)
    page = http.urlopen('GET', url)
    soup = BeautifulSoup(page)
    soup.prettify()
    for link in soup.find_all('a'):
        print(link.get('href'))

main('http://prixan.com/')
