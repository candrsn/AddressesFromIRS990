
import sys
import os
import logging
import sqlite3

logger = logging.getLogger(__name__)

class DBLOG():
    db = None

    def __init__(self, dbname, preserve=False):
        if os.path.isfile(dbname) and dbname.endswith(".db"):
            os.remove(dbname)
        self.db = sqlite3.connect(dbname)
        self.setup()

    def setup(self):
        cur = self.db.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS import_errors (fid INTEGER PRIMARY KEY AUTOINCREMENT, xml_file TEXT, msg TEXT, log_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        """)
        cur.execute("""CREATE TABLE IF NOT EXISTS irs_address (
    BusinessName TEXT ,TaxYr TEXT, Addr1 TEXT, Addr2 TEXT, Addr3 TEXT, 
    Locality TEXT ,StateorProvince TEXT, Country TEXT, PostalCode TEXT,
    AddrType TEXT, EIN TEXT, YearFormation TEXT, NumEmployees TEXT, ReturnFile TEXT );
        """)
        # wait for the statements to complete
        assert cur.fetchall() is not None, "failed to create the DB tables"
        self.db.commit()

    def log_download(self, name):
        pass

    def save_data(self, data):
        if len(data) == 0:
            return

        if type(data[0]) is dict:
            # extract the fields from the dict
            flds = list(data[0].keys())
            data = [list(d.values()) for d in data]
        else:
            # use a default series of fields
            flds = ["EIN", "BusinessName", "TaxYr", "AddrType", "NumEmployees", "YearFormation", "ReturnFile", 
                "Addr1", "Addr2", "Addr3", "Locality", "StateorProvince", "Country", "PostalCode"]
        cur = self.db.cursor()
        cur.executemany(f"""INSERT INTO irs_address ({",".join(flds)}) 
            VALUES ({",".join(['?' for d in flds])})""", data)
        self.db.commit()

    def log_validity(self, name, msg):
        cur = self.db.cursor()
        cur.executemany("""INSERT INTO import_errors (xml_file, msg) VALUES (?,?)""", [[name, f"{msg}"]])
        self.db.commit()

    def close(self):
        self.db.commit()
        self.db.close()

def main(args):
    logger.info("All done")

if __name__ == "__main__":
    main(sys.argv)

