## scan an S3 bucket on multiple monotonic axes for new files

import sys
import os
import sqlite3

import glob
import boto3
import logging
from botocore.parsers import PROTOCOL_PARSERS
import requests
import datetime
import dateutil.parser
import time
import multiprocessing

logger = logging.getLogger(__name__)


def aws_s3_listing(s3client, bucket, prefix="", cToken=None, restartAt=""):
#def aws_s3_listing(bucket, prefix="", cToken=None, restartAt=None):
    logger.debug(f"{bucket} {prefix} {cToken}")

    s3client = boto3.client('s3')
    if cToken is not None:
        response = s3client.list_objects_v2(
            Bucket=bucket,
            Delimiter='/',
            EncodingType='url',
            MaxKeys=5000,
            Prefix=prefix,
            ContinuationToken=cToken,
            FetchOwner=False
        )
    else:
        if restartAt > '':
            response = s3client.list_objects_v2(
                Bucket=bucket,
                Delimiter='/',
                EncodingType='url',
                MaxKeys=5000,
                Prefix=prefix,
                FetchOwner=False,
                StartAfter=restartAt
            )
        else:
            response = s3client.list_objects_v2(
                Bucket=bucket,
                Delimiter='/',
                EncodingType='url',
                MaxKeys=5000,
                Prefix=prefix,
                FetchOwner=False
            )

    return { "Contents": response.get("Contents") or [], 
        "Prefixes": response.get("CommonPrefixes") or [], 
        "ContinuationToken": response.get("NextContinuationToken"),
        "scanPrefix": prefix}


