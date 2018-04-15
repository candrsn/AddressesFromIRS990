#!/bin/bash

# compare_to_nad.sh


get_states() {
    echo "AR CA DC DE IN MA MD ME MT NC NM NY TN UT VA VT"
}



compare_state() {
  _st="$1"
  
}


main() {
  for st in `get_states`; do
     compare_state $st
  done

}

