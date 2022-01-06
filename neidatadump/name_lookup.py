import json
from collections import defaultdict
from termcolor import cprint

# Startup imports
with open('data/refmt/itemlist.json', 'r') as f:
    db = json.load(f)

with open('data/refmt/fluids.json', 'r') as f:
    db.update(json.load(f))

rev = defaultdict(list)
for key, value in db.items():
    rev[value].append(key)


def meta_to_name(meta):
    return db[meta]

def name_to_metas(name):
    return rev[name]


if __name__ == '__main__':
    while True:
        cprint('> ', 'green', end='')
        entry = input()
        sp = entry.split(' ')
        typ, name = sp[0], ' '.join(sp[1:])
        if typ == 'f':
            if name in db:
                print(db[name])
        elif typ == 'b':
            name = name.strip().lower().title()
            if name in rev:
                print(rev[name])
        else:
            cprint('Unrecognized mode. f for ID -> name, b for name -> IDs', 'red')
