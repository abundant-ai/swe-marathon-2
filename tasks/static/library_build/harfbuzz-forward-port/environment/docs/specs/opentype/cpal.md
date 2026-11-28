# CPAL - Color Palette Table
Source: CPAL - Color Palette Table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/cpal
These notes restate the source's structures and rules; where they differ, the source governs.

## Scope

- CPAL holds one or more color palettes. Version 1 can also name palettes and palette entries through 'name' table IDs.
- Every color is an sRGB color (IEC 61966-2-1:1999; CSS Color Module Level 4, section 10.2, also gives its primaries and transfer function), stored as four 8-bit channels in the byte order blue, green, red, alpha.
- COLR always needs CPAL; the SVG table may use it (see "Use by COLR and SVG").

## Palette model

- All palettes have the same number of entries, numPaletteEntries. Entries are addressed by a zero-based index.
- The color records of all palettes sit in one shared array of numColorRecords ColorRecords. Palette i is the run of numPaletteEntries consecutive records that starts at colorRecordIndices[i].
- Palettes may start at the same record (they are then identical) or overlap partly. So the number of distinct palettes can be below numPalettes, and numColorRecords can be below numPalettes * numPaletteEntries.
- Palette 0 is the default palette.
- A CPAL table, when present, defines at least one palette, and each palette has at least one entry. An empty CPAL table (no palettes and no records) is not allowed.
- numColorRecords >= max(colorRecordIndices) + numPaletteEntries, so every palette fits inside the shared array.

## Header

Only versions 0 and 1 are defined.

### Version 0 header (12 + 2 * numPalettes bytes)

| Type | Name | Description |
|---|---|---|
| uint16 | version | Header version: 0 |
| uint16 | numPaletteEntries | Entries in every palette |
| uint16 | numPalettes | How many palettes the table defines |
| uint16 | numColorRecords | Length of the shared ColorRecord array |
| Offset32 | colorRecordsArrayOffset | Start of the ColorRecord array, from start of CPAL |
| uint16 | colorRecordIndices[numPalettes] | Per palette, index of its first record within the shared array |

### Version 1 header (24 + 2 * numPalettes bytes)

| Type | Name | Description |
|---|---|---|
| uint16 | version | Header version: 1 |
| uint16 | numPaletteEntries | Entries in every palette |
| uint16 | numPalettes | How many palettes the table defines |
| uint16 | numColorRecords | Length of the shared ColorRecord array |
| Offset32 | colorRecordsArrayOffset | Start of the ColorRecord array, from start of CPAL |
| uint16 | colorRecordIndices[numPalettes] | Per palette, index of its first record within the shared array |
| Offset32 | paletteTypesArrayOffset | Palette types array, from start of CPAL; 0 when absent |
| Offset32 | paletteLabelsArrayOffset | Palette labels array, from start of CPAL; 0 when absent |
| Offset32 | paletteEntryLabelsArrayOffset | Palette entry labels array, from start of CPAL; 0 when absent |

Version 1 appends three offsets to the version 0 header. Because colorRecordIndices has a variable length, the first of them sits at byte 12 + 2 * numPalettes from the start of the table: read numPalettes before locating them. Each of the three may be 0, meaning that array is not provided.

## Color records

Lookup: for palette p and entry e (both zero-based), the record index is colorRecordIndices[p] + e.

Color records array, at colorRecordsArrayOffset:

| Type | Name | Description |
|---|---|---|
| ColorRecord | colorRecords[numColorRecords] | The shared colors of all palettes |

ColorRecord (4 bytes):

| Type | Name | Description |
|---|---|---|
| uint8 | blue | Blue channel, byte 0 (B0) |
| uint8 | green | Green channel, byte 1 (B1) |
| uint8 | red | Red channel, byte 2 (B2) |
| uint8 | alpha | Alpha channel, byte 3 (B3) |

Rules:

- Channel values are sRGB levels on the non-linear (transfer-function encoded) scale, 0 to 255.
- Colors are stored straight, not premultiplied by alpha. Every entry should set its alpha explicitly.
- Alpha 0 is fully transparent and 255 fully opaque. The record's alpha combines with, and does not override, opacity applied by higher-level contexts.
- Where separately drawn overlapping elements meet, edge rendering of one can show at the edge of another ("seaming"); how visible this is depends on color contrast.

## Palette types array (version 1)

At paletteTypesArrayOffset, when that offset is not 0:

| Type | Name | Description |
|---|---|---|
| uint32 | paletteTypes[numPalettes] | One flag word per palette |

Flags:

| Mask | Name | Description |
|---|---|---|
| 0x0001 | USABLE_WITH_LIGHT_BACKGROUND | Bit 0: suited to display over a light (for example white) background |
| 0x0002 | USABLE_WITH_DARK_BACKGROUND | Bit 1: suited to display over a dark (for example black) background |
| 0xFFFC | Reserved | Reserved for later use; set to 0 |

- Both bits may be set on the same palette; they do not exclude each other.
- The field is 32 bits wide while the source gives the reserved mask as 0xFFFC (bits 2 to 15); no meaning is defined for bits 16 to 31 either. Only bits 0 and 1 carry meaning.

