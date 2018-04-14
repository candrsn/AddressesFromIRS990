### extract_address.py

import sys
import os
import glob
import xml.etree.ElementTree as ET
import csv

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
    "{http://www.irs.gov/efile}ProvinceOrStateNm",]

countryTags = [
    "{http://www.irs.gov/efile}CountryCd",
    "{http://www.irs.gov/efile}Country"
]

def save_data(data, yr):
    #fieldnames = data[0].keys()
    fieldnames = ['BusinessName', 'TaxYr',
            'Addr1','Addr2','Addr3', 'Locality',
            'StateorProvince', 'Country', 'PostalCode',
            'EIN','AddrType']

    destFile = 'address_{}.csv'.format(yr)
    if os.path.exists(destFile):
        needHdr = False
    else:
        needHdr = True
    with open(destFile, 'at') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if needHdr:
            writer.writeheader()
        for itm in data:
            writer.writerow(itm)

def scanFile(irsFile, unknownTags=[]):
    try:
        tree = ET.parse(irsFile)
        root = tree.getroot()
    except:
        print("failed to read {}".format(irsFile))
        #return nothing as if the file was readable
        return [], unknownTags

    parentMap = {c:p for p in tree.iter() for c in p}

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

    for srchTag in addressContentTags:
        # return for nodes that contain an address component
        for addressNode in root.findall('.//efile:' + srchTag + '/..',  ns):
            #pe = parentMap[addressNode]
            context =  parentMap[addressNode].tag.replace('{http://www.irs.gov/efile}', '') + "." +  addressNode.tag.replace('{http://www.irs.gov/efile}', '')
            item = {"EIN":ein, "BusinessName":businessName, "TaxYr": taxYr,
                'AddrType': context}
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
            if 'Addr1' in item and not item["Addr1"] == "RESTRICTED":
                data.append(item)
            else:
                if not 'Addr1' in item:
                    print(addressComponent.tag, addressComponent.text)
                    print(item)

    if len(newUnknownTags) > 0:
        print(newUnknownTags)

    return data, unknownTags

def scan_year(yr, sampleSize=False):
    files = glob.glob('data/' + yr + '/*xml')
    ctr = 0
    unknownTags = []
    data = []

    for irsReturn in files:
        newData, unknownTags = scanFile(irsReturn, unknownTags)
        data += newData
        ctr += 1
        if (ctr % 1000) == 0:
            print(".", )
            save_data(data, yr)
            data = []

        # only read a sampling of returns
        if sampleSize and sampleSize < ctr:
            break
    save_data(data, yr)

def main(args):
    #scanFile('data/2017/201700069349100100_public.xml')
    if len(args) > 0:
        scan_year(args[0], 1200)
    else:
        scan_year('2017')

if __name__ == "__main__":
    main(sys.argv[1:])
    print("All Done")
