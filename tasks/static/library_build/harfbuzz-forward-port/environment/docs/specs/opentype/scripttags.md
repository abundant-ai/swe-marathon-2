# Script Tags
Source: Script tags (OpenType 1.9.1), https://learn.microsoft.com/en-us/typography/opentype/spec/scripttags
These notes restate the source's structures and rules; where they differ, the source governs.

## How script tags relate to scripts

- A script tag is a 4-byte Tag (see otff.md, Data types) stored in a ScriptRecord of the
  GSUB, GPOS, BASE or JSTF ScriptList. How Script Records are selected and processed is in
  chapter2.md (ScriptList table and ScriptRecord).
- Registered script tags are four lowercase ASCII letters by convention. A shorter name is
  padded with spaces (0x20) to four bytes, as in 'lao ', 'nko ', 'vai ' and 'yi  '.
- A tag usually corresponds to one Unicode script, but not always one-to-one. Tags are not
  guaranteed to equal Unicode Script property value aliases or ISO 15924 codes, and the rules
  for choosing them differ, because OpenType tags predate both.
- One Unicode script can have several registered tags when each selects a different
  OpenType Layout shaping implementation. The second-generation Indic tags ('bng2',
  'dev2', 'gjr2', 'gur2', 'knd2', 'mlm2', 'ory2', 'tml2', 'tel2') and 'mym2' are of this
  kind; the older tags ('beng', 'deva', 'gujr', 'guru', 'knda', 'mlym', 'orya', 'taml',
  'telu', 'mymr') remain registered.
- DFLT is the default script tag (written without quotes in the source table). See
  chapter2.md for how the default script is used when no matching script is present.

## Registered script tags

The table lists every registered tag in the source's order (alphabetical by script name,
as the source names the scripts).

