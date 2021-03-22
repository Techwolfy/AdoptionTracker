#!/usr/bin/python3

import time
import requests
from lxml import html, etree

url = 'https://www.paws.org/adopt/dogs/'
headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0'}

#print(etree.tostring(h, encoding='unicode', pretty_print=True))

seen = {}

while True:
    r = requests.get(url, headers=headers)
    h = html.document_fromstring(r.text)
    dogs = h.xpath('//section[@class="cards"]//article')

    alert = False
    for dog in dogs:
        animalIdLink = dog.xpath('.//a[@class="card-block__link"]/@href')
        name = dog.xpath('.//h3[@class="card-block__title"]/text()')[0]
        pending = len(dog.xpath('.//span[@class="card-block__pill"]/text()')) != 0
        animalId = ''
        if len(animalIdLink) != 0:
            animalId = animalIdLink[0].rsplit('=', 1)[-1]

        if name not in seen or seen[name]['pending'] != pending or seen[name]['id'] != animalId:
            seen[name] = {}
            seen[name]['id'] = animalId
            seen[name]['pending'] = pending
            print(name + (' - Adoption Pending' if pending else '') + ' (' + animalId + ')')
            alert = True

    if alert:
        print(time.strftime('%c'))
        for i in range(0, 5):
            print('\x07', end='', flush=True)
            time.sleep(0.25)
        alert = False

    time.sleep(1)
