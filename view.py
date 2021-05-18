#!/usr/bin/python3

#
# Imports
#

import json
import time
from datetime import datetime


#
# Globals
#

dogs = {}


#
# Refresh state from file
#

def refresh():
    global dogs
    with open('state.json', 'r') as f:
        dogs = json.loads(f.read())


#
# Search based on multiple criteria
#

def search(animal = None,
           shelter = None,
           name = None,
           breed = None,
           photo = None,
           pending = False,
           provider = None,
           timeFound = None,
           timePending = None,
           timeAdopted = None,
           timeSeen = None,
           includeData = False):
    
    results = []

    for providerId in dogs:
        if provider != None and providerId != provider:
            continue

        for shelterId in dogs[providerId]:
            if shelter != None and shelterId != shelter:
                continue

            for animalId in dogs[providerId][shelterId]:
                if animal != None and animalId != animal:
                    continue

                dog = dogs[providerId][shelterId][animalId]

                if name != None and dog['name'] != name:
                    continue
                if breed != None and breed.lower() not in dog['breed'].lower():
                    continue
                if photo != None and (dog['photo'] != None) != photo:
                    continue
                if pending != None and dog['pending'] != pending:
                    continue
                if timeFound != None and dog['timeFound'] < timeFound:
                    continue
                if timePending != None and dog['timePending'] < timePending:
                    continue
                if timeSeen != None and dog['timeSeen'] < timeSeen:
                    continue

                if not includeData:
                    dog['data'] = ''

                results.append(dog)

    return results


#
# Display search results
#

def display(results,
            animal = True,
            shelter = True,
            name = True,
            breed = True,
            photo = False,
            pending = False,
            provider = True,
            timeFound = False,
            timePending = False,
            timeAdopted = False,
            timeSeen = False,
            includeData = False):
    
    for result in results:
        text = ''

        if name:
            text += '{:<22} '.format(result['name'])
        if pending:
            text += '{:<12} '.format('- PENDING' if result['pending'] else '- AVAILABLE')

        if provider or shelter or animal:
            text += '('
            if provider:
                text += '{:<9}'.format(result['provider'])
                if shelter or animal:
                    text += '-'
            if shelter:
                text += '{:<5}'.format(result['shelterId'])
                if animal:
                    text += '-'
            if animal:
                text += '{:<8}'.format(result['animalId'])
            text += ') '

        if breed:
            text += '- {:<52} '.format(result['breed'])

        now = datetime.now()
        if timeFound:
            text += 'Found: {:<17.17} ago '.format(str(now - datetime.fromtimestamp(result['timeFound'])).split('.')[0])
        if timePending:
            text += 'Pending: {:<17.17} ago '.format(str(now - datetime.fromtimestamp(result['timePending'])).split('.')[0])
        if timeAdopted:
            text += 'Adopted: {:<17.17} ago '.format(str(now - datetime.fromtimestamp(result['timeAdopted'])).split('.')[0])
        if timeSeen:
            text += 'Seen: {:<17.17} ago '.format(str(now - datetime.fromtimestamp(result['timeSeen'])).split('.')[0])

        if photo:
            text += '{}'.format(result['photo'] if result['photo'] != None else 'NO_PHOTO')

        print(text)

#
# Automatically load state on import
#

refresh()
