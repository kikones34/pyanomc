#!/usr/bin/env python3

"""PyanoMC - Piano Midi Checker
alpha 0.1

Usage:
  pyanomc <file> [options]
  pyanomc [--help]

Options:
  --help                Show this message.

  Player restrictions:
  -h --hands <n>        Number of hands available [default: 2].
  -f --fingers <n>      Fingers available per hand [default: 5].
  -s --span <n>         Maximum distance* between two keys played by the same hand [default: 7].
  -n --max-notes <n>    Maximum number of notes which can be held at once [default: hands*fingers].
    
                        * white key = 1, black key = 0.5, e.g. distance from C4 to C#4 = 7.5

  Piano restrictions:
  -l --lowest-key <n>   Lowest note which can be played [default: A0].
  -r --highest-key <n>  Highest note which can be played [default: C8].

  Other:
  -A --abort-on-fail    Stop analizing the MIDI once a fail occurs.
  -W --hide-warnings    Don't display warning messages.
  -N --no-note-trans    Show the original MIDI note values.
  -T --no-time-trans    Show the original MIDI time values.
  -P --no-piano-res     Disable piano restrictions.
  -Y --no-player-res    Disable player restrictions.

Nomenclature:
  warning: An issue with the MIDI events unrelated to the restrictions.
  fail:    A violation of the restrictions.

"""

from arg_parsing import *

arg_parsers = {
    "--hands": int_parser(minv=1),
    "--fingers": int_parser(minv=1),
    "--span": float_parser(), 
    "--max-notes": int_parser(),
    "--lowest-key": note_parser(),
    "--highest-key": note_parser()
}

import mido
from docopt import docopt

# utility functions
def m2h_note(note):
    # TODO: support different keys
    pitches = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = (note // 12) - 1
    pitch = pitches[note % 12]
    return pitch + str(octave)

def white_key_index(note):
    key_index = [0, 0.5, 1, 1.5, 2, 3, 3.5, 4, 4.5, 5, 5.5, 6]
    octave = note // 12
    key = note % 12
    index = octave*7 + key_index[key]
    return index

def key_distance(n1, n2):
    return white_key_index(n2) - white_key_index(n1)

class Config():
    """ This class provides a cleaner API than just using the args dictionary directly.
        It transforms the CLI parameters into class attributes (leading dashes are removed and
        dashes inside the name are replaced with an underscore).
        It also sets up some functions to perform actions which depend on the configuration.
    """
    def __init__(self, args):
        self.__dict__ = {k.replace("--", "").replace("<", "").replace(">", "").replace("-", "_") : v for k, v in args.items()}
        self.note2str = str if self.no_note_trans else m2h_note
        self.time2str = str if self.no_time_trans else lambda t: str(mido.tick2second(t, self.ppqn, self.tempo)) + "s"

class Action:
    """ A class which represents an action performed on the piano """
    def __init__(self, press, note, time, config):
        self.press = press
        self.note = note
        self.time = time
        self.config = config

    def __str__(self):
        return f"{'Press' if self.press else 'Release'} note {self.config.note2str(self.note)} at {self.config.time2str(self.time)}"


def verify_restrictions(pressed_notes, config):
    sorted_pressed_notes = sorted(pressed_notes)
    
    # piano restrictions
    if not config.no_piano_res:
        # note range check
        for n in pressed_notes:
            if not config.lowest_key <= n <= config.highest_key:
                return f"Note out of range. Must be between {config.note2str(config.lowest_key)} and {config.note2str(config.highest_key)}."
    
    # player restrictions
    if not config.no_player_res:
        # max notes check
        if len(pressed_notes) > config.max_notes:
            return f"Too many notes held at once ({len(pressed_notes)}), maximum is {config.max_notes}.\n" \
                   f"Notes pressed at once: {', '.join(map(config.note2str, sorted_pressed_notes))}."

        # hands & fingers check (assumes min 1 hand and 1 finger per hand)
        hand_keys = [[sorted_pressed_notes[0]]]
        hand = 0
        for n in sorted_pressed_notes[1:]:
            if len(hand_keys[hand]) == config.fingers or key_distance(hand_keys[hand][0], n) > config.span:
                hand += 1
                if hand == config.hands:
                    hand_keys_str = '\n'.join(f"Hand {h}: {', '.join(map(config.note2str, hand_keys[h]))}." for h in range(config.hands))
                    return f"Not enough hands/fingers to press all the keys. Keys pressed by each hand:\n" \
                           f"{hand_keys_str}\n" \
                           f"Then trying to also hold {config.note2str(n)}."
                hand_keys.append([n])
            else:
                hand_keys[hand].append(n)

    return None

if __name__ == "__main__":
    # automatic arg parsing from module docstring
    args = docopt(__doc__)
    if args["<file>"] is None:
        print(__doc__)
        exit(0)
    # handles --max-notes special default case
    def_max_notes = False
    if args["--max-notes"] == "hands*fingers":
        del args["--max-notes"]
        def_max_notes = True
    # must parse args before calculating default value of --max-notes
    parse_args(args, arg_parsers)
    if def_max_notes:
        args["--max-notes"] = args["--hands"] * args["--fingers"]
    # instantiantes a config object with the provided arguments
    config = Config(args)

    # opens midi file and sets up some variables
    midi = mido.MidiFile(config.file)
    config.ppqn = midi.ticks_per_beat
    config.tempo = 500000 # TODO: extract this info from MIDI file

    # creates a list of actions (press/release note) with their associated timestamp
    actions = []
    for i, track in enumerate(midi.tracks):
        acc_time = 0
        for msg in track:
            # experimental
            # if msg.type == "set_tempo":
            #     config["tempo"] = msg.tempo
            # if msg.type == "key_signature":
            #     config["key"] = msg.key
            # if msg.type == "time_signature":
            #     config["timesig"] = (msg.numerator, msg.denominator)
            acc_time += msg.time
            if msg.type in ["note_on", "note_off"]:
                actions.append(Action(msg.type == "note_on", msg.note, acc_time, config))

    # analizes all note intersections to determine if they are playable with the given restrictions
    no_fails = True
    pressed_notes = []
    for a in actions:
        if a.press:
            if a.note in pressed_notes:
                if not config.hide_warnings:
                    print(f"Warning: Note press while note is already being pressed, in action '{a}'")
            else:
                pressed_notes.append(a.note)
            violation = verify_restrictions(pressed_notes, config)
            if violation is not None:
                print(f"Fail: Restrictions not satisfied, in action '{a}'")
                indent = "      "
                print(indent + violation.replace("\n", "\n" + indent))
                no_fails = False
                if config.abort_on_fail:
                    exit(1)
        else:
            if a.note not in pressed_notes:
                if not config.hide_warnings:
                    print(f"Warning: Note release while note is not being pressed, in action '{a}'")
            else:
                pressed_notes.remove(a.note)
    
    if no_fails:
        print("All tests passed!")

""" TODO: Future features
- Support multi-track MIDI files
- Be measure-aware (i.e. instead of giving the time of the action in seconds, give the measure and position inside the measure)
- Allow to have a different amount fingers on each hand
- Add restrictions related to the speed, finger patterns, etc.
- Take pedals into account (e.g. you can use sustain instead of keeping a note pressed to have more free fingers)
- Recommend a fix for the fails
    * try to compute the most restrictive configuration which would avoid the fail
    * try transposing the song so that it doesn't cause a fail
    * try changing the octave of some notes so that they don't casue a fail
"""
