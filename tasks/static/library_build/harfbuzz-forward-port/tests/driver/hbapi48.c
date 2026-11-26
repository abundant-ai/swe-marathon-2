/*
 * hbapi48: probe hb_font_create_without_funcs_or_fail() of the HarfBuzz library it is linked against and print
 * integer results. It does not compile against a library that lacks the function.
 *
 * Input (stdin), one case per line, tab-separated, as for hbdrv:
 *   id <TAB> font file <TAB> face index <TAB> options <TAB> arguments
 * options: cmd=create, and funcs=1 to install client font functions on the new font afterwards and shape the
 * arguments (code points, hexadecimal, comma-separated) with them.
 * Every case makes a new face (from the file's cached blob, with the face index as given, named-instance bits
 * included) and a new font. Output, one line per case: id <TAB> result, integers only:
 *   nn:0 when the function returns NULL, otherwise
 *   nn:1|emp:<font is the empty font>|same:<font's face is the face>|fimm:<face immutable>|imm:<font immutable>|
 *   par:<parent is the empty font>|fu:<upem>,<glyph count> of the font's face after the caller released it|
 *   sc:<x scale>,<y scale>|pp:<x ppem>,<y ppem>|pt:<ptem>|sl:<synthetic slant>|
 *   bo:<x embolden>,<y embolden>,<in place>|ni:<named instance>|nc:<normalized coords>|dc:<design coords>|
 *   q:<nominal glyph of U+0041 found>,<its glyph>,<advance of glyph 1>,<font extents found>,<ascender>,<descender>
 *   and, with funcs=1, |s:<shaped glyphs>|x:<shaped advances>.
 * Floats are printed as f:<IEEE-754 bits in hex>. A setup failure prints !err:<word>.
 */
#include <hb.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINE (1 << 20)
#define MAX_ARGS 4096
#define MAX_OPTS 32
#define MAX_CACHE 1024

typedef struct
{
  char *path;
  hb_blob_t *blob;
} blob_entry_t;

static blob_entry_t blobs[MAX_CACHE];
static int n_blobs;

static hb_blob_t *
get_blob (const char *path)
{
  for (int i = 0; i < n_blobs; i++)
    if (!strcmp (blobs[i].path, path))
      return blobs[i].blob;
  hb_blob_t *blob = hb_blob_create_from_file_or_fail (path);
  if (!blob)
    return NULL;
  if (n_blobs < MAX_CACHE)
  {
    blobs[n_blobs].path = strdup (path);
    blobs[n_blobs].blob = blob;
    n_blobs++;
  }
  return blob;
}

static char *opt_key[MAX_OPTS], *opt_val[MAX_OPTS];
static int n_opts;

static const char *
opt (const char *key)
{
  for (int i = 0; i < n_opts; i++)
    if (!strcmp (opt_key[i], key))
      return opt_val[i];
  return NULL;
}

static int
parse_args (const char *s, uint32_t *out, int max)
{
  int n = 0;
  while (*s && n < max)
  {
    while (*s == ',' || *s == ' ')
      s++;
    if (!*s)
      break;
    char *end;
    unsigned long v = strtoul (s, &end, 16);
    if (end == s)
      return -1;
    out[n++] = (uint32_t) v;
    s = end;
  }
  return n;
}

static void
put_float (float v)
{
  uint32_t u;
  memcpy (&u, &v, sizeof (u));
  printf ("f:%08x", u);
}

/* Client font functions: code point U maps to glyph U - 0x20 (none below 0x21), glyph g advances 100 + 10 g. */
static hb_bool_t
client_nominal_glyph (hb_font_t *font, void *font_data, hb_codepoint_t unicode, hb_codepoint_t *glyph,
		      void *user_data)
{
  (void) font, (void) font_data, (void) user_data;
  if (unicode <= 0x20)
    return 0;
  *glyph = unicode - 0x20;
  return 1;
}

static hb_position_t
client_h_advance (hb_font_t *font, void *font_data, hb_codepoint_t glyph, void *user_data)
{
  (void) font, (void) font_data, (void) user_data;
  return (hb_position_t) (100 + 10 * glyph);
}

static hb_font_funcs_t *
client_funcs (void)
{
  static hb_font_funcs_t *funcs;
  if (!funcs)
  {
    funcs = hb_font_funcs_create ();
    hb_font_funcs_set_nominal_glyph_func (funcs, client_nominal_glyph, NULL, NULL);
    hb_font_funcs_set_glyph_h_advance_func (funcs, client_h_advance, NULL, NULL);
    hb_font_funcs_make_immutable (funcs);
  }
  return funcs;
}

