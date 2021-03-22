#!/usr/bin/python3

#
# Imports
#

import json
import time
import requests
from lxml import html, etree


#
# Constants
#

PAWS_URL = 'https://www.paws.org/adopt/dogs/'
PETANGO_URL = 'https://www.petango.com/DesktopModules/Pethealth.Petango/Pethealth.Petango.DnnModules.AnimalSearchResult/API/Main/Search'

USERAGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0'
UA_HEADER = {'User-Agent': USERAGENT}
PETANGO_HEADERS = {'ModuleId': '983', 'TabId': '278', 'User-Agent': USERAGENT}

EXCLUDED_BREEDS = [
    'Boxer',
    'Chihuahua',
    'Pit Bull',
    'Staffordshire',
    'Small (under 24 lbs fully grown)'
]

#
# Globals
#

seenPAWS = {}
seen = {}
shelterIdsPetango = [
    '2642'  #PAWS
]


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

        if name not in seenPAWS or seenPAWS[name]['pending'] != pending or seenPAWS[name]['id'] != animalId:
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

    r = requests.post(PETANGO_URL, data=search, headers=PETANGO_HEADERS)
    dogs = r.json()['items']
    delta = False

    for dog in dogs:
        if dog['id'] not in seen:
            seen[dog['id']] = dog

            if any(b in dog['breed'] for b in EXCLUDED_BREEDS):
                continue

            print('%s (Petango-%s-%s) - %s' % (dog['name'], shelterId, dog['id'], dog['breed']))
            delta = True

    if delta:
        alert()

#
# Alert user
#

def alert():
    print(time.strftime('%c'))
    for i in range(0, 5):
        print('\x07', end='', flush=True)
        time.sleep(0.25)
    print()


#
# Main function
#

if __name__ == '__main__':
    while True:
        runPAWS()
        for shelter in shelterIdsPetango:
            runPetangoShelter(shelter)
        time.sleep(1)
