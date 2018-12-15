# PyanoMC
PyanoMC - Piano Midi Checker is a program which analyzes a MIDI file and determines if it can be performed on a piano given a set of restrictions.

## Dependencies

PyanoMC is made in Python 3 and uses the following libraries:

`mido` - to manipulate MIDI files

`docopt` - to handle console arguments

You can install them through `pip`:

`pip install mido docopt`

## Usage examples

* Determine if the MIDI `toho.mid` is playable on a standard 88-key piano by a player with 2 hands and 5 fingers on each hand, capable of spanning at least the distance of an octave (7 white notes) with a single hand. Show all warnings and fails:

  `pyanomc toho.mid`

* Determine if the MIDI `black.mid` is playable on a standard 61-key keyboard by three octopuses (each having 1 "hand" with 8 "fingers" on each hand), capable of spanning at least the distance of 13 white notes plus a black note with their tentacles. Don't show any warnings, abort on first fail:

  `pyanomc black.mid -AW -h 3 -f 8 -s 13.5 -l C2 -r C7`

  or using long parameter names

  `pyanomc black.mid --abort-on-fail --hide-warnings --hands 3 --fingers 8 --span 13.5 --lowest-key C2 --highest-key C7`

Run `pyanomc --help` for full usage information.

## Contributing

Feel free to improve the current features or add new ones through pull requests.

See the "TODO" docstring at the end of `pyanomc.py` for a list of ideas which I'd like to get implemented at some point.
