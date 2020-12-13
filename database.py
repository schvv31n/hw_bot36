import json
import data

def write(key, hw_text='', hw_photoid=''):
    db = json.load(open(data.LOCAL_DB_FILENAME))
    db.update({key: {'text': hw_text, 'photoid': hw_photoid}})
    json.dump(db, open(data.LOCAL_DB_FILENAME, 'w'))

def read(key=''):
    db = json.load(open(data.LOCAL_DB_FILENAME))
    if key:
        return db.get(key, '')
    else:
        return '\n'.join([k+' - '+v for k, v in db.items()])
