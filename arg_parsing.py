""" Functions related to CLI argument parsing """

def parse_args(args, arg_parsers):
    for k, v in args.items():
        if k in arg_parsers:
            parsed_val = arg_parsers[k](k, v)
            if parsed_val is None:
                exit(1)
            args[k] = parsed_val

def int_parser(minv=None, maxv=None):
    return lambda arg, val: num_parser_impl(arg, val, minv=minv, maxv=maxv, cast=int)

def float_parser(minv=None, maxv=None):
    return lambda arg, val: num_parser_impl(arg, val, minv=minv, maxv=maxv, cast=float)

def num_parser_impl(arg, val, minv=None, maxv=None, cast=None):
    cast_str = {int: "an integer", float: "a number"}
    try:
        cast_val = cast(val)
    except:
        print(f"{arg} must be {cast_str[cast]}.")
        return None
    if minv is not None:
        if cast_val < minv:
            print(f"{arg} must be >= {minv}")
            return None
    if maxv is not None:
        if cast_val > maxv:
            print(f"{arg} must be <= {maxv}")
            return None
    return cast_val

def note_parser():
    return lambda arg, val: note_parser_impl(arg, val)

def note_parser_impl(arg, val):
    letter, *rest = val
    if rest[0] in ["#", "b"]:
        letter += rest[0]
        octave = int(''.join(rest[1:]))
    else:
        octave = int(''.join(rest))
    pitches = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
    pitch = pitches[letter]
    midi_note = (octave+1)*12 + pitch
    return midi_note
