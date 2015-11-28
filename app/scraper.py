from pyquery import PyQuery as pq
import urllib.parse

class NoValidCssError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class Scraper(object):

    def __init__(self, data):
        self.data = data
        
    def find(self,f, lst):
        """ Reurn the first elem that evaluates to truth with function f"""
        for i in lst:
            t = f(i)
            if t:
                return t
        #LOGGER.error('Invalid css: %s')
        return None # None of the css_selectors was found on the html

    def extract(self,info_type, q):
        """ Extract link or text dependig on data type"""
        if not q:
            return None
        if info_type == 'image_css':
            return [e.attr['src'] for e in q.items()]
        else:
            return [e.text() for e in q.items()]

    def get_data(self, pyquery_tree, css_selectors):
        """ Query the page with the css_selfelectors dict using pyquery"""
        try:
            css_rules = {info_type : self.extract(info_type, self.find(pyquery_tree, selectors)) 
                         for info_type, selectors in css_selectors.items()}
        except Exception as e:
            print(e)
            return {'error': None}
        return css_rules

    def fix_url(self,url):
        """Prefix a schema-less URL with http://."""
        if '://' not in url:
            if 'www.' in url:
                url = url[4:]
            url_http = 'http://' + url
            url_https = 'https://' + url
        return (url_http, url_https)

    def find_css_selectors(self,root_url):
        wwwhttp, wwwhttps = self.fix_url(root_url)
        possible_urls = [wwwhttp, wwwhttps, root_url, 'https://'+root_url, 'http://'+root_url]
        for url in possible_urls:
            found = self.data.get(url, None)
            if found:
                return found

    def scrape(self, url, html):
        tree = pq(html)
        parts = urllib.parse.urlparse(url)
        root_url, port = urllib.parse.splitport(parts.netloc)
        css_selectors = self.find_css_selectors(root_url)
        if not css_selectors:
            return {'error':None}
        return self.get_data(tree, css_selectors)
