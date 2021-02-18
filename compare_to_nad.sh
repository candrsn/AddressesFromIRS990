#!/bin/bash

# compare_to_nad.sh
DB="analysis.db"

get_states() {
    echo "AR CA DC DE IN MA MD ME MT NC NM NY TN UT VA VT"
}



compare_state() {
  _st="$1"
  echo "PRAGMA SYNCHRONOUS=off;
ATTACH DATABASE '/home/candrsn/media/archive/fema/nad/nad.gpkg' as nad;
ATTACH DATABASE 'irs_address' as irs;

CREATE TABLE nad_addr as SELECT * FROM nad.address WHERE state = 'AR';
UPDATE nad_addr set post_comm = lower(post_comm), streetname = lower(streetname), stn_postyp = lower(stn_postyp);
CREATE TABLE irs_addr AS SELECT * FROM irs.irs_address WHERE state = 'AR';
CREATE INDEX nad_addr__idx ON nad_addr(add_number,post_comm);

SELECT * from nad_addr 
    WHERE
       STATE = 'AR' and 
       post_comm = 'Mountain Home' and
       add_number = '1635' and StreetName like 'L%'
    LIMIT 50;

CREATE TEMP TABLE matches_t1 as SELECT i.addr1, i.locality, i.rownum as irn, n.objectid,
    n.zip_code, n.add_number, n.streetname, n.stn_postyp, n.post_comm
    FROM nad_Addr n,
      irs_addr i
    WHERE
      n.post_comm = lower(i.locality) and
      n.add_number = trim(substr(i.addr1,1,instr(i.addr1,' '))) and
      n.streetname like substr(i.addr1,instr(i.addr1,' ')

  " | sqlite3 $DB
}


main() {
  for st in `get_states`; do
     compare_state $st
  done

}

