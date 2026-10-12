"""Play a few recorded emotions, then one dance.

Motion libraries live on Hugging Face. The first run downloads them.
Sound is off. Edit PREFERRED_EMOTIONS to try other names printed below.
"""

from reachy_mini.motion.recorded_move import RecordedMoves

from robot import connect, go_home

EMOTIONS = "pollen-robotics/reachy-mini-emotions-library"
DANCES = "pollen-robotics/reachy-mini-dances-library"
PREFERRED_EMOTIONS = ["amazed1", "happy1", "curious1", "sad1"]


def pick(library: RecordedMoves, preferred: list[str], limit: int) -> list[str]:
    names = library.list_moves()
    chosen = [name for name in preferred if name in names]
    if not chosen:
        chosen = sorted(names)[:limit]
    return chosen[:limit]


def main() -> None:
    emotions = RecordedMoves(EMOTIONS)
    dances = RecordedMoves(DANCES)
    emotion_names = pick(emotions, PREFERRED_EMOTIONS, limit=3)
    dance_names = pick(dances, [], limit=1)

    print(f"Emotions available: {len(emotions.list_moves())}")
    print("Playing:", ", ".join(emotion_names))
    print("Then dance:", ", ".join(dance_names))

    with connect() as mini:
        for name in emotion_names:
            move = emotions.get(name)
            print(f"Emotion {name}: {move.description}")
            mini.play_move(move, initial_goto_duration=1.0, sound=False)

        for name in dance_names:
            move = dances.get(name)
            print(f"Dance {name}: {move.description}")
            mini.play_move(move, initial_goto_duration=1.0, sound=False)

        go_home(mini)
        print("Done.")


if __name__ == "__main__":
    main()
