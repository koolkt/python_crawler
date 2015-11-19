#
# Verify functions
#

def host_okay(self, host):
    """Check if a host should be crawled.
    
    A literal match (after lowercasing) is always good.  For hosts
    that don't look like IP addresses, some approximate matches
    are okay depending on the strict flag.
    """
    host = host.lower()
    if host in self.root_domains:
        return True
    if re.match(r'\A[\d\.]*\Z', host):
        return False
    if self.strict:
        return self._host_okay_strictish(host)
    else:
        return self._host_okay_lenient(host)
    
def _host_okay_strictish(self, host):
    """Check if a host should be crawled, strict-ish version.
    
    This checks for equality modulo an initial 'www.' component.
    """
    host = host[4:] if host.startswith('www.') else 'www.' + host
    return host in self.root_domains

def _host_okay_lenient(self, host):
    """Check if a host should be crawled, lenient version.
    
    This compares the last two components of the host.
    """
    return lenient_host(host) in self.root_domains

def verify_headers(self, response):
    """ Verify that the response is ok and the webpage is in html"""
    content_type = None
    if response.status == 200:
        content_type = response.headers.get('content-type')
        pdict = {}
        if content_type:
            content_type, pdict = cgi.parse_header(content_type)
        encoding = pdict.get('charset', 'utf-8')
        return content_type in ('text/html', 'application/xml')

def url_allowed(self, url):
    if self.exclude and re.search(self.exclude, url):
        return False
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ('http', 'https'):
        #LOGGER.debug('skipping non-http scheme in %r', url)
        return False
    host, port = urllib.parse.splitport(parts.netloc)
    if not self.host_okay(host):
        #LOGGER.debug('skipping non-root host in %r', url)
        return False
    return True
