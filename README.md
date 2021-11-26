##Extract Address data from IRS form 990

  * Retrieve data from the S3 bucket with the efile forms
  * Extract and normalize address data from the forms


### monthly flow
   python3 s3_indexer.py
   bash -x get_data.sh
   # which builds several content download scripts into tmp

   bash -x retrieve_aws.sh
   


