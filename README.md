# mtg2tts
takes a mtg decklist and converts it into a tabletop simulator object that can be spawned in

# Installation

if you want to use this as a command line tool, simply clone this repository and see the usage section.

# Usage

## Command Line

`py Converter.py -i 'input_file.txt' -o 'output_file.json' -s 'someurl.com/someimage.png'`

Where
* `-i`: should contain the text copied and pasted from moxfield's export button. defaults to `deck.txt` if not given
* `-o`: a json file that can be placed (or saved to) `C:\Users\<username>\Documents\My Games\Tabletop Simulator\Saves\Saved Objects\` for the object to show up as a spawnable obejct in tabletop simulator. defaults to `deck.json` if not given
* `-s`: a url to an image to use a sleeve / cardback

## Library

You may use the high level function `decklist_to_tts()` like:

```py
import json
import Converter

with open('deck.txt', 'r') as input_file, open('deck.json', 'w') as output_file:
    tts_json = Converter.decklist_to_tts(input_file.read())
    json.dump(tts_json, output_file)
```

---

If you would like more granular control over the flow and wish to intercept data as it passes from function to function, you can do:

```py
import json
import Converter

with open('deck.txt', 'r') as input_file:
    raw = file.read()
  
decklist = Converter.parse(raw)
piles = Converter.generate_cards(decklist)
tts_json = Converter.to_tts_json(piles)

with open('deck.json', 'r') as output_file:
    json.dump(tts_json, output_file)
```

This is essentially what `decklist_to_tts()` does

---

Just be mindful that sometimes this is unable to find cards for whatever reason (either due to bad parsing or bad input). In that scenario, `generate_cards()`, and by extension `decklist_to_tts()`, will throw a `Converter.CardsNotFoundError` which has 2 attributes: 
* `not_found`: a list of all the cards that couldn't be found in the form of dicts
* `piles`: the decks/piles that the converter was able to produce, excluding those not found
