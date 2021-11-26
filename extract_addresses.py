### extract_address.py

from io import StringIO
import sys
import os
import io
import glob
import time
import xml.etree.ElementTree as ET
import unicodecsv as csv
import zipfile
import logging
import traceback
import db_logging
import sqlite3

# set TMPDIR to be here unless it already is defined
if "TMPDIR" not in os.environ:
    os.environ["TMPDIR"] = os.path.realpath(__name__)

TIMINGS = False

addressTags = [
    "AddressUS",
    "USAddress",
    "ForeignAddress",
    "PreparerFirmUSAdrress",
    "PreparerFirmForeignAddress",
    "HospitalNameAndAddress",
    "BooksInCareOfUSAddress",
    "AddressOfGamingRecKeeperUS"
    ]

addressContentTags = [
    "AddressLine1",
    "AddressLine1Txt"
    ]

businessContentTags = [
    "Filer/efile:BusinessName",
    "Filer/efile:Name",
    "BusinessNameLine1/..",
    "BusinessNameLine1Txt/.."
    ]

timestamps = [
    "Timestamp",
    "ReturnTS"
    ]

line1Tags = [
    "{http://www.irs.gov/efile}AddressLine1",
    "{http://www.irs.gov/efile}AddressLine1Txt"
]

line2Tags = [
    "{http://www.irs.gov/efile}AddressLine2",
    "{http://www.irs.gov/efile}AddressLine2Txt"
]

line3Tags = [
    "{http://www.irs.gov/efile}AddressLine3",
    "{http://www.irs.gov/efile}AddressLine3Txt"
]

zipCodeTags = [
    "{http://www.irs.gov/efile}ZIPCd",
    "{http://www.irs.gov/efile}ZIP",
    "{http://www.irs.gov/efile}ZIPCode",
    "{http://www.irs.gov/efile}PostalCode",
    "{http://www.irs.gov/efile}ForeignPostalCd",
    ]

cityTags = [
    "{http://www.irs.gov/efile}CityNm",
    "{http://www.irs.gov/efile}City"
    ]

stateTags = [
    "{http://www.irs.gov/efile}State",
    "{http://www.irs.gov/efile}StateAbbreviationCd",
    "{http://www.irs.gov/efile}ProvinceOrState",
    "{http://www.irs.gov/efile}ProvinceOrStateNm"
    ]

countryTags = [
    "{http://www.irs.gov/efile}CountryCd",
    "{http://www.irs.gov/efile}Country"
    ]

csvHeaders = [
    'BusinessName', 'TaxYr',
    'Addr1','Addr2','Addr3', 'Locality',
    'StateorProvince', 'Country', 'PostalCode',
    'AddrType','EIN','YearFormation','NumEmployees','ReturnFile'
    ]

class csvData():
    exists = False

    def __init__(self, yr, refresh=False):
        self.filename = 'build/address_{}.csv'.format(yr)
        fieldnames = csvHeaders
        if os.path.exists(self.filename) and refresh is False:
            self.exists = True
        else:
            self.f = open(self.filename, 'wb')
            self.writer = csv.DictWriter(self.f, fieldnames=fieldnames)
            self.writer.writeheader()
            self.exists = False

    def save_data(self, data):
        for itm in data:
            self.writer.writerow(itm)

    def close(self):
        self.f.close()

