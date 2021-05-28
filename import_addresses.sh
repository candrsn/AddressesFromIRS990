#!/bin.bash
#import_addresses.sh

export TMPDIR="~/tmp"

set -e

setup() {
    echo "PRAGMA SYNCHRONOUS=off;
CREATE TABLE IF NOT EXISTS irs_address (
    BusinessName TEXT ,TaxYr TEXT, Addr1 TEXT, Addr2 TEXT, Addr3 TEXT, 
    Locality TEXT ,StateorProvince TEXT, Country TEXT, PostalCode TEXT,
    AddrType TEXT, EIN TEXT, YearFormation TEXT, NumEmployees TEXT, ReturnFile TEXT );

    " | sqlite3 $DB
}

import_file() {
    echo "PRAGMA SYNCHRONOUS=off;
.headers off
.mode csv
.import $1 irs_address

    " | sqlite3 $DB
}

import_yr() {
    yr="$1"
    DB="data/irs_addresses_${yr}.db"
    if [ -r "$DB" ]; then
        rm $DB | :
    fi

    setup

    import_file build/address_${yr}.csv

    echo "
CREATE INDEX irs_address__returnfile__ind on irs_address(returnfile);
.mode tab
.headers on
.once odd_returns.tsv
SELECT returnfile FROM irs_address WHERE returnfile IN (SELECT returnFile FROM irs_address i GROUP BY 1 HAVING count(*) > 10000);
 " | sqlite3 $DB
}

for s in build/address_*.csv; do
    j=`basename "$s" .csv | sed -e 's/.*address_//'`
    import_yr $j
done