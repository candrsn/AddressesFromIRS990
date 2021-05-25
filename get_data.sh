#!/bin/bash


##  bash -x get_data.sh 2020 | tee run2020.log
set -e

if [ "$CONDA_SHLVL" == "0" -o -z "$CONDA_SHLVL" ]; then
    eval "$(conda shell.bash hook)"
    conda activate gis
fi

if [ ! "$0" == "bash" -a ! "$0" == "-bash" ]; then
  # turn onn exit on error if it is set
  set +e
else
  echo "running as $0 so suppressing fail on error"
fi

set +e

get_irs_index() {
    curl -O https://s3.amazonaws.com/irs-form-990/index_${1}.csv
    remove_xml index_${1}.csv
}

archive_indexes() {
    dt=`date -r index_2021.csv +%Y%m%d`
    dest="index_${dt}.zip"
    set -e
    if [ ! -s bk/$dest ]; then
        zip $dest index*json index*csv
        mv $dest bk
        rm index*csv index*json
    fi
}

archive_listings() {
    dt=`date -r aws_2021.lst.gz "+%Y%m%d"`
    dest="aws_listing_${dt}.zip"
    set -e
    if [ ! -s bk/$dest ]; then
        zip $dest aws*gz
        mv $dest bk
        rm aws*gz
    fi
}

get_irs_static_files() {
    return

    pushd index
    
    for yr in `get_years`; do
        if [ ! -s index_${yr}.csv ]; then
            get_irs_index $yr
        fi
    done
    popd

    # hold off on this for now
    #get_irs_eo
}

get_irs_eo() {
    nyr=`date +%Y%m`
    mkdir -p eo_extract/$nyr

    pushd eo_extract/$nyr

    for src in eo_xx eo_pr eo1 eo2 eo3 eo4; do
        curl -O https://www.irs.gov/pub/irs-soi/${src}.csv
        remove_xml ${src}.csv
    done

    popd

}

get_years() {
    echo "2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021"
}

get_tax_years_from_csv() {
  for yr in `get_years`; do
      cat index/index_${yr}.csv | cut -d ',' -f4 | cut -c 1-4 | sort -u
  done  | sort -u | grep -i -v "tax"
}

get_irs_trust_info() {
    rflg="-i"
    pushd trusts
    for yr in `get_years`; do
        src="SIT%20${yr}.csv"
        if [ ! -s "$src" ]; then
            #curl -O https://www.irs.gov/pub/irs-soi/$src
	    :
	fi
        remove_html "$src"
    done

    for src in "2019-sit.csv" "2018_sit.csv" "SIT 2017.csv" "SIT 2016.csv" ; do
        if [ ! -s "$src" ]; then
            curl -O https://www.irs.gov/pub/irs-soi/"$src"
	fi
	remove_html "$src"
    done

    popd

}

get_irs_zipstats() {
    for yr in `get_years`; do
        src="zipcode${yr}.zip" 
        if [ ! -s "$src" ]; then
            curl -O https://www.irs.gov/pub/irs-soi/$src
	    remove_html $src
	fi
    done

}

remove_xml() {
    src="$1"
    if [ ! -r "$src" ]; then
        return
    fi
    
    f=`file "$src" | grep -c XML`
    if [ $f -gt 0 ]; then
	echo "$src is XML:: $f"
        rm $rflg $src
    fi
}

remove_html() {
    src="$1"
    if [ ! -r "$src" ]; then
        return
    fi
    
    f=`file "$src" | grep -c HTML`
    if [ $f -gt 0 ]; then
	echo "$src is HTML:: $f"
        rm $rflg $src
    fi

}

get_migration() {

    for baseyr in 10 11 12 13 14 15 16 17 18 19; do
        nyr=$((baseyr + 1))
        src="${baseyr}${nyr}migrationdata.zip"
	if [ ! -s "$src" ]; then
            curl -O https://www.irs.gov/pub/irs-soi/${src}
	    remove_html "$src"
        fi
    done
}

list_prefix() {
    aws s3 ls s3://irs-form-990/${1} --recursive | awk -e '/./ { print $4 };'
}

get_aws_indexes() {
    pushd index
    archive_indexes | :
    
    for sfx in `list_prefix index_`; do
        aws s3 cp s3://irs-form-990/${sfx} ${sfx}
    done
   popd
}

get_aws_yr_list() {
    pushd listing
    ayr="$1"
    destFile="aws_${ayr}.lst.gz"
    
    if [ ! -s $destFile ]; then
        echo "get s3 listing for $ayr"
        aws s3 ls s3://irs-form-990/${ayr} --recursive |  gzip -c - > $destFile
    fi
    popd
}

get_years_listings() {
    force_reload="$1"
    if [ -z "$force_reload" ]; then
        force_reload=0
    fi

    pushd listing
    archive_listings
    popd

    for i in `get_years`; do
        get_aws_yr_list $i $force_reload &
        
        if [ `jobs -p | grep -c '.'` -gt 7 ]; then
            wait -n
        fi
    done
    
    echo "waiting for aws index scans to complete"
    ## wait for all jobs started above to end
    wait
    
    get_aws_indexes
}

