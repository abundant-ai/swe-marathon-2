/*
 * hbprops: print the library's own Unicode properties for a range of code points.
 *
 * Usage: hbprops FIRST LAST   (hexadecimal, inclusive)
 * Output, one line per code point: cp general_category combining_class script mirroring decomposition composition
 *   decomposition: the two code points of the canonical decomposition, or "-"
 *   composition: the code point composed with U+0300..U+036F etc. is not enumerated here; "-" when none for the pair
 * Only public API present in 14.3.0 is used.
 */
#include <hb.h>

#include <stdio.h>
#include <stdlib.h>

int
main (int argc, char **argv)
{
  if (argc != 3)
    return 2;
  hb_codepoint_t first = (hb_codepoint_t) strtoul (argv[1], NULL, 16);
  hb_codepoint_t last = (hb_codepoint_t) strtoul (argv[2], NULL, 16);
  hb_unicode_funcs_t *uf = hb_unicode_funcs_get_default ();
  for (hb_codepoint_t cp = first; cp <= last; cp++)
  {
    hb_codepoint_t a = 0, b = 0, ab = 0;
    hb_script_t sc = hb_unicode_script (uf, cp);
    char tag[5];
    hb_tag_to_string (hb_script_to_iso15924_tag (sc), tag);
    tag[4] = 0;
    printf ("%04X %d %u %s %04X", cp, (int) hb_unicode_general_category (uf, cp), hb_unicode_combining_class (uf, cp),
	    tag, hb_unicode_mirroring (uf, cp));
    if (hb_unicode_decompose (uf, cp, &a, &b))
    {
      printf (" %04X,%04X", a, b);
      printf (" %s", hb_unicode_compose (uf, a, b, &ab) && ab == cp ? "c" : "n");
    }
    else
      fputs (" - -", stdout);
    putchar ('\n');
  }
  return 0;
}
