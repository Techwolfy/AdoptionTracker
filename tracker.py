#!/usr/bin/python3

#
# Imports
#

import json
import re
import time
import requests
from lxml import html, etree


#
# Constants
#

PAWS_URL = 'https://www.paws.org/adopt/dogs/'
PETANGO_URL = 'https://www.petango.com/DesktopModules/Pethealth.Petango/Pethealth.Petango.DnnModules.AnimalSearchResult/API/Main/Search'
PETFINDER_URL = 'https://www.petfinder.com/search/'
UA_HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0'}

EXCLUDED_BREEDS = [
    'Boxer',
    'Chihuahua',
    'Chow Chow',
    'Pit Bull',
    'Rottweiler',
    'Staffordshire',
    'Small (under 24 lbs fully grown)'
]

PETANGO_GOLDEN_RETRIEVER = '601'


#
# Globals
#

alertEnabled = False
keys = {
    'petfinderToken': '',
    'location': '',
    'sheltersPetango': [],
    'sheltersPetfinder': []
}

seenPAWS = {}
seen = {}


#
# Search PAWS shelter
#

def runPAWS():
    r = requests.get(PAWS_URL, headers=UA_HEADER)
    h = html.document_fromstring(r.text)
    dogs = h.xpath('//section[@class="cards"]//article')
    delta = False

    for dog in dogs:
        animalIdLink = dog.xpath('.//a[@class="card-block__link"]/@href')
        dogData = dog.xpath('.//span[@class="card-block__label"]')

        name = dog.xpath('.//h3[@class="card-block__title"]/text()')[0]
        pending = len(dog.xpath('.//span[@class="card-block__pill"]/text()')) != 0
        animalId = animalIdLink[0].rsplit('=', 1)[-1] if len(animalIdLink) != 0 else '00000000'
        breed = dogData[1].text if len(dogData) > 2 else 'Breed Unknown'

        if name in seenPAWS and seenPAWS[name]['pending'] == pending and seenPAWS[name]['id'] == animalId:
            continue

        seenPAWS[name] = {}
        seenPAWS[name]['id'] = animalId
        seenPAWS[name]['pending'] = pending

        if any(b in breed for b in EXCLUDED_BREEDS):
            continue

        print('%s%s (PAWS-%s) - %s' % (name, (' - Adoption Pending' if pending else ''), animalId, breed))
        delta = True

    if delta:
        alert()


#
# Search Petango shelters
#

def runPetangoShelter(shelterId):
    search = {
        'speciesId': '1',
        'goodWithDogs': False,
        'goodWithCats': False,
        'goodWithChildren': False,
        'mustHavePhoto': False,
        'mustHaveVideo': False,
        'shelterId': shelterId,
        'happyTails': False,
        'lostAnimals': False,
        'moduleId': 983,
        'recordOffset': 0,
        'recordAmount': 100
    }

    r = requests.post(PETANGO_URL, data=search, headers={'ModuleId': '983', 'TabId': '278', **UA_HEADER})
    dogs = r.json()['items']
    delta = False

    for dog in dogs:
        if dog['id'] in seen:
            continue

        seen[dog['id']] = dog

        if any(b in dog['breed'] for b in EXCLUDED_BREEDS):
            continue

        print('%s (Petango-%s-%s) - %s' % (dog['name'], shelterId, dog['id'], dog['breed']))
        delta = True

    if delta:
        alert()


#
# Search Petango by breed
#

def runPetango(location, gender, breedId):
    search = {
        'location': location,
        'distance': '250',
        'speciesId': '1',
        'breedId': breedId,
        'gender': gender,
        'size': '',
        'color': '',
        'goodWithDogs': False,
        'goodWithCats': False,
        'goodWithChildren': False,
        'mustHavePhoto': False,
        'mustHaveVideo': False,
        'declawed': '',
        'happyTails': False,
        'lostAnimals': False,
        'animalId': '',
        'moduleId': 843,
        'recordOffset': 0,
        'recordAmount': 100
    }

    r = requests.post(PETANGO_URL, data=search, headers={'ModuleId': '843', 'TabId': '260', **UA_HEADER})
    dogs = r.json()['items']
    delta = False

    for dog in dogs:
        if dog['id'] in seen:
            continue

        seen[dog['id']] = dog

        if any(b in dog['breed'] for b in EXCLUDED_BREEDS):
            continue

        print('%s (Petango-0000-%s) - %s' % (dog['name'], dog['id'], dog['breed']))
        delta = True

    if delta:
        alert()


#
# Search Petfinder shelters
#

def runPetfinderShelter(shelterId, page=1):
    search = {
        'page': str(page),
        'limit[]': '100',
        'status': 'adoptable',
        'token': keys['petfinderToken'],
        'distance[]': 'Anywhere',
        'type[]': 'dogs',
        'sort[]': 'recently_added',
        'shelter_id[]': shelterId,
        'include_transportable': 'true'
    }

    r = requests.get(PETFINDER_URL, params=search, headers={'X-Requested-With': 'XMLHttpRequest', **UA_HEADER})
    result = r.json()['result']
    dogs = result['animals']
    delta = False

    for dog in dogs:
        if dog['animal']['id'] in seen:
            continue

        seen[dog['animal']['id']] = dog

        if any(b in dog['animal']['breeds_label'] for b in EXCLUDED_BREEDS):
            continue

        print('%s (Petfinder-%s-%s) - %s' % (dog['animal']['name'], dog['organization']['display_id'], dog['animal']['id'], dog['animal']['breeds_label']))
        delta = True

    if page < result['pagination']['total_pages']:
        runPetfinderShelter(shelterId, page + 1)

    if delta:
        alert()

#
# Alert user
#

def alert():
    if alertEnabled:
        print(time.strftime('%c'))
        for i in range(0, 5):
            print('\x07', end='', flush=True)
            time.sleep(0.25)
    print()


#
# Display waiting spinner
#

def spin(seconds):
    sequence = ['|', '/', '-', '\\']
    for i in range(0, seconds * 4):
        print('%s %s (next update in: %ds)  ' % (sequence[i % 4], time.strftime('%c'), seconds - (i / 4)), end='\r')
        time.sleep(0.25)
    print(' ' * 80, end='\r')


#
# Load keys from file
#

def loadKeys():
    global keys
    with open('keys.json', 'r') as f:
        raw = f.read()
        parsed = re.sub('#.*', '', raw)
        keys = json.loads(parsed)


#
# Main function
#

if __name__ == '__main__':
    loadKeys()

    while True:

        runPAWS()

        for shelter in keys['sheltersPetango']:
            runPetangoShelter(shelter)

        runPetango(keys['location'], 'F', PETANGO_GOLDEN_RETRIEVER)

        for shelter in keys['sheltersPetfinder']:
            runPetfinderShelter(shelter)

        alertEnabled = True
        spin(30)
