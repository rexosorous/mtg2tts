# python standard libraries
import getopt
import json
import re
import sys

# local modules
import Scryfall



'''
i don't feel like commenting this out well. i'm pretty tired.
but essentially, this takes any deck list generated for importing to MTG Arena (only tested with tappedout.net),
pulls data (mainly card pictures) from scryfall, and then makes a json that tabletop simulator uses to spawn the decks
also spawns in a life counter and an endless supply of dice as those are almost always used in mtg games
'''



class CardsNotFoundError(Exception):
    '''
    Thrown if Scryfall returns that it hasn't found some cards for whatever reason

    Args:
        not_found (list[dict]): all the cards that couldn't be found (from parser)
        piles (dict): the piles that were able to be generated
    '''
    def __init__(self, not_found: list[dict], piles: dict):
        self.not_found = not_found
        self.piles = piles
        super().__init__(f'Could not find the following cards: {self.not_found}')



'''
Takes a decklist that follows the form "<quantity> <card name> (<set>) <collector number>\n" and translates it into a tabletop simulator readable json

Command Line Usage:
    py Converter.py -i 'input_file.txt' -o 'output_file.json' -s 'someurl.com/image.png'
    if -i and -o are not provided, it will defaul to -i 'deck.txt' and -o 'deck.json'

Library Usage:
    for a high level function, you can call decklist_to_tts() like

        import json
        import Converter
        with open('deck.txt', 'r') as file:
            tts_json = Converter.decklist_to_tts(file.read())
        with open('deck.json', 'w+') as file:
            json.dump(tts_json, file)

    if you want more granular control over the flow and wish to intercept data as it passes between functions you can do the following (this is essentially what decklist_to_tts() does anyway)

        import json
        with open('deck.txt', 'r') as file:
            raw = file.read()
        decklist = Converter.parse(raw)
        piles = Converter.generate_cards(decklist)
        tts_json = Converter.to_tts_json(piles)
        with open('deck.json', 'w+') as file:
            json.dump(tts_json, file)
'''



def _find_in_decklist(decklist: list[dict], card: dict) -> dict:
    '''
    Utility function to find elements in a list of dicts
    Searches by set and num or name

    Args:
        decklist (list[dict]): the list to search in
        card (dict): what to search for

    Returns:
        (dict): the found element
    '''
    # return [x for x in decklist if x['set'] == (card['set'] and x['num'] == card['collector_number']) or x['name'] == card['name']][0]
    return list(filter(lambda n: (n['set'] == card['set'] and n['num'] == card['collector_number']) or n['name'] == card['name'], decklist))[0]



def parse(deck_str: str) -> list[dict]:
    '''
    Parses a raw deck string using regex and converts them into jsons based on their regex group

    Args:
        deck_str (str): raw deck string

    Returns:
        decklist (list[dict])
    '''
    REGEX = "(?P<qty>\d+) (?P<name>[\w\d :&'/,-]+)(?: \((?P<set>\w+)\)|$)(?: (?P<num>\w+))?"
    decklist = list()

    deck_str_split = deck_str.split('\n\nSIDEBOARD:\n')
    for parsed in re.finditer(REGEX, deck_str_split[0]):
        card = parsed.groupdict()
        card['board'] = 'mainboard'
        card['raw'] = parsed[0]
        decklist.append(card)
    if len(deck_str_split) == 2:
        for parsed in re.finditer(REGEX, deck_str_split[1]):
            card = parsed.groupdict()
            card['board'] = 'sideboard'
            card['raw'] = parsed[0]
            decklist.append(card)

    return decklist



def generate_cards(decklist: list[dict], sleeve: str = 'http://3.219.233.7/images/backs/0aeebaf5-8c7d-4636-9e82-8c27447861f7.jpg') -> dict:
    '''
    Searches for cards via the Scryfall API and parses the response for the relevant data

    Args:
        decklist (list[dict]): keys = qty, name, set, num
        sleeve (str): url to an image to use as a deck sleeve / card back

    Returns:
        piles (dict): keys = mainboard, sideboard, other | each reperesenting a different pile to be generated in TTS

    Raises:
        CardsNotFoundError: if one or more cards aren't found
    '''
    piles = {
        'mainboard': list(),
        'sideboard': list(),
        'other': list()
    }

    token_ids = list()

    response = Scryfall.bulk_search(decklist)
    for card_data in response['data']:
        input_card = _find_in_decklist(decklist, card_data)
        if card_data['lang'] != 'en':
            print(card_data['name'])
            card_data = Scryfall.exact_search(card_data['set'], card_data['collector_number'])

        # does this produce tokens?
        if 'all_parts' in card_data:
            token_ids += [token['id'] for token in card_data['all_parts'] if token['component'] == 'token']

        # is this a single faced card?
        if 'image_uris' in card_data:
            front_image_url = card_data['image_uris']['png']
        else: # is this a dual faced card?
            front_image_url = card_data['card_faces'][0]['image_uris']['png']
            piles['other'].append({ # add dual faced card to other pile
                'name': card_data['name'],
                'qty': input_card['qty'],
                'front_image_url': front_image_url,
                'back_image_url': card_data['card_faces'][1]['image_uris']['png']
            })

        # add the card to the appropariate pile
        piles[input_card['board']].append({
            'name': card_data['name'],
            'qty': input_card['qty'],
            'front_image_url': front_image_url,
            'back_image_url': sleeve
        })

    # handle tokens
    for card_data in Scryfall.token_search(token_ids)['data']:
        piles['other'].append({
            'name': card_data['name'],
            'qty': 1,
            'front_image_url': card_data['image_uris']['png'],
            'back_image_url': sleeve
        })

    if not_found := [_find_in_decklist(decklist, x) for x in response['not_found']]:
        raise CardsNotFoundError(not_found, piles)

    return piles



