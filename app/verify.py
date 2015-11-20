#
# Verify functions
#
import urllib.parse
import re

def lenient_host(host):
    parts = host.split('.')[-2:]
    return ''.join(parts)

def _host_okay_strictish(host, root_domains):
    """Check if a host should be crawled, strict-ish version.
    
    This checks for equality modulo an initial 'www.' component.
    """
    host = host[4:] if host.startswith('www.') else 'www.' + host
    return host in root_domains

def _host_okay_lenient(host, root_domains):
    """Check if a host should be crawled, lenient version.
    
    This compares the last two components of the host.
    """
    return lenient_host(host) in root_domains

def host_okay(host, root_domains, strict):
    """Check if a host should be crawled.
    
    A literal match (after lowercasing) is always good.  For hosts
    that don't look like IP addresses, some approximate matches
    are okay depending on the strict flag.
    """
    host = host.lower()
    if host in root_domains:
        return True
    if re.match(r'\A[\d\.]*\Z', host):
        return False
    if strict:
        return _host_okay_strictish(host, root_domains)
    else:
        return _host_okay_lenient(host, root_domains)

def verify_headers(response):
    """ Verify that the response is ok and the webpage is in html"""
    content_type = None
    if response.status == 200:
        content_type = response.headers.get('content-type')
        pdict = {}
        if content_type:
            content_type, pdict = cgi.parse_header(content_type)
        encoding = pdict.get('charset', 'utf-8')
        return content_type in ('text/html', 'application/xml')

def url_allowed(url, root_domains, exclude=None, strict=True):
    if exclude and re.search(exclude, url):
        return False
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ('http', 'https'):
        #LOGGER.debug('skipping non-http scheme in %r', url)
        return False
    host, port = urllib.parse.splitport(parts.netloc)
    if not host_okay(host, root_domains, strict):
        #LOGGER.debug('skipping non-root host in %r', url)
        return False
    return True
