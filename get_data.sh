#!/bin/bash

if [ ! "$0" == "bash" -a ! "$0" == "-bash" ]; then
  set -e
else
  echo "running as $0 so suppressing fail on error"
fi

get_index() {
	curl -O https://s3.amazonaws.com/irs-form-990/index_2011.csv
}

get_exodb_mdf() {
    curl -O https://www.irs.gov/pub/irs-soi/eo_xx.csv
    curl -O https://www.irs.gov/pub/irs-soi/eo_pr.csv
    curl -O https://www.irs.gov/pub/irs-soi/eo1.csv
    curl -O https://www.irs.gov/pub/irs-soi/eo2.csv
    curl -O https://www.irs.gov/pub/irs-soi/eo3.csv
    curl -O https://www.irs.gov/pub/irs-soi/eo4.csv

    curl -O https://www.irs.gov/pub/irs-soi/SIT%202017.csv
    curl -O https://www.irs.gov/pub/irs-soi/SIT%202016.csv

}

get_irs_zipstats() {
    curl -O https://www.irs.gov/pub/irs-soi/zipcode2015.zip
}

get_aws_yr_list() {
    ayr="$1"
    destFile="aws_${ayr}.lst.gz"
    
    if [ -s $destFile ]; then
      return
    fi
    echo "get s3 listing for $ayr"

    aws s3 ls s3://irs-form-990/${ayr} --recursive |  gzip -c - > $destFile
}

get_years_listings() {
    for i in 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018; do
        get_aws_yr_list $i
    done
}

refresh_status() {
    yr="$1"
    find data/${yr} -name "*xml" | sed -e 's/data\/.*\/..\///' | sort > status_${yr}.lst
    
    echo "PRAGMA SYNCHRONOUS=off;
    CREATE TABLE IF NOT EXISTS retrieve_log (path TEXT PRIMARY KEY);
.headers off
.import status_${yr}.lst retrieve_log

CREATE UNIQUE INDEX retrieve_log__ind on retrieve_log(path);

    " | sqlite3 listing.db
}

load_yr_from_aws_listing() {
    yr="$1"
    if [ ! -r tmp/p ]; then
      mkfifo tmp/p
    fi
    zcat aws_${yr}.lst.gz | awk 'BEGIN {print "date,time,size,path"; } /./ { print $1 "," $2 "," $3 "," $4; }' >> tmp/p &
    echo "
PRAGMA SYNCHRONOUS=off;
CREATE TABLE IF NOT EXISTS aws_listing (date TEXT, time TEXT, size INTEGER, path TEXT PRIMARY KEY);
.headers on
.mode csv
.import 'tmp/p' aws_listing

    " | sqlite3 listing.db
}

load_from_aws_listings() {
    for yr in 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018; do
        load_yr_from_aws_listing $yr
    done
    echo "
PRAGMA SYNCHRONOUS=off;
INSERT INTO filings (object_id) SELECT path
    FROM aws_listing a 
    WHERE NOT EXISTS (SELECT 1 FROM filings f WHERE f.object_id = path);

    " | sqlite3 listing.db
}

index_2_db() {
  if [ -n "$1" ]; then
    wyr="$1"
  else
    wyr="2016"
  fi
  
  get_years_listings
  refresh_status $wyr

  echo "
PRAGMA synchronous=off;

CREATE TABLE IF NOT EXISTS filings (return_id TEXT,
    filing_type TEXT,
    ein text,
    tax_period TEXT,
    sub_date TEXT,
    taxpayer_name TEXT,
    return_type TEXT,
    dln TEXT,
    object_id TEXT PRIMARY KEY );

.headers off
.mode csv
.import index/index_2017.csv filings
.import index/index_2015.csv filings
.import index/index_2014.csv filings
.import index/index_2013.csv filings
.import index/index_2012.csv filings
.import index/index_2011.csv filings
.import index/index_2010.csv filings

UPDATE filings SET object_id = object_id || '_public.xml' WHERE not object_id like '%_public.xml';
  " | sqlite3 listing.db

  # merge in data from the aws S3 listing
  load_from_aws_listings
}

build_dl_script() {
  yr="$1"

  echo "
.mode column
.output  'tmp/retrieve_aws.sh'
SELECT 'mkdir -p data/${yr}/' || s.seg || ';'
    FROM  (SELECT DISTINCT
        substr(object_id,5,2) as seg
      FROM filings f
      WHERE object_id like '${yr}%.xml' and
        NOT EXISTS (SELECT 1 FROM retrieve_log r WHERE r.path = f.object_id) ) as s
  ;

SELECT 'cd data/${yr}';
SELECT 'idx=0';
SELECT 'if [ ! -s '|| substr(s.url,5,2) || '/' || s.url|| ' ]; then idx=\$((idx + 1)); (cd ' || substr(s.url,5,2) || '; curl -O ' || s.fullurl || ' &); fi'
    FROM (SELECT 'https://s3.amazonaws.com/irs-form-990/'||object_id as fullurl, 
        object_id as url
      FROM filings f
      WHERE object_id like '${yr}%.xml' and
        NOT EXISTS (SELECT 1 FROM retrieve_log r WHERE r.path = f.object_id) ) as s
    ORDER BY url
    ;

  " | sqlite3 listing.db

  cat tmp/retrieve_aws.sh | awk '/./ { print $0; if ( (NR % 150) == 0 ) { 
  print "if [ $idx -gt 5 ]; then "; print "sleep 3; fi"; 
  print "if [ $idx -gt 50 ]; then"; print "child_count=`ps -ef | grep curl | wc -l`; if [ $child_count -gt 50 ]; then sleep $((child_count * 4 / 15)); echo  \" sleeping for \"$((child_count * 4 / 15)); fi" 
  print "idx=0";
  print "fi"; } }' > tmp/span_${yr}_dl.sh
}

main() {
    rm -f listing.db
    mkdir -p index
    mkdir -p tmp
    mkdir -p data

    if [ -n "$1" ]; then
      list_yr="$1"
    else
      list_yr=2017
    fi
    echo "running for year ${list_yr}"
    index_2_db ${list_yr}

    build_dl_script ${list_yr}
}

if [ ! "$0" == "bash" -a ! "$0" == "-bash" ]; then
    main "$1"
fi
    
