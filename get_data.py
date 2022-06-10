

import sys
import os
import requests
import logging

logger = logging.getLogger(__file__)


def get_file(rfile, dest):
    logger.debug(f"downloading {dest}")

    req = requests.get(rfile, stream=True)
    if req.status_code in (200, 201, 202):
        with open(dest, 'wb') as w:
            for chunk in req.iter_content(chunk_size=512 * 1024):
                if chunk:
                    w.write(chunk)
        logger.info(f"downloaded {dest}")
    else:
        logger.warning(f"failed to download {rfile}")


def get_filelist(flist):
    with open(flist, 'r') as fl:
        for itm in fl:
            itm =  itm.strip()
            dest = f'rawdata/{os.path.basename(itm)}'
            if itm.startswith('#') or itm == '':
                continue
            dest = f'rawdata/{os.path.basename(itm)}'
            if not os.path.exists(dest):
                get_file(itm, dest)
            else:
                logger.debug(f"skipping download of {dest}")


def main(args=[]):

    get_filelist("2021_2022_urls.txt")

    logger.info("All Done")


if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)
    main(sys.argv)