setup_retrieve_log() {
    echo "CREATE TABLE IF NOT EXISTS retrieve_log (path TEXT);
    CREATE TABLE IF NOT EXISTS local_index (object_id TEXT, fullpath TEXT, taxyr TEXT );
    CREATE UNIQUE INDEX IF NOT EXISTS retrieve_log__path__ind ON retrieve_log(path);
    CREATE UNIQUE INDEX IF NOT EXISTS local_index__fullpath__ind ON local_index(fullpath);
    "
}

build_simple_object_listing() {
    yr=$1
    # build inserts for retrieve_log
    pushd tmpdata;
    ( 
      find ${yr} -name "*xml" | sed -e 's/.*\/..\///' 
      zf="irs_f990_${yr}.zip"
      if [ -s "$zf" ]; then
         unzip -l ${{zf} | awk -e '/./ { a=split($4,p,"/"); print p[a]; }'
      fi ) | sort -u | grep -e '\.xml' > listing/status_${yr}.lst
    popd
}

build_object_lisitng() {
    yr=$1
    # build inserts for local_index
    pushd tmpdata;
    ( 
      find ${yr} -type f | awk -e '/./ {  a=split($0,p,"/"); print p[a] "," $0 "," '${yr}';}' 
      zf="irs_f990_${yr}.zip"
      if [ -s "$zf" ]; then
        # the ZIPfile listing has a preamble and postamble to the lisitng
         unzip -l ${zf} | awk -e 'NR>4 { a=split($4,p,"/"); if (substr($0,1,1) == " " && p[a] != "") {  print p[a] "," $4 "," '$yr'; }}'
      fi ) | sort -u  > ../listing/local_status_${yr}.lst
    popd
}

refresh_status() {
    if [ -z "$1" ]; then
        echo "refresh_status requires a year or years"
        return
    fi

    pushd .
    for yr in $1; do

    #build_simple_object_listing $yr
    build_object_lisitng $yr
 
    ( setup_retrieve_log  
    echo "PRAGMA SYNCHRONOUS=off;

.headers off
.mode csv

 DROP TABLE IF EXISTS import_tmp;
 CREATE TABLE import_tmp AS SELECT * FROM local_index;
.import \"listing/local_status_${yr}.lst\" import_tmp

 INSERT INTO local_index (object_id, fullpath, taxyr)
     SELECT object_id, fullpath, taxyr from import_tmp p
         WHERE NOT EXISTS (SELECT 1 FROM local_index r WHERE r.fullpath = p.fullpath);

 -- we need the DISTINCT clause here because some returns are encoded in multiple years
 INSERT INTO retrieve_log (path)
     SELECT DISTINCT object_id from import_tmp p
         WHERE p.object_id like '%.xml' and
         NOT EXISTS (SELECT 1 FROM retrieve_log r WHERE r.path = p.object_id);

 DROP TABLE IF EXISTS import_tmp;

       ") | tee scripts/refresh_status_${yr}.sql |  sqlite3 data/listing.db
    done
    popd
}

load_yr_from_aws_listing() {
    yr="$1"
    if [ ! -r tmp/p ]; then
      mkfifo tmp/p
    fi
    zcat listing/aws_${yr}.lst.gz | awk 'BEGIN {print "date,time,size,path"; } /./ { print $1 "," $2 "," $3 "," $4; }' >> tmp/p &
    echo "
PRAGMA SYNCHRONOUS=off;
DROP TABLE IF EXISTS aws_listing_tmp;
CREATE TABLE IF NOT EXISTS aws_listing_tmp (date TEXT, time TEXT, size INTEGER, path TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS aws_listing (date TEXT, time TEXT, size INTEGER, path TEXT PRIMARY KEY);
CREATE UNIQUE INDEX IF NOT EXISTS aws_listing__path__ind on aws_listing(path);

.headers off 
.mode csv
.import 'tmp/p' aws_listing_tmp
INSERT INTO aws_listing (date, time, size, path)
    SELECT date, time, size, path FROM aws_listing_tmp t
      WHERE t.path > '' and
          NOT EXISTS (SELECT 1 FROM aws_listing l WHERE l.path = t.path);

DROP TABLE aws_listing_tmp;

    " | sqlite3 data/listing.db
}

load_from_aws_listings() {
    setup_filings | sqlite3 data/listing.db

    for yr in `get_years`; do
        load_yr_from_aws_listing $yr
    done
    (
    echo "
PRAGMA SYNCHRONOUS=off;
CREATE INDEX IF NOT EXISTS filings__object_id__ind on filings(object_id);
CREATE INDEX IF NOT EXISTS aws_listing__path__ind on aws_listing(path);

INSERT INTO filings (object_id, tax_period, return_type)
  SELECT DISTINCT a.path, substr(a.path,1,4) | '00', 'AWS listing'
    FROM aws_listing a
    WHERE 
        length(a.path) = 29 and
        NOT EXISTS (SELECT 1 FROM filings f WHERE f.object_id = a.path);

    " ) | sqlite3 data/listing.db
}

setup_filings() {
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
    object_id TEXT );

    "
}

build_db() {
  
  (setup_filings
  echo "

.headers off
.mode csv
"

for yr in `get_years`; do
ifil="index/index_${yr}.csv"
  if [ -s "$fil" ]; then
    echo ".import ${ifil} filings"
  fi
done

echo "
DELETE FROM filings WHERE object_id is NULL;

UPDATE filings SET object_id = object_id || '_public.xml' WHERE not object_id like '%_public.xml';
CREATE INDEX IF NOT EXISTS filings__object_id__ind on filings(object_id);

DELETE FROM filings as fo 
    WHERE rowid < (SELECT max(rowid) FROM filings f WHERE f.object_id = fo.object_id)
  ") | tee -a scripts/build_data.sql | sqlite3 data/listing.db

  # merge in data from the aws S3 listing
  load_from_aws_listings
}

build_cleanup_script() {
  yr="$1"

  echo "
.mode column
.headers off
.output  'tmp/clean_${yr}_files.sh'

SELECT 'pushd tmpdata';
SELECT 'rm ' || s.fullpath
    FROM (SELECT
        object_id, fullpath
      FROM local_index f
      WHERE
         taxyr = '$yr' and
         length(object_id) != 29 ) as s
    ORDER BY object_id;

SELECT 'find $yr -type d  -size -10 -delete';

SELECT 'popd';

-- have to scan this way as the error being fixed was this way
SELECT 'pushd tmpdata/';
SELECT 'zip -d irs_f990_${yr}.zip ' ||  '${yr}/' || substr(s.object_id,5,2) || '/' || s.object_id
    FROM (SELECT
        object_id, taxyr
      FROM local_index f
      WHERE 
         taxyr = '$yr' and
         length(object_id) != 29 ) as s
    ORDER BY object_id;


SELECT 'popd';
  " | tee scripts/build_cln_script_${yr}.sql | sqlite3 data/listing.db

    echo "after downloading the files run this to put the files into a ZIP archive and then remove the original downloaded files
    bash -x tmp/clean_${yr}_files.sh

    " >&2
}

build_dl_script() {
  yr="$1"

  echo "
.mode column
.headers off
.output  'tmp/retrieve_aws.sh'
SELECT 'mkdir -p tmpdata/${yr}/' || s.seg || ';'
    FROM  (SELECT DISTINCT
        substr(object_id,5,2) as seg
      FROM filings f
      WHERE object_id like '${yr}%.xml' and
        NOT EXISTS (SELECT 1 FROM retrieve_log r WHERE r.path = f.object_id) ) as s;

SELECT 'pushd tmpdata/${yr}';
SELECT 'idx=0';
SELECT 'if [ ! -s '|| substr(s.url,5,2) || '/' || s.url|| ' ]; then idx=\$((idx + 1)); (cd ' || substr(s.url,5,2) || '; curl -O ' || s.fullurl || ' &); fi'
    FROM (SELECT 'https://s3.amazonaws.com/irs-form-990/'||object_id as fullurl, 
        object_id as url
      FROM filings f
      WHERE object_id like '${yr}%.xml' and
        NOT EXISTS (SELECT 1 FROM retrieve_log r WHERE r.path = f.object_id) ) as s
    ORDER BY url;

  " | tee scripts/build_dl_script_${yr}.sql | sqlite3 data/listing.db


  ## inject a pid and a wait every 150 lines in the file
  (cat tmp/retrieve_aws.sh | awk '/./ { print $0; if ( (NR % 150) == 0 ) {
    print "# wait for all child processes to complete"
    print "wait" 
    print "idx=0";
  }
  if ( (NR % 300) == 0 ) {
    print "sp=`jobs | grep -c \"Run\"`";
    print "if [ $sp -gt 0 ]; then";
    print "    wait";
    print "    sleep 1";
    print "fi";
  }
   }'
   ) > tmp/span_${yr}_dl.sh
   
   echo "to actually do the download.....
   bash -x tmp/span_${yr}_dl.sh
   " >&2
}

reload() {
    rm -f data/listing.db data/listing.db-journal| :
    sync
}

load_files() {

    if [ "$FORCERELOAD" == "1" ]; then
        reload
    fi
    # Re-acquire the AWS listings
    get_years_listings 0
    # get a  list of what has been downloaded
    refresh_status "$list_yrs"

    get_irs_static_files

    for list_yr in $list_yrs; do
        echo "running for year ${list_yr}"
        get_aws_yr_list $list_yr
    done

}

main()  {

    mkdir -p index | :
    mkdir -p tmp | :
    mkdir -p data | :
    mkdir -p tmpdata | :

    if [ -n "$1" ]; then
      list_yrs="$1"
    else
      list_yrs=`get_years`
    fi

    export FORCERELOAD="1"
    #get static and dynamic listings of returns
    load_files
 
    build_db

    for list_yr in $list_yrs; do
        build_dl_script ${list_yr}
        build_cleanup_script ${list_yr}
    done

    echo "All Done"
}

# if called as a "source" then do not do anything
if [ ! "$0" == "bash" -a ! "$0" == "-bash" ]; then
    main "$1"
    :
fi
    
