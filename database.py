import json

DB_FILENAME = 'hw.json'

def write(key, hw_text='', hw_photoid=''):
    db = json.load(open('hw.json'))
    db.update({key: {'text': hw_text, 'photoid': hw_photoid}})
    json.dump(db, open('hw.json', 'w'))

def read(key=''):
    db = json.load(open('hw.json'))
    if key:
        return db.get(key, '')
    else:
        return db