## Palette labels array (version 1)

At paletteLabelsArrayOffset, when that offset is not 0:

| Type | Name | Description |
|---|---|---|
| uint16 | paletteLabels[numPalettes] | 'name' table ID with the palette's user-interface name; 0xFFFF when it has none |

## Palette entry labels array (version 1)

At paletteEntryLabelsArrayOffset, when that offset is not 0:

| Type | Name | Description |
|---|---|---|
| uint16 | paletteEntryLabels[numPaletteEntries] | 'name' table ID naming the role of entry index i (such as "Outline" or "Fill"); 0xFFFF when it has none |

- Entry labels describe entry indices, so one set of labels serves every palette.
- Label IDs normally lie in the font-specific 'name' ID range.

## Use by COLR and SVG

COLR (see colr.md):

- A font with a COLR table must also have a CPAL table, which holds every font-defined color used by its color glyphs.
- COLR references a color by palette entry index; the application decides which palette is in use.
- In COLR, palette entry index 0xFFFF is not a CPAL entry: it selects the application's foreground (text) color, and it means that in every palette. Usable entry indices therefore end at 0xFFFE (65534).

SVG:

- CPAL is optional for a font with an SVG table, because SVG documents can state colors directly. When present, CPAL can supply the values of color variables used by the SVG glyph descriptions.
- In SVG glyph descriptions the foreground color is written with the currentColor keyword.
- With an SVG table, the default palette (palette 0) must hold the same colors as the default values of the SVG color variables, so that engines that render SVG but do not support palettes show the same colors.
- Colors written directly ("hard-coded") in SVG documents are not color variables and do not change when another palette is selected. See the SVG table chapter for details.

## Interpolation of colors

These rules govern gradient fills in the SVG table and in COLR version 1, whose color stops are interpolated along a color line.

- Interpolate linearly between the two neighboring stops: for t between a stop at t0 (color C0) and the next stop at t1 (color C1), let f = (t - t0) / (t1 - t0); then C(t) = (1 - f) * C0 + f * C1, for each of R, G and B (alpha is handled below).
- The source's worked example (stops at 0.5 and 0.9, sample at 0.8) gives the 75% share to the first stop, but under linear interpolation f = (0.8 - 0.5) / (0.9 - 0.5) = 0.75 is the weight of the second stop (at 0.9), and 0.25 that of the first.
- Interpolating on the non-linear sRGB scale gives different colors from interpolating in linear light, so the scale is fixed per table:
  - COLR gradients: interpolate linear-light values, that is, after applying the inverse sRGB transfer function to each channel.
  - SVG gradients: follow SVG 1.1 (Second Edition); its 'color-interpolation' property selects the non-linear sRGB scale (the default) or a linear-light scale obtained with the inverse sRGB transfer function.
- CPAL values are always encoded with the non-linear sRGB transfer function.
- For both tables, alpha is premultiplied into each linearized R, G and B component before interpolating:
  1. Turn the CPAL alpha into a value in [0, 1] by dividing by 255.
  2. For COLR version 1 color references, also multiply by the reference's own alpha (including any variation delta).
  3. Multiply each linear-light R, G and B by that alpha.
  4. Interpolate the premultiplied R, G and B values, and interpolate alpha the same way. Alpha is already on a linear scale and needs no transfer function.
  5. Divide each interpolated R, G and B by the interpolated alpha to undo the premultiplication.
  6. Whether the sRGB transfer function is applied again afterward depends on what the output context needs.
- Precision: no minimum is required, but the linearization, premultiplication and interpolation steps need more precision than 8 bits per channel. When the output device supports more depth (for example 10 or 12 bits per channel), using it for the gradient ramp reduces visible banding.

sRGB transfer function, for reference (defined by IEC 61966-2-1 and CSS Color Module Level 4; the source cites it but does not repeat it). With a channel c = value / 255 in [0, 1]:

- To linear light: lin = c / 12.92 if c <= 0.04045, otherwise ((c + 0.055) / 1.055) ^ 2.4.
- Back to the encoded scale: c = 12.92 * lin if lin <= 0.0031308, otherwise 1.055 * lin ^ (1 / 2.4) - 0.055.

## Processing steps

1. Read version, numPaletteEntries, numPalettes, numColorRecords and colorRecordsArrayOffset, then numPalettes uint16 values of colorRecordIndices.
2. If version is 1, read the three Offset32 fields that follow, at byte 12 + 2 * numPalettes. A zero offset means that array is absent.
3. The table must satisfy: numPalettes >= 1; numPaletteEntries >= 1; colorRecordIndices[i] + numPaletteEntries <= numColorRecords for every palette i; every array inside the table.
4. Use palette 0 unless the application selects another one (for example with help of the light and dark background flags in paletteTypes).
5. To resolve a COLR color reference with entry e in palette p: if e is 0xFFFF, use the foreground color; otherwise read colorRecords[colorRecordIndices[p] + e] and convert its B, G, R, A byte order to whatever the renderer needs.
6. For user interfaces, look up palette names and entry names in the 'name' table through the label arrays, skipping 0xFFFF values.