def s3_listing_ddl(db):
    cur = db.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS s3_listing (key TEXT, bucket TEXT, size INTEGER, object_date TIMESTAMP )
    """)
    cur.execute("""CREATE UNIQUE INDEX IF NOT EXISTS s3_listing__bucket__key__ind on s3_listing(bucket, key)
    """)
    cur.execute("""CREATE TABLE IF NOT EXISTS s3_listing_scan (prefix TEXT, bucket TEXT, last_key TEXT, scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
    """)
    cur.execute("""CREATE UNIQUE INDEX IF NOT EXISTS s3_listing_scan__bucket__prefix__ind on s3_listing_scan(bucket, prefix)
    """)

    assert cur.fetchall() is not None, "unable to create s3 listing tables"


def save_s3_listing_data(db, data):
    if data is None or len(data) == 0:
        #gracefully leave if there is nothing to save
        return []

    cur = db.cursor()
    cur.executemany("""INSERT INTO s3_listing (key, bucket, object_date, size) VALUES (?,?,?,?)
    ON CONFLICT (bucket, key) DO
    UPDATE SET object_date = excluded.object_date, size = excluded.size
    """, data)
    assert cur.fetchall is not None, "Unable to save listing data to DB"


def save_s3_listing_scan_info(db, bucket, prefix):
    cur = db.cursor()
    cur.executemany("""INSERT INTO s3_listing_scan (prefix, bucket) VALUES (?,?)
    ON CONFLICT (bucket, prefix) DO
    UPDATE SET scan_date = excluded.scan_date
    """, [[prefix, bucket]])
    assert cur.fetchall is not None, "Unable to save scan info data to DB"

    cur.execute("""SELECT last_key FROM s3_listing_scan s WHERE bucket = ? and prefix = ?
    """, [bucket, prefix])
    res = cur.fetchone()

    return res[0] or ""

def scan_s3_prefix(s3client, db, bucket, pfx):
    data = []
    more_prefixes = []

    resp = aws_s3_listing(s3client, bucket, pfx)
    while resp.get('ContinuationToken') is not None:
        resp = aws_s3_listing(s3client, bucket, prefix=pfx, cToken=resp["ContinuationToken"])
        d = [ [d['Key'], bucket, d["LastModified"].isoformat(), d["Size"]] for d in resp['Contents']]
        data += d
        more_prefixes += resp.get("Prefixes") or []
        if len(data) >= 10000:
            save_s3_listing_data(db, data)
            data = []

    save_s3_listing_data(db, data)

    return more_prefixes or []


def scan_s3(db, bucket, prefixes):
    # create missing tables
    s3_listing_ddl(db)
    more_prefixes = []

    s3client = boto3.client('s3')
    for pfx in prefixes:
        save_s3_listing_scan_info(db, bucket, pfx)

        more_prefixes += scan_s3_prefix(s3client, db, bucket, pfx)
        db.commit()

        for pfx in more_prefixes:
            scan_s3_prefix(s3client, db, bucket, pfx)

        ## Pool.add(resp["Prefixes"])


def update_scan_info(db, prefixes):
    cur = db.cursor()
    for itm in prefixes:
        cmd = f"""UPDATE s3_listing_scan as u 
            SET last_key = (SELECT max(l.key) 
                FROM s3_listing l 
                WHERE l.key like '{itm}%' and
                  l.bucket = u.bucket )
            WHERE u.prefix = '{itm}'
        """
        logging.info(cmd)
        cur.execute(cmd)

        # wait for the update command to complete 
        assert cur.fetchall() is not None, "problems computing info"


def indexing_worker(input, output):
    # per thread variables go here

    s3client = boto3.client('s3')

    for args in iter(input.get, 'STOP'):
        #result = scan_s3_prefix(args)
        result = aws_s3_listing(s3client, *args)
        output.put(result)


def scan_s3_using_pool(db, bucket, prefixes):
    NUM_PROCESSES = 8

    task_queue = multiprocessing.Queue()
    done_queue = multiprocessing.Queue()

    # create missing tables
    s3_listing_ddl(db)
    more_prefixes = []
    data = []
    tasks = 0

    s3client = boto3.client('s3')

    for pfx in prefixes:
        start_key = save_s3_listing_scan_info(db, bucket, pfx)
        task_queue.put((bucket, pfx, None, start_key))
        tasks += 1
    
    # Start worker processes
    for i in range(NUM_PROCESSES):
        multiprocessing.Process(target=indexing_worker, args=(task_queue, done_queue)).start()

    # grab some results
    while tasks > 0 or not done_queue.empty():
        # wait for one of the threads to stop, collect its output and start it on the next portion
        itm = done_queue.get()
        tasks -= 1

        logger.debug(f"{itm}")

        if itm.get("ContinuationToken") is not None:
            logger.info(f"""continue with scanning {itm.get("scanPrefix")} using {itm.get("ContinuationToken")}""")
            task_queue.put((bucket, itm.get("scanPrefix"), itm.get("ContinuationToken")))
            tasks += 1
        else:
            logger.info(f"""finished scanning {itm.get("scanPrefix")}""")
            update_scan_info(db, [itm.get("scanPrefix")])

        d = [ [d['Key'], bucket, d["LastModified"].isoformat(), d["Size"]] for d in itm['Contents']]
        data += d
        if len(data) >= 5000:
            save_s3_listing_data(db, data)
            data = []

        for itmdir in itm.get("Prefixes"):
            task_queue.put((bucket, itmdir))
            tasks += 1

    logging.info(f"shutting the scan down")
    # Tell child processes to stop
    for i in range(NUM_PROCESSES):
        task_queue.put('STOP')

    task_queue.close()
    done_queue.close()

    # after shutting doen all of the workers, save any remaining data
    save_s3_listing_data(db, data)


def parse_args(args):
    pass

    return 

def parse_args():
    pass
    ["--db", "listing/s3_catalog.db",
                "--bucket", "irs-form-990",
                "--prefixes", "default"]

def irs_prefixes():
    core_prefixes = [str(d) for d in range(2007, 2022)]
    prefixes = []
    for itm in core_prefixes:
        # add a small scanning differentiator so more threads can be built in parallel
        munged = [f"{itm}{d:-01}" for d in range(0, 10, 1)]
        prefixes += munged
    # add the special file types
    prefixes += ["index", "list"]
    
    return prefixes

def default_prefixes():
    # see https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-keys.html
    # for why this list
    core_prefixes = [chr(d) for d in [range(97,122)]]
    core_prefixes += [chr(d) for d in [range(65,90)]]
    core_prefixes += [chr(d) for d in [range(48, 57)]]
    core_prefixes += ['!', '-', '_', '.', '*', "'", '(', ')']

    return core_prefixes

def main(args=[]):

    if len(args) < -2:
        usage()
    else:

        s3_catalog = "data/s3_catalog.db"
        s3_bucket = "irs-form-990"

        db = sqlite3.connect(s3_catalog)

        prefixes = default_prefixes()
        prefixes = ["2","index", "list"]

        # The unthreaded version
        #scan_s3(db, 'irs-form-990', prefixes=prefixes)

        # The threaded version
        scan_s3_using_pool(db, s3_bucket, prefixes=prefixes)

        update_scan_info(db, prefixes)
        db.commit()
        logger.info("All Done")


def usage():
    logger.warning("")


def cli():
    args = sys.argv
    main(args)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(sys.argv)
