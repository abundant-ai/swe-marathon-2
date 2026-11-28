"""Input decoding and normalization (PART 0 INPUT: CARVE-P0-001, -002, -023)."""


def normalize(data):
    """bytes -> normalized text: ill-formed UTF-8 -> U+FFFD (one per maximal
    subpart), a single leading BOM dropped, NUL -> U+FFFD, CRLF / CR -> LF."""
    text = data.decode("utf-8", errors="replace")
    text = text.removeprefix("\ufeff")
    if "\x00" in text:
        text = text.replace("\x00", "\ufffd")
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text