static void
run (const char *path, unsigned index, const uint32_t *args, int n_args)
{
  hb_blob_t *blob = get_blob (path);
  if (!blob)
  {
    printf ("!err:nofile");
    return;
  }
  hb_face_t *face = hb_face_create (blob, index);
  hb_font_t *font = hb_font_create_without_funcs_or_fail (face);
  if (!font)
  {
    printf ("nn:0");
    hb_face_destroy (face);
    return;
  }
  /* The font keeps the face alive: drop the caller's reference before using the font's face. */
  int face_immutable = hb_face_is_immutable (face);
  int same = hb_font_get_face (font) == face;
  hb_face_destroy (face);
  hb_face_t *kept = hb_font_get_face (font);

  int x_scale = 0, y_scale = 0;
  unsigned x_ppem = 0, y_ppem = 0;
  float x_bold = 0, y_bold = 0;
  hb_bool_t in_place = 0;
  hb_font_get_scale (font, &x_scale, &y_scale);
  hb_font_get_ppem (font, &x_ppem, &y_ppem);
  hb_font_get_synthetic_bold (font, &x_bold, &y_bold, &in_place);
  printf ("nn:1|emp:%d|same:%d|fimm:%d|imm:%d|par:%d|fu:%u,%u|sc:%d,%d|pp:%u,%u|pt:", font == hb_font_get_empty (),
	  same, face_immutable, (int) hb_font_is_immutable (font), hb_font_get_parent (font) == hb_font_get_empty (),
	  hb_face_get_upem (kept), hb_face_get_glyph_count (kept), x_scale, y_scale, x_ppem, y_ppem);
  put_float (hb_font_get_ptem (font));
  printf ("|sl:");
  put_float (hb_font_get_synthetic_slant (font));
  printf ("|bo:");
  put_float (x_bold);
  putchar (',');
  put_float (y_bold);
  printf (",%d|ni:%u|nc:", (int) in_place, hb_font_get_var_named_instance (font));
  unsigned n = 0;
  const int *coords = hb_font_get_var_coords_normalized (font, &n);
  for (unsigned i = 0; i < n; i++)
    printf ("%s%d", i ? "," : "", coords[i]);
  printf ("|dc:");
  const float *design = hb_font_get_var_coords_design (font, &n);
  for (unsigned i = 0; i < n; i++)
  {
    if (i)
      putchar (',');
    put_float (design[i]);
  }

  hb_codepoint_t glyph = 0;
  hb_bool_t found = hb_font_get_nominal_glyph (font, 0x41, &glyph);
  hb_font_extents_t extents;
  memset (&extents, 0, sizeof (extents));
  hb_bool_t have_extents = hb_font_get_h_extents (font, &extents);
  printf ("|q:%d,%u,%d,%d,%d,%d", (int) found, glyph, hb_font_get_glyph_h_advance (font, 1), (int) have_extents,
	  extents.ascender, extents.descender);

  const char *v = opt ("funcs");
  if (v && atoi (v))
  {
    hb_font_set_funcs (font, client_funcs (), NULL, NULL);
    hb_buffer_t *buf = hb_buffer_create ();
    hb_buffer_add_codepoints (buf, args, n_args, 0, n_args);
    hb_buffer_guess_segment_properties (buf);
    hb_shape (font, buf, NULL, 0);
    unsigned len = 0;
    hb_glyph_info_t *info = hb_buffer_get_glyph_infos (buf, &len);
    hb_glyph_position_t *pos = hb_buffer_get_glyph_positions (buf, NULL);
    printf ("|s:");
    for (unsigned i = 0; i < len; i++)
      printf ("%s%u", i ? "," : "", info[i].codepoint);
    printf ("|x:");
    for (unsigned i = 0; i < len; i++)
      printf ("%s%d", i ? "," : "", pos[i].x_advance);
    hb_buffer_destroy (buf);
  }
  hb_font_destroy (font);
}

static void
run_case (char *line)
{
  char *fields[5];
  int nf = 0;
  for (char *p = line; nf < 5;)
  {
    fields[nf++] = p;
    char *tab = strchr (p, '\t');
    if (!tab)
      break;
    *tab = 0;
    p = tab + 1;
  }
  if (nf < 5)
  {
    if (nf >= 1)
      printf ("%s\t!err:line\n", fields[0]);
    return;
  }
  n_opts = 0;
  char *save = NULL;
  for (char *kv = strtok_r (fields[3], ";", &save); kv && n_opts < MAX_OPTS; kv = strtok_r (NULL, ";", &save))
  {
    char *eq = strchr (kv, '=');
    if (!eq)
      continue;
    *eq = 0;
    opt_key[n_opts] = kv;
    opt_val[n_opts] = eq + 1;
    n_opts++;
  }
  static uint32_t args[MAX_ARGS];
  int n_args = parse_args (fields[4], args, MAX_ARGS);
  const char *cmd = opt ("cmd");
  printf ("%s\t", fields[0]);
  if (n_args < 0)
    printf ("!err:args");
  else if (!cmd || strcmp (cmd, "create"))
    printf ("!err:cmd");
  else
    run (fields[1], (unsigned) strtoul (fields[2], NULL, 10), args, n_args);
  putchar ('\n');
}

int
main (void)
{
  static char line[MAX_LINE];
  while (fgets (line, sizeof (line), stdin))
  {
    size_t n = strlen (line);
    while (n && (line[n - 1] == '\n' || line[n - 1] == '\r'))
      line[--n] = 0;
    if (!n || line[0] == '#')
      continue;
    run_case (line);
    fflush (stdout);
  }
  return 0;
}
