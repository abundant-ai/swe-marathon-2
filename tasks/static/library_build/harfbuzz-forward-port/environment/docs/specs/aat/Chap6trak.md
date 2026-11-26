# 'trak' table: tracking (digest)
Source: Tracking Table - TrueType Reference Manual - Apple Developer, https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6trak.html
These notes restate the source's structures and rules; where they differ, the source governs.

## What tracking does

Tracking changes the spacing of every glyph by the same amount. The amount
depends only on the point size and on a chosen track number; glyph identity
plays no part (that is the difference from kerning).

- The table stores, per track, one value in FUnits for each listed point size.
- If the requested track and size are stored, that value is used; otherwise
  the engine interpolates or extrapolates from the stored values.
- The value is converted to ems (FUnits / unitsPerEm), scaled by the point
  size, and the result is added to every glyph's advance width. Negative values
  shrink advances, positive values widen them. (At 2048 units per em, 10
  FUnits = 10/2048 em.)
- A font should provide at least tracks -1, 0 and +1, each at two or more
  point sizes; more sizes are allowed. Track numbers are otherwise arbitrary.
  The page's prose pairs -1 / 0 / +1 with loose / normal / tight, but its
  worked example uses -1 = tight and +1 = loose, which matches the sign rule
  above.
- Each track can carry a descriptive name ("tight", "normal", ...) stored in
  the 'name' table; the track entry holds that name ID.

## Header

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | fixed32 | version | 0x00010000 |
| 4 | uint16 | format | 0 (the only format) |
| 6 | uint16 | horizOffset | offset from the start of 'trak' to the TrackData for horizontal text; 0 = none |
| 8 | uint16 | vertOffset | offset from the start of 'trak' to the TrackData for vertical text; 0 = none |
| 10 | uint16 | reserved | 0 |
| 12 | TrackData | horizData | horizontal TrackData, if present |
| - | TrackData | vertData | vertical TrackData, if present |

The two TrackData blocks are reached through their offsets, so their order is
free.

## TrackData (must start on a 4-byte boundary)

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | nTracks | number of tracks |
| 2 | uint16 | nSizes | number of point sizes |
| 4 | uint32 | sizeTableOffset | offset from the start of 'trak' to the size table |
| 8 | TrackTableEntry[nTracks] | trackTable | one entry per track (the example lists them sorted by track value) |
| - | fixed32[nSizes] | sizeTable | the point sizes, as 16.16 values (located through sizeTableOffset) |

## TrackTableEntry (8 bytes)

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | fixed32 | track | track value of this entry (for example 0xFFFF0000 = -1.0) |
| 4 | uint16 | nameIndex | 'name' table ID of the track's descriptive name; 256 <= nameIndex < 32768 |
| 6 | uint16 | offset | offset from the start of 'trak' to this track's per-size values |

Per-size values: nSizes signed 16-bit FUnit values, in the same order as
sizeTable. The per-track value arrays may be stored in any order.

## Example data from the page

Three horizontal tracks at 12 and 24 point:

| Track | 12 pt | 24 pt |
|---|---|---|
| -1 (tight, name ID 256) | -15 | -7 |
| 0 (normal, name ID 258) | 0 | 0 |
| +1 (loose, name ID 257) | 50 | 20 |

In that example the word at offset 10 (the reserved field) serves as padding
so that the TrackData starts 4-byte aligned at offset 12, sizeTableOffset is
44 (sizes 0x000C0000 and 0x00180000),
and the per-size arrays sit at 52 (track -1), 56 (track +1) and 60
(track 0).
