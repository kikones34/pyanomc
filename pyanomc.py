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
    
                        * white key = 1, black key = 0.5, e.g. distance from C4 to C#5 = 7.5

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

import mido
from docopt import docopt

from arg_parsing import *

arg_parsers = {
    "--hands": int_parser(minv=1),
    "--fingers": int_parser(minv=1),
    "--span": float_parser(),
    "--max-notes": int_parser(),
    "--lowest-key": note_parser(),
    "--highest-key": note_parser()
}


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
    index = octave * 7 + key_index[key]
    return index


def key_distance(n1, n2):
    return white_key_index(n2) - white_key_index(n1)


def midi_time_to_seconds(time, ppqn, tempo):
    return mido.tick2second(time, ppqn, tempo)


def midi_time_to_measure(time, ppqn, timesig):
    beat = time / ppqn
    beats_per_measure = 4 * (timesig[0] / timesig[1])
    measure = 1 + int(beat / beats_per_measure)

    return measure


class Config:
    """
    @DynamicAttrs
    This class provides a cleaner API than just using the args dictionary directly.
    It transforms the CLI parameters into class attributes (leading dashes are removed and
    dashes inside the name are replaced with an underscore).
    It also sets up some functions to perform actions which depend on the configuration.
    """

    def __init__(self, args):
        # hack to automatically convert command line args to config attributes
        self.__dict__ = {k.replace("--", "").replace("<", "").replace(">", "").replace("-", "_"): v for k, v in
                         args.items()}

        # extra attributes that don't come from the command line
        self.tempo = None
        self.key = None
        self.timesig = None
        self.ppqn = None

        # functions
        self.note2str = str if self.no_note_trans else m2h_note
        self.time2str = str if self.no_time_trans else lambda t: str(
            midi_time_to_seconds(t, self.ppqn, self.tempo)) + "s"


class Action:
    """ A class which represents an action performed on the piano """

    def __init__(self, press, note, time, config):
        self.press = press
        self.note = note
        self.time = time
        self.config = config

    def __str__(self):
        action_str = "Press" if self.press else "Release"
        note_str = self.config.note2str(self.note)
        time_str = self.config.time2str(self.time)
        measure = midi_time_to_measure(self.time, self.config.ppqn, self.config.timesig)
        return f"{action_str} note {note_str} at measure {measure} ({time_str})"


class MidiChecker:
    def __init__(self, config):
        # opens midi file and sets up some variables
        self.midi = mido.MidiFile(config.file)
        self.config = config
        self.config.ppqn = self.midi.ticks_per_beat

    def parse_events(self):
        # creates a list of actions (press/release note) with their associated timestamp
        actions = []
        for i, track in enumerate(self.midi.tracks):
            acc_time = 0
            for msg in track:
                # assume MIDI song metadata is at some event at time 0
                # TODO: for now, assume tempo and time sig don't change for the whole song
                if msg.time == 0:
                    if msg.type == "set_tempo":
                        self.config.tempo = msg.tempo
                    elif msg.type == "key_signature":
                        self.config.key = msg.key
                    elif msg.type == "time_signature":
                        self.config.timesig = (msg.numerator, msg.denominator)

                acc_time += msg.time
                if msg.type in ["note_on", "note_off"]:
                    actions.append(Action(msg.type == "note_on", msg.note, acc_time, self.config))

        # sort actions by acc time (needed if the midi has more than one track)
        actions.sort(key=lambda a: a.time)

        return actions

    def verify_actions(self, actions):
        # analizes all note intersections to determine if they are playable with the given restrictions
        no_fails = True
        pressed_notes = []
        for a in actions:
            if a.press:
                if a.note in pressed_notes:
                    if not self.config.hide_warnings:
                        print(f"Warning: Note press while note is already being pressed, in action '{a}'")
                else:
                    pressed_notes.append(a.note)
                violation = self._verify_restrictions(pressed_notes)
                if violation is not None:
                    print(f"Fail: Restrictions not satisfied, in action '{a}'")
                    indent = "      "
                    print(indent + violation.replace("\n", "\n" + indent))
                    no_fails = False
                    if self.config.abort_on_fail:
                        exit(1)
            else:
                if a.note not in pressed_notes:
                    if not self.config.hide_warnings:
                        print(f"Warning: Note release while note is not being pressed, in action '{a}'")
                else:
                    pressed_notes.remove(a.note)

        if no_fails:
            print("All tests passed!")

    def _verify_restrictions(self, pressed_notes):
        sorted_pressed_notes = sorted(pressed_notes)

        # piano restrictions
        if not self.config.no_piano_res:
            # note range check
            for n in pressed_notes:
                if not self.config.lowest_key <= n <= self.config.highest_key:
                    return f"Note out of range. Must be between {self.config.note2str(self.config.lowest_key)} and {self.config.note2str(self.config.highest_key)}."

        # player restrictions
        if not self.config.no_player_res:
            # max notes check
            if len(pressed_notes) > self.config.max_notes:
                return f"Too many notes held at once ({len(pressed_notes)}), maximum is {self.config.max_notes}.\n" \
                       f"Notes pressed at once: {', '.join(map(self.config.note2str, sorted_pressed_notes))}."

            # hands & fingers check (assumes min 1 hand and 1 finger per hand)
            hand_keys = [[sorted_pressed_notes[0]]]
            hand = 0
            for n in sorted_pressed_notes[1:]:
                if len(hand_keys[hand]) == self.config.fingers or key_distance(hand_keys[hand][0],
                                                                               n) > self.config.span:
                    hand += 1
                    if hand == self.config.hands:
                        hand_keys_str = '\n'.join(
                            f"Hand {h}: {', '.join(map(self.config.note2str, hand_keys[h]))}." for h in
                            range(self.config.hands))
                        return f"Not enough hands/fingers to press all the keys. Keys pressed by each hand:\n" \
                               f"{hand_keys_str}\n" \
                               f"Then trying to also hold {self.config.note2str(n)}."
                    hand_keys.append([n])
                else:
                    hand_keys[hand].append(n)

        return None


def main():
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

    midi_checker = MidiChecker(config)
    actions = midi_checker.parse_events()
    midi_checker.verify_actions(actions)


if __name__ == "__main__":
    main()

""" TODO: Future features
- Allow to have a different amount of fingers on each hand
- Add restrictions related to the speed, finger patterns, etc.
- Take pedals into account (e.g. you can use sustain instead of keeping a note pressed to have more free fingers)
- Recommend a fix for the fails
    * try to compute the most restrictive configuration which would avoid the fail
    * try transposing the song so that it doesn't cause a fail
    * try changing the octave of some notes so that they don't casue a fail
"""
