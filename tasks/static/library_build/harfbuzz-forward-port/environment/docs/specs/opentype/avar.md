# avar - Axis Variations Table
Source: avar - Axis variations table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/avar
These notes restate the source's structures and rules; where they differ, the source governs.

## Role

- 'avar' is optional in a variable font and is used together with 'fvar' (fvar.md).
- It changes, axis by axis, how an instance coordinate is normalized before variation data is
  applied. Without it, the user-to-normalized map has two linear pieces: minValue maps to
  -1, defaultValue to 0 and maxValue to +1. With it, extra breakpoints turn the map into a
  piecewise-linear function with more segments, so equal steps in user value can produce
  small changes in one part of the axis and large ones in another.
- The full normalization process (with or without 'avar') belongs to the "Coordinate scales
  and normalization" section of the OpenType Font Variations Overview chapter, which has no
  digest here; otvarcommonformats.md (Coordinate normalization) summarizes it, including the
  final conversion to F2DOT14.
- This page defines version 1.0 only.

## Default normalization (the input to 'avar')

For one axis, with v the user value already clamped to [minValue, maxValue] and the three
axis values taken from 'fvar':

1. v < defaultValue: n = -(defaultValue - v) / (defaultValue - minValue).
2. v > defaultValue: n = (v - defaultValue) / (maxValue - defaultValue).
3. Otherwise: n = 0.

The result n lies in [-1, +1]. When the font has an 'avar' table, n is then passed through
that axis's segment map.

## Table layout

Axis variation table:

| Type | Name | Description |
|---|---|---|
| uint16 | majorVersion | Major version; 1. |
| uint16 | minorVersion | Minor version; 0. |
| uint16 | (reserved) | Permanently reserved; 0. |
| uint16 | axisCount | Number of axes; must equal axisCount in 'fvar'. |
| SegmentMaps | axisSegmentMaps[axisCount] | One segment map per axis, in the axis order of 'fvar'. |

SegmentMaps record:

| Type | Name | Description |
|---|---|---|
| uint16 | positionMapCount | Number of mapping pairs for this axis; may be 0. |
| AxisValueMap | axisValueMaps[positionMapCount] | The mapping pairs of this axis. |

AxisValueMap record:

| Type | Name | Description |
|---|---|---|
| F2DOT14 | fromCoordinate | Input value: a coordinate as produced by default normalization. |
| F2DOT14 | toCoordinate | Output value: the adjusted normalized coordinate for that input. |

Layout notes:

- The header is 8 bytes and the segment maps follow it back to back.
- A SegmentMaps record is 2 + 4 x positionMapCount bytes, so the map of axis k is found by
  walking over the maps of axes 0 to k-1.

## Required mappings and invalid data

- There must be exactly one segment map per 'fvar' axis, in 'fvar' axis order.
- An axis whose normalization is not modified may have positionMapCount 0; its values pass
  through unchanged.
- A map that has any entries must contain at least the three identity pairs -1 -> -1, 0 -> 0
  and +1 -> +1, even if it adds nothing else. If any of the three is missing, that axis is not
  modified at all.
- fromCoordinate values must all differ and must rise from record to record. A record whose
  fromCoordinate is not greater than that of an earlier record may be ignored.
- toCoordinate values must never fall: every record after the first needs a toCoordinate at
  least as large as the one before it, so the mapping cannot run backwards. A record whose
  toCoordinate is smaller than that of the previous record may be ignored.

## Mapping algorithm

Each two consecutive AxisValueMap records of an axis bound one segment: the segment maps
their fromCoordinate values onto their toCoordinate values, and values inside it are found by
linear interpolation. For a default-normalized value n on one axis:

1. If the axis has no map entries, or lacks one of the pairs (-1, -1), (0, 0), (+1, +1),
   return n.
2. Drop records that break the ordering rules above (the page allows ignoring them).
3. Find consecutive records a and b with a.fromCoordinate <= n <= b.fromCoordinate. The map
   holds the inputs -1 and +1 and n lies in [-1, +1], so such a pair always exists.
4. If n equals a.fromCoordinate, return a.toCoordinate; if n equals b.fromCoordinate, return
   b.toCoordinate.
5. Otherwise return a.toCoordinate + (n - a.fromCoordinate) x (b.toCoordinate -
   a.toCoordinate) / (b.fromCoordinate - a.fromCoordinate).
6. The value obtained continues to the F2DOT14 conversion (otvarcommonformats.md, Coordinate
   normalization, step 5).

```
avar_map(n, maps):                       # maps = AxisValueMap list of one axis
    if maps is empty or any of (-1,-1), (0,0), (+1,+1) is absent:
        return n
    keep = records in order, skipping any whose from <= an earlier kept from
           or whose to < the previous kept to
    for each consecutive pair (a, b) in keep:
        if a.from <= n <= b.from:
            if n == a.from: return a.to
            if n == b.from: return b.to
            return a.to + (n - a.from) * (b.to - a.to) / (b.from - a.from)
```

Because -1, 0 and +1 map to themselves, the default instance stays at 0 and the axis
extremes stay at -1 and +1; only the shape between them changes.