| Script | Script Tag | Remarks |
|---|---|---|
| Adlam | 'adlm' |  |
| Ahom | 'ahom' |  |
| Anatolian Hieroglyphs | 'hluw' |  |
| Arabic | 'arab' |  |
| Armenian | 'armn' |  |
| Avestan | 'avst' |  |
| Balinese | 'bali' |  |
| Bamum | 'bamu' |  |
| Bassa Vah | 'bass' |  |
| Batak | 'batk' |  |
| Bangla | 'beng' |  |
| Bangla v.2 | 'bng2' |  |
| Beria Erfe | 'berf' |  |
| Bhaiksuki | 'bhks' |  |
| Bopomofo | 'bopo' |  |
| Brahmi | 'brah' |  |
| Braille | 'brai' |  |
| Buginese | 'bugi' |  |
| Buhid | 'buhd' |  |
| Byzantine Music | 'byzm' |  |
| Canadian Syllabics | 'cans' |  |
| Carian | 'cari' |  |
| Caucasian Albanian | 'aghb' |  |
| Chakma | 'cakm' |  |
| Cham | 'cham' |  |
| Cherokee | 'cher' |  |
| Chorasmian | 'chrs' |  |
| CJK Ideographic | 'hani' |  |
| Coptic | 'copt' |  |
| Cypriot Syllabary | 'cprt' |  |
| Cypro-Minoan | 'cpmn' |  |
| Cyrillic | 'cyrl' |  |
| Default | DFLT |  |
| Deseret | 'dsrt' |  |
| Devanagari | 'deva' |  |
| Devanagari v.2 | 'dev2' |  |
| Dives Akuru | 'diak' |  |
| Dogra | 'dogr' |  |
| Duployan | 'dupl' |  |
| Egyptian Hieroglyphs | 'egyp' |  |
| Elbasan | 'elba' |  |
| Elymaic | 'elym' |  |
| Ethiopic | 'ethi' |  |
| Garay | 'gara' |  |
| Georgian | 'geor' |  |
| Glagolitic | 'glag' |  |
| Gothic | 'goth' |  |
| Grantha | 'gran' |  |
| Greek | 'grek' |  |
| Gujarati | 'gujr' |  |
| Gujarati v.2 | 'gjr2' |  |
| Gunjala Gondi | 'gong' |  |
| Gurmukhi | 'guru' |  |
| Gurmukhi v.2 | 'gur2' |  |
| Gurung Khema | 'gukh' |  |
| Hangul | 'hang' |  |
| Hangul Jamo | 'jamo' | Not recommended. Fonts for Unicode conjoining jamo use 'hang' instead. |
| Hanifi Rohingya | 'rohg' |  |
| Hanunoo | 'hano' |  |
| Hatran | 'hatr' |  |
| Hebrew | 'hebr' |  |
| Hiragana | 'kana' |  |
| Imperial Aramaic | 'armi' |  |
| Inscriptional Pahlavi | 'phli' |  |
| Inscriptional Parthian | 'prti' |  |
| Javanese | 'java' |  |
| Jurchen | 'jurc' |  |
| Kaithi | 'kthi' |  |
| Kannada | 'knda' |  |
| Kannada v.2 | 'knd2' |  |
| Katakana | 'kana' |  |
| Kawi | 'kawi' |  |
| Kayah Li | 'kali' |  |
| Kharosthi | 'khar' |  |
| Khitan Small Script | 'kits' |  |
| Khmer | 'khmr' |  |
| Khojki | 'khoj' |  |
| Khudawadi | 'sind' |  |
| Kirat Rai | 'krai' |  |
| Lao | 'lao ' |  |
| Latin | 'latn' |  |
| Lepcha | 'lepc' |  |
| Limbu | 'limb' |  |
| Linear A | 'lina' |  |
| Linear B | 'linb' |  |
| Lisu (Fraser) | 'lisu' |  |
| Lycian | 'lyci' |  |
| Lydian | 'lydi' |  |
| Mahajani | 'mahj' |  |
| Makasar | 'maka' |  |
| Malayalam | 'mlym' |  |
| Malayalam v.2 | 'mlm2' |  |
| Mandaic, Mandaean | 'mand' |  |
| Manichaean | 'mani' |  |
| Marchen | 'marc' |  |
| Masaram Gondi | 'gonm' |  |
| Mathematical text layout | 'math' | For math layout engines; features tied to MATH table layout use it. |
| Medefaidrin (Oberi Okaime) | 'medf' |  |
| Meitei Mayek (Meithei, Meetei) | 'mtei' |  |
| Mende Kikakui | 'mend' |  |
| Meroitic Cursive | 'merc' |  |
| Meroitic Hieroglyphs | 'mero' |  |
| Miao | 'plrd' |  |
| Modi | 'modi' |  |
| Mongolian | 'mong' |  |
| Mro | 'mroo' |  |
| Multani | 'mult' |  |
| Musical Symbols | 'musc' |  |
| Myanmar | 'mymr' | Not recommended. Fonts for Unicode-encoded Myanmar use 'mym2' instead. |
| Myanmar v.2 | 'mym2' |  |
| Nabataean | 'nbat' |  |
| Nag Mundari | 'nagm' |  |
| Nandinagari | 'nand' |  |
| Newa | 'newa' |  |
| New Tai Lue | 'talu' |  |
| N'Ko | 'nko ' |  |
| Nushu | 'nshu' |  |
| Nyiakeng Puachue Hmong | 'hmnp' |  |
| Odia | 'orya' |  |
| Odia v.2 | 'ory2' |  |
| Ogham | 'ogam' |  |
| Ol Chiki | 'olck' |  |
| Ol Onal | 'onao' |  |
| Old Italic | 'ital' |  |
| Old Hungarian | 'hung' |  |
| Old North Arabian | 'narb' |  |
| Old Permic | 'perm' |  |
| Old Persian Cuneiform | 'xpeo' |  |
| Old Sogdian | 'sogo' |  |
| Old South Arabian | 'sarb' |  |
| Old Turkic, Orkhon Runic | 'orkh' |  |
| Old Uyghur | 'ougr' |  |
| Osage | 'osge' |  |
| Osmanya | 'osma' |  |
| Pahawh Hmong | 'hmng' |  |
| Palmyrene | 'palm' |  |
| Pau Cin Hau | 'pauc' |  |
| Phags-pa | 'phag' |  |
| Phoenician | 'phnx' |  |
| Proto-Cuneiform | 'pcun' |  |
| Psalter Pahlavi | 'phlp' |  |
| Rejang | 'rjng' |  |
| Runic | 'runr' |  |
| Samaritan | 'samr' |  |
| Saurashtra | 'saur' |  |
| Seal ("Small Seal") | 'seal' |  |
| Sharada | 'shrd' |  |
| Shavian | 'shaw' |  |
| Siddham | 'sidd' |  |
| Sidetic | 'sidt' |  |
| Sign Writing | 'sgnw' |  |
| Sinhala | 'sinh' |  |
| Sogdian | 'sogd' |  |
| Sora Sompeng | 'sora' |  |
| Soyombo | 'soyo' |  |
| Sumero-Akkadian Cuneiform | 'xsux' |  |
| Sundanese | 'sund' |  |
| Sunuwar | 'sunu' |  |
| Syloti Nagri | 'sylo' |  |
| Syriac | 'syrc' |  |
| Tagalog | 'tglg' |  |
| Tagbanwa | 'tagb' |  |
| Tai Le | 'tale' |  |
| Tai Tham (Lanna) | 'lana' |  |
| Tai Viet | 'tavt' |  |
| Tai Yo | 'tayo' |  |
| Takri | 'takr' |  |
| Tamil | 'taml' |  |
| Tamil v.2 | 'tml2' |  |
| Tangsa | 'tnsa' |  |
| Tangut | 'tang' |  |
| Telugu | 'telu' |  |
| Telugu v.2 | 'tel2' |  |
| Thaana | 'thaa' |  |
| Thai | 'thai' |  |
| Tibetan | 'tibt' |  |
| Tifinagh | 'tfng' |  |
| Tirhuta | 'tirh' |  |
| Todhri | 'todr' |  |
| Tolong Siki | 'tols' |  |
| Toto | 'toto' |  |
| Tulu-Tigalari | 'tutg' |  |
| Ugaritic Cuneiform | 'ugar' |  |
| Vai | 'vai ' |  |
| Vithkuqi | 'vith' |  |
| Wancho | 'wcho' |  |
| Warang Citi | 'wara' |  |
| Yezidi | 'yezi' |  |
| Yi | 'yi  ' | Tag bytes are 0x79 0x69 0x20 0x20 ('yi' plus two spaces). |
| Zanabazar Square (Zanabazarin Dorboljin Useg, Xewtee Dorboljin Bicig, Horizontal Square Script) | 'zanb' |  |

Notes on special rows:

- 'yi  ' is the only registered tag with two padding spaces. The source displays it with
  NO-BREAK SPACE characters only so that both spaces stay visible; the stored bytes are
  ordinary spaces.
- 'kana' covers both Hiragana and Katakana; 'hani' covers CJK ideographs; 'hang' covers
  Hangul including conjoining jamo.
