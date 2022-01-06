import json
from termcolor import cprint

with open('data/refmt/meta_to_oredict.json', 'r') as f:
    meta_to_oredict = json.load(f)

if __name__ == '__main__':
    while True:
        cprint('> ', 'green', end='')
        entry = input()
        if entry in meta_to_oredict:
            print(meta_to_oredict[entry])
        else:
            cprint('UNRECOGNIZED', 'red')
