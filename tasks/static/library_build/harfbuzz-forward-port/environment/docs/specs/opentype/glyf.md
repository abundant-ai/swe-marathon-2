# glyf - Glyph Data Table
Source: glyf - Glyf data table (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/glyf
These notes restate the source's structures and rules; where they differ, the source governs.

## Organization

- 'glyf' holds TrueType outlines: one glyph data block per glyph ID (IDs run from 0 to
  maxp.numGlyphs - 1). The table has no header and no offsets of its own.
- 'loca' gives the offset of each block, indexed by glyph ID, plus one extra offset at the
  end; a block's size is the difference between consecutive offsets. Blocks must therefore be
  stored in glyph ID order. 'glyf' is always used together with 'loca' and 'maxp'.
- A block whose size is 0 is an empty glyph (no outline, no header).
- Each block starts with the glyph header below and continues with either a simple glyph
  description (outline given by points) or a composite glyph description (outline built from
  other glyphs).

## Glyph header

Glyph Header

| Type | Name | Description |
|---|---|---|
| int16 | numberOfContours | >= 0: simple glyph with this many contours. Negative: composite glyph (-1 is the value to use). |
| int16 | xMin | Smallest x of all points. |
| int16 | yMin | Smallest y of all points. |
| int16 | xMax | Largest x of all points. |
| int16 | yMax | Largest y of all points. |

- The box (xMin, yMin)-(xMax, yMax) is computed from every on-curve and off-curve point;
  phantom points are not included. It always contains the outline but may be larger than
  the outline's tight bounds.
- Fonts are built so that xMin equals the left side bearing from 'hmtx'; when every glyph
  follows this, bit 1 of head.flags is set (see head.md).
- Side bearings are not stored in 'glyf'. The left side bearing and advance come from
  'hmtx' (the right side bearing follows from the advance and the box); vertical top side
  bearing and advance come from 'vmtx'.
- The rasterizer appends four phantom points after the glyph's last point to represent the
  side bearings (horizontal origin and advance, vertical origin and advance); instructions
  and composite point matching may refer to them.
- Variable fonts: the header box describes the default instance only. 'gvar' has no deltas
  for it, so the box may be too small or too large for another instance. An application that
  needs the box of a non-default instance computes it from the varied point coordinates.

## Simple glyph description

Used when numberOfContours >= 0.

- With zero contours nothing more is required after the header, but data may follow, for
  example instructions acting on the phantom points.
- Points are numbered from 0 across all contours in order: each contour's first point
  follows the previous contour's last point. Phantom points are numbered after the last
  real point.

Simple Glyph table

| Type | Name | Description |
|---|---|---|
| uint16 | endPtsOfContours[numberOfContours] | Index of the last point of each contour, increasing. |
| uint16 | instructionLength | Byte length of the instructions; 0 means none, and flags follow at once. |
| uint8 | instructions[instructionLength] | TrueType instruction bytes. |
| uint8 | flags[variable] | Packed per-point flags (count found by parsing; see below). |
| uint8 or int16 | xCoordinates[variable] | Packed x values: first point relative to (0,0), each later point relative to the previous one. |
| uint8 or int16 | yCoordinates[variable] | Packed y values, relative in the same way. |

- Number of points = endPtsOfContours[numberOfContours - 1] + 1.
- Logically each point has one flag byte, one x and one y. Coordinates are deltas in font
  design units (head.unitsPerEm). Repeated flags are compressed with REPEAT_FLAG and
  unchanged coordinates may be omitted, so the stored sizes of the flag and coordinate
  arrays are known only after decoding the flags.

Simple Glyph flags

| Mask | Name | Description |
|---|---|---|
| 0x01 | ON_CURVE_POINT | Bit 0: set = on-curve point, clear = off-curve point. |
| 0x02 | X_SHORT_VECTOR | Bit 1: set = x delta is one unsigned byte whose sign comes from bit 4. Clear = bit 4 decides between "same x as before" and a 2-byte signed delta. |
| 0x04 | Y_SHORT_VECTOR | Bit 2: same as bit 1, for y, with bit 5. |
| 0x08 | REPEAT_FLAG | Bit 3: the next byte (unsigned) is how many more logical flag entries repeat this flag byte. The bit has no meaning in the expanded flags. |
| 0x10 | X_IS_SAME_OR_POSITIVE_X_SHORT_VECTOR | Bit 4: with bit 1 set: 1 = positive, 0 = negative. With bit 1 clear: 1 = x unchanged (no bytes stored), 0 = signed 16-bit delta stored. |
| 0x20 | Y_IS_SAME_OR_POSITIVE_Y_SHORT_VECTOR | Bit 5: as bit 4, for y with bit 2. |
| 0x40 | OVERLAP_SIMPLE | Bit 6: contours may overlap. Optional (overlap is allowed without it); when used it is set on the first flag byte of the glyph. |
| 0x80 | Reserved | Bit 7: must be 0. |

Decoding x for one point (y is the same with bits 2 and 5):

| X_SHORT_VECTOR | X_IS_SAME_OR_POSITIVE_X_SHORT_VECTOR | Stored data | Delta |
|---|---|---|---|
| 1 | 1 | 1 byte | +byte |
| 1 | 0 | 1 byte | -byte |
| 0 | 1 | nothing | 0 |
| 0 | 0 | 2 bytes, int16 | the int16 |

Overlap flags: OVERLAP_SIMPLE (and OVERLAP_COMPOUND for composites) are optional and some
rasterizers ignore them, but others rely on them to render overlapping contours correctly.
Tools that produce a static instance of a variable font should set the flag for glyphs whose
contours overlap in that instance, or remove the overlaps.

## Composite glyph description

Used when numberOfContours < 0.

- A composite (parent) is built from component (child) glyphs. A child may itself be a
  composite. The component graph must be acyclic and every path must end at a simple glyph.
  maxp.maxComponentDepth records the deepest nesting in the font. No minimum nesting depth
  is guaranteed to be supported, so nesting is best avoided (some devices mis-render nested
  composites; they can be flattened).
- The description is a sequence of component records, processed in order; MORE_COMPONENTS
  says whether another record follows. The contours of each child are appended to the
  parent, and the child's points are renumbered to follow all points already in the parent.
- Each child is fully processed before it is added: its phantom points exist and its own
  instructions have run. Optional parent instructions then run on the combined, renumbered
  points.
- A child is placed either by an offset vector added to all its points, or by matching one
  of its points to a point already in the parent. Point matching needs earlier points, so
  it cannot be used by the first component. A scale or 2x2 transform may also be applied to
  the child.

Component Glyph record

| Type | Name | Description |
|---|---|---|
| uint16 | flags | Component flags (below). |
| uint16 | glyphIndex | Glyph ID of the child. |
| uint8, int8, uint16 or int16 | argument1 | x offset or parent point number; type set by flag bits 0 and 1. |
| uint8, int8, uint16 or int16 | argument2 | y offset or child point number; type set by flag bits 0 and 1. |
| [transform data] |  | Optional F2DOT14 transform values, per the flags. |

Argument types:

| ARG_1_AND_2_ARE_WORDS | ARGS_ARE_XY_VALUES | argument1 and argument2 |
|---|---|---|
| set | set | int16 each (offset x, y) |
| set | clear | uint16 each (point numbers) |
| clear | set | int8 each (offset x, y) |
| clear | clear | uint8 each (point numbers) |

Parsing the component sequence (own pseudo-code):

```
any_instructions = false
loop:
    read uint16 flags, uint16 glyphIndex
    if flags & ARG_1_AND_2_ARE_WORDS: read two 16-bit arguments
    else:                             read two 8-bit arguments (argument1 first)
    if   flags & WE_HAVE_A_SCALE:          read F2DOT14 scale
    elif flags & WE_HAVE_AN_X_AND_Y_SCALE: read F2DOT14 xscale, yscale
    elif flags & WE_HAVE_A_TWO_BY_TWO:     read F2DOT14 xscale, scale01, scale10, yscale
    if flags & WE_HAVE_INSTRUCTIONS: any_instructions = true
    stop looping when flags & MORE_COMPONENTS is clear
if any_instructions:
    read uint16 numInstr, then numInstr instruction bytes
```

Component Glyph flags

| Mask | Name | Description |
|---|---|---|
| 0x0001 | ARG_1_AND_2_ARE_WORDS | Bit 0: arguments are 16-bit; clear = 8-bit. |
| 0x0002 | ARGS_ARE_XY_VALUES | Bit 1: arguments are a signed x, y offset; clear = unsigned point numbers. |
| 0x0004 | ROUND_XY_TO_GRID | Bit 2: round the offset to the pixel grid; ignored without bit 1. |
| 0x0008 | WE_HAVE_A_SCALE | Bit 3: one uniform scale follows; otherwise scale is 1.0. |
| 0x0020 | MORE_COMPONENTS | Bit 5: another component record follows this one. |
| 0x0040 | WE_HAVE_AN_X_AND_Y_SCALE | Bit 6: separate x and y scales follow. |
| 0x0080 | WE_HAVE_A_TWO_BY_TWO | Bit 7: a 2x2 matrix follows. |
| 0x0100 | WE_HAVE_INSTRUCTIONS | Bit 8: instructions for the whole composite follow the last component. |
| 0x0200 | USE_MY_METRICS | Bit 9: the composite takes its advance width, lsb and rsb from this component (hinted or not). |
| 0x0400 | OVERLAP_COMPOUND | Bit 10: components may overlap. Optional; when used it is set on the first component's flags. Some rasterizers need it (as for OVERLAP_SIMPLE). |
| 0x0800 | SCALED_COMPONENT_OFFSET | Bit 11: the offset is in the child's coordinate system and is transformed. Ignored without bit 1. |
| 0x1000 | UNSCALED_COMPONENT_OFFSET | Bit 12: the offset is in the parent's coordinate system and is not transformed. Ignored without bit 1. |
| 0xE010 | Reserved | Bits 4, 13, 14 and 15: must be 0. |

### Placement: offsets versus point matching

- ARGS_ARE_XY_VALUES must be set on the first component.
- Offset placement (ARGS_ARE_XY_VALUES set): (argument1, argument2) is a vector in design
  units added to every point of the child. In a variable font 'gvar' can vary this vector
  (see gvar.md, composite glyphs). Whether a scale or matrix also applies to the vector is
  governed by SCALED_COMPONENT_OFFSET / UNSCALED_COMPONENT_OFFSET (below). With
  ROUND_XY_TO_GRID also set, the final vector (after transform and variation deltas) is
  rounded to whole pixels.
- Point matching (ARGS_ARE_XY_VALUES clear): argument1 is a point number in the parent
  (counting the renumbered points of the components added so far), argument2 is a point
  number in the child (its own numbering, before renumbering). Phantom points of either glyph
  may be used. The child is moved so that the two points coincide; any transform is applied
  to the child's point before matching.
- Variable fonts with point matching: deltas are applied to the child glyphs before the
  points are matched, and any deltas the parent provides for such a component are ignored.

### Transforms

- At most one of WE_HAVE_A_SCALE, WE_HAVE_AN_X_AND_Y_SCALE and WE_HAVE_A_TWO_BY_TWO may be
  set. They add 1, 2 or 4 F2DOT14 values respectively.
- With WE_HAVE_A_TWO_BY_TWO the values are, in order, xscale, scale01, scale10, yscale, and a
  child point (x, y) becomes:
  - x' = xscale * x + scale10 * y
  - y' = scale01 * x + yscale * y
  (so the unit x vector maps to (xscale, scale01) and the unit y vector to (scale10, yscale)).
- WE_HAVE_AN_X_AND_Y_SCALE is the same with scale01 = scale10 = 0; WE_HAVE_A_SCALE further
  sets xscale = yscale = scale.
- The child is transformed as it is added to the parent, before the parent is grid-fitted.

### Scaled versus unscaled offsets

- SCALED_COMPONENT_OFFSET set: the offset is in the child's coordinate system, so the
  transform is applied to the offset as well.
- UNSCALED_COMPONENT_OFFSET set: the offset is in the parent's coordinate system and is used
  as is.
- Neither set: the rasterizer's default applies. Microsoft and Apple platforms behave as if
  UNSCALED_COMPONENT_OFFSET were set, and that default is the recommended one.
- Both set: invalid; the rasterizer uses its default behaviour.

### Other composite rules

- WE_HAVE_INSTRUCTIONS on any component means a uint16 instruction length, followed by the
  instruction bytes, comes right after the last component record.
- USE_MY_METRICS copies the child's metrics to the composite (for example a dotless i
  component inside i-circumflex keeps the composite's side bearings equal to the dotless i).
  Without it, lsb and rsb come from the composite's own 'hmtx' entry. The result is
  undefined when the component is rotated.
