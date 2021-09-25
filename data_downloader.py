
import sys
import os

import logging
import requests
import datetime
import dateutil.parser

logger = logging.getLogger(__name__)


def download_newer(url, fpath):
    # compare the web version of an object and any existing file version of the object to 
    # conditionally download it  
    r = requests.head(url)
    url_time = r.headers['last-modified']
    url_date = dateutil.parser.parse(url_time)
    if os.path.exists(fpath):
        file_time = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
    else:
        file_time = datetime.datetime(1,1,1,0,0,0)
    
    if url_date > file_time:
        if not os.path.exists(os.path.dirname(fpath)):
            os.makedirs(os.path.dirname(fpath))
        with open(fpath, 'wb') as fd:
            for chunk in r.iter_content(4096):
                fd.write(chunk)



def main(args=[]):
    pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(sys.argv)