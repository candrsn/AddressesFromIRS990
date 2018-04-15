#!/bin.bash

#import_addresses.sh
DB=irs_addresses.db

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

rm $DB
setup

import_file address_2010.csv
import_file address_2012.csv
import_file address_2015.csv
import_file address_2017.csv
import_file address_2018.csv

