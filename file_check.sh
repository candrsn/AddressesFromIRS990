#!/bin/bash

# call this as
#  find tmpdata/2017 -exec bash ./file_check.sh {} \;

fil="$1"

if [ -f $fil ]; then
    lastLine=`tail -n 1 $fil`
    if [ ! "${lastLine:0:9}" == "</Return>" ]; then
        echo "# ${lastLine:0:9}"
        echo "rm $fil"
    fi
fi
