#!/usr/bin/env python3

from bs4 import BeautifulSoup
import urllib3

'''
Main fucntion

'''

http = urllib3.PoolManager()
page = http.urlopen('GET','http://prixan.com/')
soup = BeautifulSoup(page)
soup.prettify()
for link in soup.find_all('a'):
    print(link.get('href'))
