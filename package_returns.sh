#!/bin/bash

# exit on failure
set +e

if [ "$0" == "bash" -o "$0" == "-bash" ]; then
    export WD=`pwd`/tmpdata
    set -e
else
    export WD=`dirname $0`/tmpdata
fi

archive_year() {
    pushd $WD
    #pushd bk
    
    echo "archiving year $1"
    yr="$1"
    for i in $yr/*; do
        echo "archiving segment $i"
        j=`basename "$i"`
        if [ -d "$i" -a -n "$j" ]; then
            echo "zip returns from prefix $i"
            zip -u -q -r irs_f990_${yr}_${j}.zip ${i}
        fi
    done
    
    popd
 
}

archive_years() {
    echo "searching for years with XML data"
    yrs=`find tmpdata -maxdepth 3 -name "*_public.xml" | awk -e '/./ { split($0, r, "/"); print r[2]; }' | sort -u`

    for yr in $yrs; do
        echo "archiving year $yr"
        archive_year $yr
        merge_year $yr
    done
}

clean_year() {
    yr="$1"
    pushd tmpdata
    if [ -n "$yr" ]; then
        find "$yr"/*/ -name "*xml" -type f -delete
    fi

    popd
}

merge_year() {
    
    echo "mergeing segments for the year $yr"
    pushd $WD
    
    yr="$1"
    for x in irs_f990_${yr}_*.zip; do
        if [ -s "$x" ]; then
            s="1"
        else
            s=""
        fi
    done
    
    if [ -n "$s" ]; then
        # do not attempt to merge if there are not candidates
        
        dest="irs_f990_${yr}.zip"
        if [ -s "$dest" ]; then
            mv $dest ziptmp.zip
            orig="ziptmp.zip"
        else
            orig=""
        fi
        
        zipmerge irs_f990_${yr}.zip $orig irs_f990_${yr}_*.zip
        
        if [ -n "$orig" ]; then
            rm $orig | :
        fi
    fi
    
    ## remove the segments of returns for the year
    flgs="-i"
    flgs=""
    
    echo "removing the constituent files that were merged"
    rm $flgs irs_f990_${yr}_*.zip
    
    popd
    
}


if [ "$0" == "bash" -o "$0" == "-bash" ]; then
    echo "code is sourced,  call 
    archive_years"
else
    archive_years
fi


