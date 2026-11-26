# 'feat' table: feature names (digest)
Source: Feature Name Table - TrueType Reference Manual - Apple Developer, https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6feat.html
These notes restate the source's structures and rules; where they differ, the source governs.

## Purpose

'feat' lists the text features a font supports, the settings (selectors) of
each feature, and the 'name' table IDs of their human-readable names. The
feature and selector numbers come from Apple's Font Feature Registry (see
AppendixF.md). 'feat' and 'morx' describe the same features, so they must be
kept consistent with each other (see Chap6morx.md).

## Layout

Header, then the feature name array, then the setting name arrays.

### Header (12 bytes, then the feature name array)

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | fixed32 | version | 0x00010000 |
| 4 | uint16 | featureNameCount | number of FeatureName records |
| 6 | uint16 | (reserved) | 0 |
| 8 | uint32 | (reserved) | 0 |
| 12 | FeatureName[featureNameCount] | names | feature name array, sorted by feature type |

### FeatureName record (12 bytes)

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | feature | feature type |
| 2 | uint16 | nSettings | number of records in this feature's setting name array |
| 4 | uint32 | settingTable | offset from the start of 'feat' to this feature's setting name array (the page says the record type there depends on exclusivity, but defines only one setting record layout) |
| 8 | uint16 | featureFlags | see next table |
| 10 | int16 | nameIndex | 'name' table ID of the feature's name; 256 <= nameIndex < 32768 |

### featureFlags (uint16)

| Mask | Meaning |
|---|---|
| 0x8000 | exclusive: the settings are mutually exclusive |
| 0x4000 | clear: the setting at index 0 of the setting name array is the default (when one is needed); set: the low bits of featureFlags give the index of the default setting |
| 0x3F00 | unused, 0 |
| 0x00FF | index into the setting name array of the default setting, used when 0x8000 and 0x4000 are both set |

The page's prose calls the two high flags "bit 31" and "bit 30" and speaks of
"bits 0-15" or "bits 0-16" for the index; the mask values above are the ones
given in its table. Example value from the page: 0xC001 = exclusive, explicit
default, default index 1.

### SettingName record (4 bytes)

| Offset | Type | Field | Meaning |
|---|---|---|---|
| 0 | uint16 | setting | selector value |
| 2 | int16 | nameIndex | 'name' table ID of the setting's name; 256 <= nameIndex < 32768 |

Ordering: setting name arrays come after the feature name array; each array
is sorted by setting value; the arrays themselves may be in any order.

## Rules for settings

- Non-exclusive features come in on/off pairs: the "on" selector is even and
  the matching "off" selector is that value + 1 (always odd). Only the "on"
  selector is listed in the setting name array.
- Exclusive features: exactly one selector is in effect. One of them must
  describe the text as it looks when no selector is applied at all, so that a
  user interface can show which choice is active by default. Example: Letter
  Case (feature 3) defaults to its upper-and-lower-case selector.

## Choosing the default selector

The default can usually be inferred from 'morx', but featureFlags can state
it explicitly:

| 0x8000 (exclusive) | 0x4000 | Default selector |
|---|---|---|
| clear | any | not applicable; the default bits are ignored |
| set | clear | the setting at index 0 of the setting name array |
| set | set | the setting whose index is held in the low bits (mask 0x00FF) |

Whatever default featureFlags names must agree with what 'morx' implies.

## Feature type 39 (language tags)

Used together with 'ltag' for language-specific glyphs; it must be flagged
exclusive. Selector 0 = no change (language-independent forms); selector
n > 0 = the language at 'ltag' index n - 1. The designer decides which glyphs
are language-specific.

## Example from the page (condensed)

| Feature | featureFlags | Settings listed (value: name ID) |
|---|---|---|
| 0 All typographic features (name 260) | 0x0000 | 0: 261 |
| 1 Ligatures (name 256) | 0x0000 | 2 (common ligatures on): 257 |
| 3 Letter case (name 262) | 0x8000 | 0: 268, 3: 264, 4: 265 |
| 6 Number spacing (name 258) | 0xC001 | 0: 259, 1: 260 |

Letter case uses the first listed setting (upper and lower case) as default
because 0x4000 is clear; number spacing names index 1 (proportional) as
default.
