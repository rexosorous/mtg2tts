# python standard libraries
import inspect
import requests


'''
Interacts with Scryfall's BASE_URL
Documentation: https://scryfall.com/docs/BASE_URL
Scryfall asks that no more than 10 requests be made per second (100ms delay between requests)
'''


class HttpResponseError(Exception):
    def __init__(self, calling_function, url, body, code, text):
        self.calling_function = calling_function
        self.url = url
        self.body = body
        self.code = code
        self.text = text
        super().__init__(f'{calling_function} got Response {code}: {text}')



BASE_URL = 'https://api.scryfall.com'


def send_get(url):
    ''' Utility function to reduce repeated code
    '''
    response = requests.get(url)
    if not response.ok:
        raise HttpResponseError(inspect.stack()[1].function, response.url, response.request.body, response.status_code, response.text)
    return response.json()


def send_post(url, body):
    ''' Utility function to reduce repeated code
    '''
    response = requests.post(url, json=body)
    if not response.ok:
        raise HttpResponseError(inspect.stack()[1].function, response.url, response.request.body, response.status_code, response.text)
    return response.json()


def search(name: str) -> dict:
    '''
    Searches for a card based on exact name

    Args:
        name (str)

    Returns:
        (dict): response from scryfall
    '''
    ENDPOINT = '/cards/named?exact='
    return send_get(f'{BASE_URL}{ENDPOINT}{name}')


def fuzzy_search(name: str) -> dict:
    '''
    Searches for a card based on name (fuzzily)

    Args:
        name (str)

    Returns:
        (dict): response from scryfall
    '''
    ENDPOINT = '/cards/named?fuzzy='
    return send_get(f'{BASE_URL}{ENDPOINT}{name}')


def exact_search(set_code: str, collector_number: str) -> dict:
    '''
    Searches for a card based on set and collector number

    Args:
        set_code (str): ex rtr
        collector_number (str): ex 127p

    Returns:
        (dict): response from scryfall
    '''
    ENDPOINT = f'/cards'
    return send_get(f'{BASE_URL}{ENDPOINT}/{set_code}/{collector_number}/en')


def bulk_search(decklist: list[dict]) -> dict:
    '''
    Searches for multiple cards (usually a deck) using set and collector number as identifiers.
    Max 75 cards per search.

    Args:
        deck (list[str])

    Returns:
        (dict): response from scryfall
    '''
    ENDPOINT = '/cards/collection'

    pages = list()
    while decklist:
        pages.append(decklist[:75])
        decklist = decklist[75:]

    full_response = None
    for page in pages:
        search_params = {'identifiers':
            [{'set': card['set'], 'collector_number': card['num']} if 'set' in card and 'num' in card else {'name': card['name']} for card in page] # attempts to search by set and collector num if available, else search by name
        }
        response = send_post(f'{BASE_URL}{ENDPOINT}', search_params)
        if not full_response:
            full_response = response
        else:
            full_response['not_found'] += (response['not_found'])
            full_response['data'] += (response['data'])
    return full_response


def token_search(tokens: list[str]) -> dict:
    '''
    Finds tokens based on their scryfall ID

    Args:
        tokens (list[str]): scryfall IDs, not names

    Returns:
        (dict): response from scryfall
    '''
    ENDPOINT = '/cards/collection'

    if not tokens:
        return {'data': []}

    pages = list()
    while tokens:
        pages.append(tokens[:75])
        tokens = tokens[75:]

    full_response = None
    for page in pages:
        search_params = {'identifiers':
            [{'id': token_id} for token_id in page] # attempts to search by set and collector num if available, else search by name
        }
        response = send_post(f'{BASE_URL}{ENDPOINT}', search_params)
        if not full_response:
            full_response = response
        else:
            full_response['not_found'] += (response['not_found'])
            full_response['data'] += (response['data'])
    return full_response