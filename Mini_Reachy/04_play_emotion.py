"""Play one recorded emotion from the official Reachy Mini library.

The first run may download the dataset from Hugging Face.
Sound is off so this still works when camera and audio are not available.
Change EMOTION below, or pick any name printed at startup.
"""

from reachy_mini.motion.recorded_move import RecordedMoves

from robot import connect

EMOTIONS = "pollen-robotics/reachy-mini-emotions-library"
EMOTION = "amazed1"


def main() -> None:
    library = RecordedMoves(EMOTIONS)
    names = sorted(library.list_moves())
    print(f"Loaded {len(names)} emotions. Examples: {', '.join(names[:8])}")
    print("Change EMOTION at the top of this file to play a different one.")

    name = EMOTION if EMOTION in names else names[0]
    if name != EMOTION:
        print(f"{EMOTION!r} is not in this library. Playing {name!r} instead.")

    move = library.get(name)
    print(f"Playing {name}: {move.description}")

    with connect() as mini:
        mini.play_move(move, initial_goto_duration=1.0, sound=False)

    print("Done.")


if __name__ == "__main__":
    main()
