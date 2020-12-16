import json
import data
import sys

def write(key, hw_text='', hw_photoid=''):
    db = json.load(open(data.LOCAL_DB_FILENAME))
    db.update({key: {'text': hw_text, 'photoid': hw_photoid}})
    json.dump(db, open(data.LOCAL_DB_FILENAME, 'w'))

def read(key=''):
    key = {'all': None}.get(key, key)
    db = json.load(open(data.LOCAL_DB_FILENAME))
    if key:
        return db.get(key, '')
    else:
        return str(db)
    
if __name__=='__main__':
    command = sys.argv[1]
    if command not in ['read', 'write']:
        raise SyntaxError(f"invalid command: should be 'read' or 'write', not '{command}'.")
        
    if len(sys.argv)<3:
        raise SyntaxError(f"invalid amount of arguments for a '{command}' command: expected { {'read': 3, 'write': 4}[command] }, got {str(len(sys.argv))}")
        
    key = sys.argv[2]
    if key not in data.LESSONS_SHORTCUTS+['all']:
        print(sys.argv)
        raise SyntaxError(f"'{key}' is an invalid search key")
        
    target = sys.argv[3] if len(sys.argv)>3 else ''
    if command=='read' and target:
        raise SyntaxError(f"invalid amount of arguments for a 'read' command: expected 3, got {str(len(sys.argv))}")
        
    if len(sys.argv)>4:
        raise SyntaxError(f"invalid amount of arguments for a 'write' command: expected 4, got {str(len(sys.argv))}")
        
    exec(f"print({command}({key}, {target}))")
        
    
        