def to_tts_json(piles: dict) -> dict:
    '''
    Creates the TTS readable json file

    Args:
        piles (dict): return data from generate_cards()

    Returns:
        deck_json (dict)
    '''
    pos = 0
    deck_json = {
        'ObjectStates': []
    }

    mainboard = _gen_tts_pile('Mainboard', piles['mainboard'], pos)
    deck_json['ObjectStates'].append(mainboard)

    if piles['sideboard']:
        pos += 3
        sideboard = _gen_tts_pile('Sideboard', piles['sideboard'], pos)
        deck_json['ObjectStates'].append(sideboard)

    if piles['other']:
        pos += 3
        otherboard = _gen_tts_pile('Tokens & Dual Faced Cards', piles['other'], pos)
        deck_json['ObjectStates'].append(otherboard)

    return deck_json



def _gen_tts_pile(name: str, decklist: list[dict], pos: int) -> dict:
    '''
    Creates TTS readable json of a deck (pile)
    Must be called from to_tts_json() because this does not have the outer json wrapping

    Args:
        name (str): name of the pile
        decklist (list[dict]): the decklist for this pile
        pos (int): where should this spawn relative to the first pile?

    Returns:
        dict
    '''
    deck_json = dict()
    deck_json['Name'] = 'DeckCustom'
    deck_json['Nickname'] = name
    deck_json['ContainedObjects'] = list()
    deck_json['DeckIDs'] = list()
    deck_json['CustomDeck'] = dict()
    deck_json['Transform'] = {
        'posX': pos,
        'posY': 0,
        'posZ': 0,
        'rotX': 0,
        'rotY': 180,
        'rotZ': 180,
        'scaleX': 1,
        'scaleY': 1,
        'scaleZ': 1
    }

    count = 1
    for card in decklist:
        for _ in range(int(card['qty'])):
            deck_json['ContainedObjects'].append({
                'CardID': count*100,
                'Name': 'Card',
                'Nickname': card['name'],
                'Transform': {
                    'posX': 0,
                    'posY': 0,
                    'posZ': 0,
                    'rotX': 0,
                    'rotY': 180,
                    'rotZ': 180,
                    'scaleX': 1,
                    'scaleY': 1,
                    'scaleZ': 1
                }
            })
            deck_json['DeckIDs'].append(count*100)

        deck_json['CustomDeck'][count] = {
            'FaceURL': card['front_image_url'],
            'BackURL': card['back_image_url'],
            'NumHeight': 1,
            'NumWidth': 1,
            'BackIsHidden': True
        }
        count += 1
    return deck_json



def decklist_to_tts(deck_str: str, sleeve: str = 'http://3.219.233.7/images/backs/0aeebaf5-8c7d-4636-9e82-8c27447861f7.jpg'):
    decklist = parse(deck_str)
    piles = generate_cards(decklist, sleeve)
    return to_tts_json(piles)



if __name__ == '__main__':
    opts, _ = getopt.getopt(sys.argv[1:], "hi:o:s:")   # 'h' indicates to expect an arg '-h' with no arguments | 'i:' indiciates to expect an arg '-i' that must have an argument | same with 'o' and 's':
    input = 'deck.txt'
    output = 'deck.json'
    sleeve = 'http://3.219.233.7/images/backs/0aeebaf5-8c7d-4636-9e82-8c27447861f7.jpg'

    for opt, arg in opts:
        if opt == '-h':
            print('-i <filename>: input file. should be a raw decklist copied and pasted to some file (usually a .txt file). if not provided, defaults to "deck.txt"')
            print('-o <filename>: output file. should a json file (ends with .json). if not provided, defaults to "deck.json"')
            print('-s <url>: sleeve image link. should be a url to an image that you want to use as the sleeve or card back. if not provided, defaults to the regular mtg card back')
        elif opt == '-i':
            input = arg
        elif opt == '-o':
            output = arg
        elif opt == '-s':
            sleeve = arg

    with open(input, 'r') as file:
        raw = file.read()

    tts_json = decklist_to_tts(raw, sleeve)

    with open(output, 'w+') as file:
        json.dump(tts_json, file)