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
    'excludedBreeds': [],
    'sheltersPetango': [],
    'sheltersPetfinder': []
}

seen = {}


#
# Load state from file
#

def loadState():
    global keys
    global seen

    with open('keys.json', 'r') as f:
        raw = f.read()
        parsed = re.sub('#.*', '', raw)
        keys = json.loads(parsed)

    try:
        with open('state.json', 'r') as f:
            state = f.read()
            seen = json.loads(state)

        for provider in seen:
            for shelterId in seen[provider]:
                for animalId in seen[provider][shelterId]:
                    printDog(seen[provider][shelterId][animalId])
                print()

    except FileNotFoundError:
        pass


#
# Save state to file
#

def saveState():
    with open('state.json', 'w') as f:
        f.write(json.dumps(seen))


#
# Display dog information
#

def printDog(dog):
    adoptedString = ''
    if dog['timeAdopted'] != 0:
        adoptedTime = dog['timeAdopted'] - dog['timeFound']
        adoptedString = ' - ADOPTED [in %dd %dh %dm]' % (int(adoptedTime / 86400), int((adoptedTime % 86400) / 3600), int((adoptedTime % 3600) / 60))
    elif dog['pending']:
        adoptedString = ' - Adoption Pending'
    print('%s%s (%s-%s-%s) - %s' % (dog['name'], adoptedString, dog['provider'], dog['shelterId'], dog['animalId'], dog['breed']))


#
# Handle new dog
#

def handleDog(provider, shelterId, animalId, name, breed, photoUrl, adoptionPending, data):
    global alertTriggered

    if provider not in seen:
        seen[provider] = {}

    if shelterId not in seen[provider]:
        seen[provider][shelterId] = {}

    if animalId in seen[provider][shelterId] and seen[provider][shelterId][animalId]['pending'] == adoptionPending:
        seen[provider][shelterId][animalId]['timeSeen'] = time.time()
        return

    seen[provider][shelterId][animalId] = {
        'animalId': animalId,
        'shelterId': shelterId,
        'name': name,
        'breed': breed,
        'photo': photoUrl,
        'pending': adoptionPending,
        'provider': provider,
        'timeFound': time.time(),
        'timeAdopted': 0,
        'timeSeen': time.time(),
        'data': data
    }

    if any(b in breed for b in keys['excludedBreeds']):
        return

    with open('dogs/%s.json' % animalId, 'w') as f:
        f.write(json.dumps(seen[provider][shelterId][animalId]))
    if photoUrl:
        image = requests.get(photoUrl)
        ext = image.headers['Content-Type'].rsplit('/', 1)[-1]
        with open('dogs/%s.%s' % (animalId, ext), 'wb') as f:
            f.write(image.content)

    printDog(seen[provider][shelterId][animalId])
    alertTriggered = True


#
# Handle adoped dogs
#

def checkDogs():
    now = time.time()
    delta = False

    for provider in seen:
        for shelterId in seen[provider]:
            for animalId in list(seen[provider][shelterId]):
                if now - seen[provider][shelterId][animalId]['timeSeen'] < INTERVAL * 4:
                    continue

                dog = seen[provider][shelterId].pop(animalId)
                dog['timeAdopted'] = now

                with open('dogs/%s.json' % dog['animalId'], 'w') as f:
                    f.write(json.dumps(dog))

                printDog(dog)
                delta = True

    if delta:
        print()

#
# Search PAWS shelter
#

def runPAWS():
    r = requests.get(PAWS_URL, headers=UA_HEADER)
    if r.status_code != 200:
        print('Request failed: %d, %s, %s' % (r.status_code, r.url, r.text))
        return
    h = html.document_fromstring(r.text)
    dogs = h.xpath('//section[@class="cards"]//article')

    for dog in dogs:
        dogData = dog.xpath('.//span[@class="card-block__label"]')

        animalId = dog.xpath('@id')[0].split('-')[1]
        name = dog.xpath('.//h3[@class="card-block__title"]/text()')[0]
        photo = dog.xpath('.//img[@class="card-block__img-animal"]/@src')[0]
        pending = len(dog.xpath('.//span[@class="card-block__pill"]/text()')) != 0
        breed = dogData[1].text if len(dogData) > 2 else 'Breed Unknown'

        handleDog('PAWS',
                  '0000',
                  animalId + '-PAWS',
                  name,
                  breed,
                  photo,
                  pending,
                  etree.tostring(dog, encoding='unicode'))


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
    if r.status_code != 200:
        print('Request failed: %d, %s, %s' % (r.status_code, r.url, r.text))
        return
    dogs = r.json()['items']

    delta = False
    for dog in dogs:
        delta = handleDog('Petango',
                          str(shelterId),
                          str(dog['id']),
                          dog['name'],
                          dog['breed'],
                          dog['photo'],
                          False,
                          dog)


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
    if r.status_code != 200:
        print('Request failed: %d, %s, %s' % (r.status_code, r.url, r.text))
        return
    dogs = r.json()['items']

    for dog in dogs:
        handleDog('Petango',
                  '0000',
                  str(dog['id']),
                  dog['name'],
                  dog['breed'],
                  dog['photo'],
                  False,
                  dog)


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
    if r.status_code != 200:
        print('Request failed: %d, %s, %s' % (r.status_code, r.url, r.text))
        return
    result = r.json()['result']
    dogs = result['animals']

    for dog in dogs:
        handleDog('Petfinder',
                  shelterId,
                  str(dog['animal']['id']),
                  dog['animal']['name'],
                  dog['animal']['breeds_label'],
                  dog['animal']['primary_photo_url'],
                  False,
                  dog)

    if page < result['pagination']['total_pages']:
        runPetfinderShelter(shelterId, page + 1)


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
    loadState()

    while True:
        runPAWS()

        for shelter in keys['sheltersPetango']:
            runPetangoShelter(shelter)
        runPetango(keys['location'], 'F', PETANGO_GOLDEN_RETRIEVER)

        for shelter in keys['sheltersPetfinder']:
            runPetfinderShelter(shelter)

        checkDogs()

        handleAlert()
        saveState()
        spin(INTERVAL)