def scanFile(irsFile, unknownTags=[], zf=None, data_logger=None):
    if zf is None:
        return [], unknownTags
    else:
        irsFile=zf.open(irsFile)

    try:
        #need to strip BOM marks if they exist

        root = ET.fromstring(irsFile.read().decode('utf-8-sig'))

        # only explicitly grab the root if we passively parse the XML doc
        # tree = ET.parse(irsFile)
        # root = tree.getroot()
    except:
        # log the errors immediately so we have them if thing truely crash later
        if data_logger is not None:
            f = io.StringIO()
            traceback.print_exc(file=f)

            # reset the file pointer to the top
            f.seek(0)
            data_logger.log_validity(irsFile.name, f.read())
            
        logging.warning("failed to read {}".format(irsFile.name))
        #return nothing as if the file was readable
        return [], unknownTags

    parentMap = {c:p for p in root.iter() for c in p}

    knownTags = line1Tags + line2Tags + line3Tags + cityTags + stateTags + zipCodeTags + countryTags
    newUnknownTags = []

    data = []


    # searchNameSpace
    ns = {'efile':'http://www.irs.gov/efile'}
    businessName = []
    for srchTag in businessContentTags:
        # get all parts of the business name
        for addressNode in root.findall('.//efile:' + srchTag, ns):
            for nameComponent in addressNode:
                businessName.append(nameComponent.text)
        # stop looking once we find a valid name
        if len(businessName) > 0:
            businessName =  ' // '.join(businessName)
            break

    ein = ''
    for srchTag in ['EIN']:
        for contentNode in root.findall('.//efile:' + srchTag,  ns):
            ein = contentNode.text
        # stop looking once we find a valid name
        if not ein == '':
            break

    taxYr = ''
    for srchTag in ['TaxYr', 'TaxYear']:
        for contentNode in root.findall('.//efile:' + srchTag,  ns):
            taxYr = contentNode.text
        # stop looking once we find a valid name
        if not taxYr == '':
            break

    # search for the company establishment year
    yrFormation = ''
    for srchTag in ['YearFormation','FormationYr']:
        for contentNode in root.findall('.//efile:' + srchTag,  ns):
            yrFormation = contentNode.text
        # stop looking once we find a valid valuee
        if not yrFormation == '':
            break

    # search for the number of employees
    numEmployees = ''
    for srchTag in ['TotalNbrEmployees','NumberOfEmployees','TotalEmployeeCnt','EmployeeCnt']:
        for contentNode in root.findall('.//efile:' + srchTag,  ns):
            numEmployees = contentNode.text
        # stop looking once we find a valid value
        if not numEmployees == '':
            break

    for srchTag in addressContentTags:
        # return for nodes that contain an address component
        for addressNode in root.findall('.//efile:' + srchTag + '/..',  ns):
            #pe = parentMap[addressNode]
            context =  parentMap[addressNode].tag.replace('{http://www.irs.gov/efile}', '') + "." +  addressNode.tag.replace('{http://www.irs.gov/efile}', '')
            item = {"EIN":ein, "BusinessName":businessName, "TaxYr": taxYr,
                    'AddrType': context, 'NumEmployees': numEmployees, 
                    'YearFormation': yrFormation, 'ReturnFile': os.path.basename(irsFile.name),
                    'PostalCode': None, 'StateorProvince': None, 'Country': None,
                    'Locality': None, 'Addr1': None, 'Addr2': None, 'Addr3': None}

            for addressComponent in addressNode:
                if not addressComponent.tag in knownTags:
                    if not addressComponent.tag in unknownTags:
                        unknownTags += [addressComponent.tag]
                        newUnknownTags += [addressComponent.tag]
                else:
                    # line1Tags + line2Tags + line3Tags + cityTags + stateTags + zipCodeTags + countryTags
                    if addressComponent.tag in zipCodeTags:
                        item["PostalCode"] = addressComponent.text
                    elif addressComponent.tag in stateTags:
                        item["StateorProvince"] = addressComponent.text
                    elif addressComponent.tag in countryTags:
                        item["Country"] = addressComponent.text
                    elif addressComponent.tag in cityTags:
                        item["Locality"] = addressComponent.text
                    elif addressComponent.tag in line1Tags:
                        item["Addr1"] = addressComponent.text
                    elif addressComponent.tag in line2Tags:
                        item["Addr2"] = addressComponent.text
                    elif addressComponent.tag in line3Tags:
                        item["Addr3"] = addressComponent.text
            

            ## the special value "RESTRICTED" is used to indicate redacted info
            if 'Addr1' in item and not item["Addr1"] == "RESTRICTED":
                data.append(item)
            else:
                if not 'Addr1' in item:
                    logging.info(addressComponent.tag, addressComponent.text)
                    logging.info(item)

    if len(newUnknownTags) > 0:
        logging.info(newUnknownTags)

    return data, unknownTags

def scan_year(yr, dbname=':memory:', sampleSize=False, refresh=False):

    ocsv = csvData(yr, refresh=refresh)
    if ocsv.exists is True:
        logging.info(f"skipping the build of a csv for year {yr}, as it already exists")
        return

    logging.info(f"importing tax year {yr}")
    # materialize the file list to keep from re-scanning the dirs
    archivefile = f"tmpdata/irs_f990_{yr}.zip"
    try:
        zf = zipfile.ZipFile(archivefile, "r")
    except FileNotFoundError:
        logging.warning(f"archive {archivefile} not found")
        return

    files = list([d for d in zf.namelist() if d.endswith(".xml")])
    ctr = 0
    unknownTags = []
    data = []
    # delete any existing DB
    dblog = db_logging.DBLOG(dbname=f"data/my_{yr}.db", preserve=False)

    for irsReturn in files:
        (newData, unknownTags) = scanFile(irsReturn, unknownTags=unknownTags, zf=zf, data_logger=dblog)
        data += newData
        ctr += 1
        if (ctr % 10000) == 0:
            logging.debug(".", )
            ocsv.save_data(data)
            dblog.save_data(data)
            data = []

        # only read a sampling of returns
        if sampleSize and sampleSize < ctr:
            break

    ocsv.save_data(data)
    dblog.save_data(data)
    ocsv.close()
    dblog.close()

def years():
    yrs = []
    iyr = 2008
    while iyr < 2022:
        yrs.append(iyr)
        iyr += 1

    return yrs

def main(args):

    if "--refresh" in args:
        refreshData = True
    else:
        refreshData = False

    if "--sampleSize" in args:
        sampleSize = int(args[args.index("--sampleSize") + 1])
    else:
        sampleSize = False

    if "--taxyear" in args:
        taxyrs = [args[args.index("--taxyear") + 1]]
    else:
        taxyrs = years()

    for yr in taxyrs:
        dbname = f"data/filing_addresses_${yr}.db"
        starttm = time.time()
        scan_year(yr, dbname=dbname, sampleSize=sampleSize, refresh=refreshData)
        duration = time.time() - starttm
        logging.info(f"Records for {yr} imported in {duration}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(sys.argv)
    logging.info("All Done")
