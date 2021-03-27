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

INTERVAL = 30

PETANGO_GOLDEN_RETRIEVER = '601'


#
# Globals
#

alertEnabled = False
alertTriggered = False

keys = {
    'petfinderToken': '',
    'location': '',
    'sheltersPetango': [],
    'sheltersPetfinder': []
}

seen = {}


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
# Handle new dog
#

def handleDog(animalId, shelterId, name, breed, photoUrl, adoptionPending, provider, data):
    global alertTriggered

    if animalId in seen and seen[animalId]['pending'] == adoptionPending:
        seen[animalId]['timeSeen'] = time.time()
        return

    seen[animalId] = {}
    seen[animalId]['animalId'] = animalId
    seen[animalId]['shelterId'] = shelterId
    seen[animalId]['name'] = name
    seen[animalId]['breed'] = breed
    seen[animalId]['photo'] = photoUrl,
    seen[animalId]['pending'] = adoptionPending
    seen[animalId]['provider'] = provider
    seen[animalId]['timeFound'] = time.time()
    seen[animalId]['timeAdopted'] = 0
    seen[animalId]['timeSeen'] = time.time()
    seen[animalId]['data'] = data

    if any(b in breed for b in EXCLUDED_BREEDS):
        return

    with open('dogs/%s.json' % animalId, 'w') as f:
        f.write(json.dumps(seen[animalId]))
    if photoUrl:
        image = requests.get(photoUrl)
        ext = image.headers['Content-Type'].rsplit('/', 1)[-1]
        with open('dogs/%s.%s' % (animalId, ext), 'wb') as f:
            f.write(image.content)

    pendingString = ' - Adoption Pending' if adoptionPending else ''
    print('%s%s (%s-%s-%s) - %s' % (name, pendingString, provider, shelterId, animalId, breed))
    alertTriggered = True


#
# Handle adoped dogs
#

def checkDogs():
    now = time.time()
    delta = False

    for animalId in list(seen):
        if now - seen[animalId]['timeSeen'] < INTERVAL * 2:
            continue

        dog = seen.pop(animalId)
        dog['timeAdopted'] = now

        with open('dogs/%s.json' % dog['animalId'], 'w') as f:
            f.write(json.dumps(dog))

        hours = (now - dog['timeSeen']) / 3600
        print('%s - ADOPTED in %.2fh (%s-%s-%s) - %s' % (dog['name'], hours, dog['provider'], dog['shelterId'], dog['animalId'], dog['breed']))
        delta = True

    if delta:
        print()

#
# Search PAWS shelter
#

def runPAWS():
    r = requests.get(PAWS_URL, headers=UA_HEADER)
    h = html.document_fromstring(r.text)
    dogs = h.xpath('//section[@class="cards"]//article')

    for dog in dogs:
        dogData = dog.xpath('.//span[@class="card-block__label"]')

        animalId = dog.xpath('@id')[0].split('-')[1]
        name = dog.xpath('.//h3[@class="card-block__title"]/text()')[0]
        photo = dog.xpath('.//img[@class="card-block__img-animal"]/@src')[0]
        pending = len(dog.xpath('.//span[@class="card-block__pill"]/text()')) != 0
        breed = dogData[1].text if len(dogData) > 2 else 'Breed Unknown'

        handleDog(animalId + '-PAWS',
                  'PAWS',
                  name,
                  breed,
                  photo,
                  pending,
                  'PAWS',
                  etree.tostring(dog, encoding='unicode'))

    if alertTriggered:
        print()


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

    for dog in dogs:
        handleDog(dog['id'],
                  shelterId,
                  dog['name'],
                  dog['breed'],
                  dog['photo'],
                  False,
                  'Petango',
                  dog)

    if alertTriggered:
        print()


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

    for dog in dogs:
        handleDog(dog['id'],
                  '0000',
                  dog['name'],
                  dog['breed'],
                  dog['photo'],
                  False,
                  'Petango',
                  dog)

    if alertTriggered:
        print()


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

    for dog in dogs:
        handleDog(dog['animal']['id'],
                  dog['organization']['display_id'],
                  dog['animal']['name'],
                  dog['animal']['breeds_label'],
                  dog['animal']['primary_photo_url'],
                  False,
                  'Petfinder',
                  dog)

    if page < result['pagination']['total_pages']:
        runPetfinderShelter(shelterId, page + 1)

    if alertTriggered:
        print()


#
# Alert user
#

def handleAlert():
    global alertEnabled
    global alertTriggered

    if not alertEnabled or not alertTriggered:
        alertEnabled = True
        alertTriggered = False
        return

    print(time.strftime('%c'))

    for i in range(0, 5):
        print('\x07', end='', flush=True)
        time.sleep(0.25)

    print()
    alertTriggered = False


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

        checkDogs()

        handleAlert()
        spin(INTERVAL)
