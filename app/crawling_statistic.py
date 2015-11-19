FetchStatistic = namedtuple('FetchStatistic',
                            ['url',
                             'next_url',
                             'status',
                             'exception',
                             'content_type',
                             'encoding',
                             'num_urls',
                             'num_new_urls'])

def record_statistic(self, url=None,
                     next_url=None,
                     status=None,
                     exception=None,
                     content_type=None,
                     encoding=None,
                     num_urls=0,
                     num_new_urls=0):
    """Record the FetchStatistic for completed / failed URL."""
    fetch_statistic = FetchStatistic(url=url,
                                     next_url=None,
                                     status=None,
                                     exception=exception,
                                     content_type=None,
                                     encoding=None,
                                     num_urls=0,
                                     num_new_urls=0)
    self.done.append(fetch_statistic)
