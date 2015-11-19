def scrape_information_from_page():
    """ Get the text from the elements pointed to by css selectors"""
    is_not_product = yield from self.redis_queue.sismember(self.seed+':no_product_urls',
                                                           response.url)
    if (not is_not_product):
        data = self.data_extractor.extract(q)
        if not len(data):
            # No products found
            yield from self.redis_queue.sadd(self.seed+':no_product_urls',
                                             [response.url])
        else:
            # Add to product_urls>add url asociated with info>send to redis
            yield from self.redis_queue.sadd(self.seed+':product_urls',
                                             [response.url])
            data.update({'url': response.url})
            yield from self.save(data)

def find(f, lst):
    """ Reurn the first elem that evaluates to truth with function f"""
    for i in lst:
        t = f(i)
        if t:
            return t

def extract(info_type, q):
    """ Extract link or text dependig on data type"""
    if info_type == 'image_css':
        return [e.attr['src'] for e in q.items()]
    else:
        return [e.text() for e in q.items()]

def get_data(self, pyquery_tree, css_selectors):
    """ Query the page with the css_selectors dict using pyquery"""
    css_rules = {info_type : extract_info(info_type, find(pyquery_tree, selectors)) 
                 for info_type, selectors in css_selectors.items()}
    return data
