import itertools
import json
import os
import pickle
import time
import traceback
from collections import OrderedDict, defaultdict
from pathlib import Path

from termcolor import cprint

# TODO: Deal with circular dependency
# This assumes fluid.json and itemlist.json are written at time of import
# It is used in recipes.json generation, so this check should happen down there, not up here
from name_lookup import name_to_metas, meta_to_name


if __name__ == '__main__':
    MC_PATH = Path('/home/agent/.local/share/multimc/instances/GTNH Multiplayer/.minecraft')
    CACHE_PATH = Path('data/cache/')
    FMT_PATH = Path('data/refmt/')

    prog_start = time.time()
    timelog = lambda *args, **kwargs: print(f'[{round(time.time()-prog_start, 1)}]', *args, **kwargs)

    CACHE_PATH.mkdir(parents=True, exist_ok=True)
    FMT_PATH.mkdir(parents=True, exist_ok=True)

    timelog('starting data load...')

    to_load = [
        'recipes.json',
        'oredictionary.json',
        'itemlist.json',
    ]
    all_data = {}
    for file in to_load:
        timelog(f'loading {file}')
        pickled_json_path = (CACHE_PATH / file)
        if pickled_json_path.exists():
            with open(pickled_json_path, 'rb') as f:
                db = pickle.load(f)
        else:
            with open(MC_PATH / file, 'r') as f:
                db = json.load(f)
            with open(pickled_json_path, 'wb') as f:
                pickle.dump(db, f)

        all_data[file.split('.')[0]] = db

    timelog(f'data loaded!')


    ### itemlist.json
    # Convert names to gt.thing.item:500 instead of separate keys
    # Turn itemlist into a bona-fide lookup table
    new_itemlist_path = FMT_PATH / 'itemlist.json'
    item_lookup = {}
    for item in all_data['itemlist']['items']:
        itemstr = f'{item["item"]["id"]}:{item["item"]["metadata"]}'
        if 'name' in item:
            item_lookup[itemstr] = item['name']
        else:
            cprint(f'Missing name for {itemstr}', 'red')
    with open(FMT_PATH / 'itemlist.json', 'w') as f:
        json.dump(item_lookup, f)


    ### oredictionary.json
    # Because of how recipes are stored, want to do UUID -> oredict
    meta_to_oredict_path = FMT_PATH / 'meta_to_oredict.json'
    if not meta_to_oredict_path.exists():
        oredict_lookup = {}
        for d in all_data['oredictionary']['ore_dictionary']:
            oredict_lookup.update({f'{x["id"]}:{x["metadata"]}': d['tag'] for x in d['entries']})
        with open(meta_to_oredict_path, 'w') as f:
            json.dump(oredict_lookup, f)

    # Also do oredict -> UUIDs
    oredict_to_metas_path = FMT_PATH / 'oredict_to_metas.json'
    if not oredict_to_metas_path.exists():
        # I know I'm throwing away some stuff with set comprehension, but I'll fix this later if there are major problems
        metas_lookup = {
            x['tag']: list(
                {f'{y["id"]}:{y["metadata"]}' for y in x['entries']}
            )
            for x in all_data['oredictionary']['ore_dictionary']
        }
        with open(oredict_to_metas_path, 'w') as f:
            json.dump(metas_lookup, f)


    ### recipes.json
    # Fluid lookups
    fluid_lookup_path = FMT_PATH / 'fluids.json'
    gtfluid_to_liquid = {}
    for group in all_data['recipes']['handlers']:
        if group['handler'] == 'Fluid Canning Machine' and group.get('Gregtech', False):
            failed_lookups = 0
            for recipe in group['recipes']:
                # Convert input can name. If it follows "XYZ cell" then mark the fluid type as XYZ
                input_can = recipe['inputs'][0]['items'][0]['item']
                input_meta = f'{input_can["id"]}:{input_can["metadata"]}'
                try:
                    input_name = meta_to_name(input_meta)
                    if input_name[-4:] == 'Cell' and input_name[:6] != 'Molten' and input_name[:5] != 'Empty':
                        # It's a valid name, look up the FluidDisplay meta number
                        if len(recipe['outputs']) == 2:
                            for output_item in recipe['outputs']:
                                if output_item['items'][0]['item']['id'] == 'gt.GregTech_FluidDisplay':
                                    output_fluid = output_item['items'][0]['item']
                                    output_meta = f'{output_fluid["id"]}:{output_fluid["metadata"]}'
                                    gtfluid_to_liquid[output_meta] = input_name.split(' Cell')[0]
                except KeyError:
                    # cprint(f'{input_meta}', 'red')
                    failed_lookups += 1
            # cprint(f'Failed lookups: {failed_lookups}', 'red')
            break

    # Sort fluids by name for easy checking afterwards
    # gtfluid_to_liquid = OrderedDict(sorted(gtfluid_to_liquid.items(), key=lambda x: x[1]))

    with open(fluid_lookup_path, 'w') as f:
        json.dump(gtfluid_to_liquid, f)


    ### name_to_gt.json
    # Invert fluids and items
    name_to_gt_path = FMT_PATH / 'name_to_gt.json'
    if not name_to_gt_path.exists():
        name_to_gt = defaultdict(list)
        for gt, name in gtfluid_to_liquid.items():
            name_to_gt[name].append(gt)
        for gt, name in item_lookup.items():
            name_to_gt[name].append(gt)

        with open(name_to_gt_path, 'w') as f:
            json.dump(name_to_gt, f)


    ### Rest of recipes.json
    # Load known lookups to make sure recipes will work at runtime
    # Strip relx rely
    # Flatten info key
    # Strip description
    # Compress item info in a similar manner to itemlist

    # Most GT machines (should) have the same standard handling, so process those first
    new_recipes_path = FMT_PATH / 'recipes.json'
    if not new_recipes_path.exists():
        standardized_machines = {
            'Compressor',
            'Extractor',
            'Rock Breaker',
            'Replicator',
            'Plasma Arc Furnace',
            'Arc Furnace',
            'Forming Press',
            'Precision Laser Engraver',
            'Mixer',
            'Autoclave',
            'Electromagnetic Polarizer',
            'Chemical Bath',
            'Fluid Canning Machine',
            'Brewing Machine',
            'Fluid Heater',
            'Distillery',
            'Fermenter',
            'Fluid Solidifier',
            'Fluid Extractor',
            'Fusion Reactor',
            'Centrifuge',
            'Electrolyzer',
            'Blast Furnace',
            'Primitive Blast Furnace',
            'Implosion Compressor',
            'Vacuum Freezer',
            'Chemical Reactor',
            'Large Chemical Reactor',
            'Distillation Tower',
            'Oil Cracker',
            'Pyrolyse Oven',
            'Wiremill',
            'Bending Machine',
            'Alloy Smelter',
            'Assembler',
            'Circuit Assembler',
            'Canning Machine',
            'Cutting Machine',
            'Slicing Machine',
            'Extruder',
            'Forge Hammer',
            'Amplifabricator',
            'Mass Fabrication'
        }
        special_machines = {
            # Most items are not in NEI
            'Ore Washing Plant',
            'Thermal Centrifuge',
            'Scanner',
            'Printer',
            'Sifter',
            'Electromagnetic Separator',
            'Pulverization',
            # Not much point in adding; not usually used in machine paths
            'Packager',
            'Unpackager',
            'Lathe', # Often worse than just extruding
            # Never heard of these
            'CNC Machine',
            # Generators don't show output EU yet
            'Combustion Generator Fuels',
            'Extreme Diesel Engine Fuel',
            'Gas Turbine Fuel',
            'Semifluid Boiler Fuels',
            'Plasma Generator Fuels',
            'Magic Energy Absorber Fuels',
            'Naquadah Reactor MkI',
            'Naquadah Reactor MkII',
            'Fluid Naquadah Reactor'
            'Naquadah Reactor MkIV',
            'Naquadah Reactor MkV',
            'Large Boiler', # This one does show burn time in description
            'Rocket Engine Fuel',
        }
        recipes = defaultdict(list)
        machine_errors = defaultdict(int)
        machine_successes = defaultdict(int)
        keyerror_types = defaultdict(int)
        for group in all_data['recipes']['handlers']:
            machine = group['handler']
            if machine in standardized_machines:
                for recipe in group['recipes']:
                    try:
                        new_rec = {}
                        new_rec['eut'] = recipe['info']['EUrate']
                        new_rec['dur'] = recipe['info']['duration']
                        new_rec['I'] = []
                        new_rec['O'] = []
                        for inp in recipe['inputs']:
                            # "items" field is a list of oredict-viable dicts
                            # in general, I want to accept the gt metaitem instead of another type
                            # it would be nice if I could get the oredict key, but I don't think that was scraped from recipes
                            new_rec['I'].append([
                                [f"{x['item']['id']}:{x['item']['metadata']}" for x in inp['items']],
                                inp['items'][0]['count'] # This shouldn't change with oredict
                            ])
                        for out in recipe['outputs']:
                            new_rec['O'].append([
                                [f"{x['item']['id']}:{x['item']['metadata']}" for x in out['items']],
                                out['items'][0]['count']
                            ])
                        recipes[machine].append(new_rec)
                        machine_successes[machine] += 1
                    except KeyError as e:
                        machine_errors[machine] += 1
                        bad_key = traceback.format_exc().strip().split('\n')[-1].split('KeyError: ')[-1].strip("'")
                        keyerror_types[bad_key] += 1
                        continue

        cprint('Key lookup failures:', 'red')
        print(json.dumps(machine_errors, indent=4))
        cprint('Key lookup failure types:', 'red')
        print(json.dumps(keyerror_types, indent=4))

        timelog('Writing recipes.json...')
        with open(new_recipes_path, 'w') as f:
            json.dump(recipes, f, indent=4)

    ### Recipe I/O hashmap
    # Want {machine: [[inputs], [outputs], [recipe_indices_in_machine]]}
    # I/O will be used to make a tuple(frozenset, frozenset) lookup
    recipe_io_path = FMT_PATH / 'recipe_io_lookup.json'
    if 'recipes' in globals():
        timelog('Making recipe lookup tables based on I/O. (This is gonna take a while...)')
        recipe_io_map = {} # {machine: {tuple(frozenset, frozenset): [recipe_indices]}}
        for machine in recipes:
            recipe_lookup = defaultdict(list)
            machine_rec = recipes[machine]
            for i, rec in enumerate(machine_rec):
                # For I/O alternatives, need to list all of them (unfortunately)
                # This means using itertools.product
                # In the future I'll handle oredict properly TODO:
                I_maps = itertools.product(*[x[0] for x in rec['I']])
                O_maps = itertools.product(*[x[0] for x in rec['O']])
                for I_specific, O_specific in itertools.product(I_maps, O_maps):
                    recipe_lookup[(tuple(I_specific), tuple(O_specific))].append(i)

            recipe_io_map[machine] = [
                [io[0], io[1], machines]
                for io, machines in recipe_lookup.items()
            ]

        with open(recipe_io_path, 'w') as f:
            json.dump(recipe_io_map, f, indent=4)

    timelog('processing complete. deallocating memory...')