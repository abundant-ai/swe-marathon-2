/*
 * hbmeta: query style values, metrics, baselines, cmap coverage, glyph alternates, faces and fonts through the
 * public API of the HarfBuzz library it is linked against, and print integer results.
 *
 * Input (stdin), one case per line, tab-separated, as for hbdrv:
 *   id <TAB> font file <TAB> face index <TAB> options <TAB> arguments
 * arguments: hexadecimal integers separated by commas.
 * options: semicolon-separated key=value pairs. cmd=<command> selects the command. Font settings, honoured by
 * every command that makes a font: scale=<int>[,<int>] ppem=<int>,<int> ptem=<decimal> slant=<decimal>
 * bold=<x>,<y> boldin=1 var=<tag>=<value>,... inst=<named instance>
 * Output (stdout), one line per case: id <TAB> result. A result holds integers only (lists joined with ',',
 * groups with '|', key:value pairs); a float is printed as its IEEE-754 bits, f:<8 hex digits>. A setup
 * failure prints !err:<word>.
 *
 * Commands:
 *   style       arguments: style tags. hb_style_get_value() for each: f:<bits>,...
 *   unicodes    hb_face_collect_unicodes(): n:<count>|<first>:<last>,... (ascending ranges).
 *   metric      arguments: metrics tags. hb_ot_metrics_get_position_with_fallback() for each.
 *   baseline    arguments: baseline tags. dir=ltr|rtl|ttb|btt. With script=<ISO 15924 tag> and lang=<BCP 47>
 *               it calls hb_ot_layout_get_baseline_with_fallback2(), otherwise
 *               hb_ot_layout_get_baseline_with_fallback() with stag=<script tag> and ltag=<language tag>.
 *   alts        arguments: GSUB lookup indices, collected in turn into the same two maps, which
 *               seed=<glyph>:<count>,... (decimal) fills first. hb_ot_layout_lookup_collect_glyph_alternates():
 *               r:<return values>|c:<glyph>:<count>,...|a:<key>:<glyph>,... (both maps sorted by key). The stack
 *               is zeroed before each call (see scrub_stack).
 *   faceorfail  hb_face_create_or_fail() on the file's blob with the face index: ok:0, or
 *               ok:1|ix:<face index>|g:<glyph count>|u:<upem>|ni:<named instance>|c:<normalized coords> where the
 *               last two are those of hb_font_create() on the new face.
 *   setface     arguments: code points. hb_font_set_face() on a font of the case's face with face2=<font file>
 *               and idx2=<face index>, or face2=null (a NULL face), or same=1 (the font's own face); imm=1 makes
 *               the font immutable first. Then: o:<1 if the font still has the case's face>|u:<upem>|n:<glyph
 *               count> of the font's face|g:<nominal glyphs, -1 when missing>|a:<horizontal advances>|
 *               s:<shaped glyphs>|x:<shaped advances>.
 *
 * Faces are cached per (file, index) and blobs per file; every case gets a fresh font. Only public API that
 * HarfBuzz 14.3.0 declares is used.
 */
#include <hb.h>
#include <hb-ot.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINE (1 << 20)
#define MAX_ARGS 4096
#define MAX_OPTS 32
#define MAX_VARS 16
#define MAX_CACHE 1024
#define MAX_ITEMS 65536

typedef struct
{
  char *path;
  hb_blob_t *blob;
} blob_entry_t;

typedef struct
{
  char *path;
  unsigned index;
  hb_face_t *face;
} face_entry_t;

static blob_entry_t blobs[MAX_CACHE];
static int n_blobs;
static face_entry_t faces[MAX_CACHE];
static int n_faces;

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

static hb_face_t *
get_face (const char *path, unsigned index)
{
  for (int i = 0; i < n_faces; i++)
    if (faces[i].index == index && !strcmp (faces[i].path, path))
      return faces[i].face;
  hb_blob_t *blob = get_blob (path);
  if (!blob)
    return NULL;
  hb_face_t *face = hb_face_create (blob, index);
  if (n_faces < MAX_CACHE)
  {
    faces[n_faces].path = strdup (path);
    faces[n_faces].index = index;
    faces[n_faces].face = face;
    n_faces++;
  }
  return face;
}

/* Options of the current case. */
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

static hb_tag_t
tag_of (const char *s)
{
  char t[4] = {' ', ' ', ' ', ' '};
  for (size_t i = 0; i < 4 && s[i]; i++)
    t[i] = s[i];
  return HB_TAG (t[0], t[1], t[2], t[3]);
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

/* A fresh font on the face, with the case's font settings. */
static hb_font_t *
make_font (hb_face_t *face)
{
  hb_font_t *font = hb_font_create (face);
  const char *v;
  if ((v = opt ("inst")))
    hb_font_set_var_named_instance (font, (unsigned) strtoul (v, NULL, 10));
  if ((v = opt ("var")))
  {
    hb_variation_t vars[MAX_VARS];
    unsigned n = 0;
    char tmp[512];
    snprintf (tmp, sizeof (tmp), "%s", v);
    char *save = NULL;
    for (char *item = strtok_r (tmp, ",", &save); item && n < MAX_VARS; item = strtok_r (NULL, ",", &save))
    {
      char *eq = strchr (item, '=');
      if (!eq)
	continue;
      *eq = 0;
      vars[n].tag = tag_of (item);
      vars[n].value = strtof (eq + 1, NULL);
      n++;
    }
    hb_font_set_variations (font, vars, n);
  }
  if ((v = opt ("scale")))
  {
    char *end;
    long x = strtol (v, &end, 10);
    long y = *end == ',' ? strtol (end + 1, NULL, 10) : x;
    hb_font_set_scale (font, (int) x, (int) y);
  }
  if ((v = opt ("ppem")))
  {
    char *end;
    unsigned long x = strtoul (v, &end, 10);
    unsigned long y = *end == ',' ? strtoul (end + 1, NULL, 10) : x;
    hb_font_set_ppem (font, (unsigned) x, (unsigned) y);
  }
  if ((v = opt ("ptem")))
    hb_font_set_ptem (font, strtof (v, NULL));
  if ((v = opt ("slant")))
    hb_font_set_synthetic_slant (font, strtof (v, NULL));
  if ((v = opt ("bold")))
  {
    char *end;
    float x = strtof (v, &end);
    float y = *end == ',' ? strtof (end + 1, NULL) : x;
    const char *in = opt ("boldin");
    hb_font_set_synthetic_bold (font, x, y, in && atoi (in));
  }
  return font;
}

typedef struct
{
  uint32_t key, value;
} pair_t;

static int
cmp_pair (const void *a, const void *b)
{
  uint32_t x = ((const pair_t *) a)->key, y = ((const pair_t *) b)->key;
  return x < y ? -1 : x > y;
}

static pair_t items[MAX_ITEMS];

static void
put_map (const hb_map_t *map)
{
  int n = 0, pos = -1;
  hb_codepoint_t key, value;
  while (n < MAX_ITEMS && hb_map_next (map, &pos, &key, &value))
  {
    items[n].key = key;
    items[n].value = value;
    n++;
  }
  qsort (items, (size_t) n, sizeof (items[0]), cmp_pair);
  for (int i = 0; i < n; i++)
    printf ("%s%u:%u", i ? "," : "", items[i].key, items[i].value);
}

static void
cmd_style (hb_face_t *face, const uint32_t *args, int n_args)
{
  hb_font_t *font = make_font (face);
  for (int i = 0; i < n_args; i++)
  {
    if (i)
      putchar (',');
    put_float (hb_style_get_value (font, (hb_style_tag_t) args[i]));
  }
  hb_font_destroy (font);
}

static void
cmd_unicodes (hb_face_t *face)
{
  hb_set_t *set = hb_set_create ();
  hb_face_collect_unicodes (face, set);
  printf ("n:%u", hb_set_get_population (set));
  hb_codepoint_t first = HB_SET_VALUE_INVALID, last = HB_SET_VALUE_INVALID;
  for (int i = 0; hb_set_next_range (set, &first, &last); i++)
    printf ("%c%u:%u", i ? ',' : '|', first, last);
  hb_set_destroy (set);
}

static void
cmd_metric (hb_face_t *face, const uint32_t *args, int n_args)
{
  hb_font_t *font = make_font (face);
  for (int i = 0; i < n_args; i++)
  {
    hb_position_t position = 0;
    hb_ot_metrics_get_position_with_fallback (font, (hb_ot_metrics_tag_t) args[i], &position);
    printf ("%s%d", i ? "," : "", position);
  }
  hb_font_destroy (font);
}

static void
cmd_baseline (hb_face_t *face, const uint32_t *args, int n_args)
{
  hb_font_t *font = make_font (face);
  const char *d = opt ("dir"), *script = opt ("script"), *lang = opt ("lang");
  const char *stag = opt ("stag"), *ltag = opt ("ltag");
  hb_direction_t dir = d ? hb_direction_from_string (d, -1) : HB_DIRECTION_LTR;
  for (int i = 0; i < n_args; i++)
  {
    hb_position_t coord = 0;
    hb_ot_layout_baseline_tag_t tag = (hb_ot_layout_baseline_tag_t) args[i];
    if (script)
      hb_ot_layout_get_baseline_with_fallback2 (font, tag, dir,
						 hb_script_from_iso15924_tag (tag_of (script)),
						 lang ? hb_language_from_string (lang, -1) : HB_LANGUAGE_INVALID,
						 &coord);
    else
      hb_ot_layout_get_baseline_with_fallback (font, tag, dir,
						stag ? tag_of (stag) : HB_OT_TAG_DEFAULT_SCRIPT,
						ltag ? tag_of (ltag) : HB_OT_TAG_DEFAULT_LANGUAGE,
						&coord);
    printf ("%s%d", i ? "," : "", coord);
  }
  hb_font_destroy (font);
}

/* Zero the stack below the caller. HarfBuzz 14.3.0 and 15.0.0 read a dead lambda parameter while collecting
 * glyph alternates; whatever the compiler makes of that read, it then never sees what earlier cases left on the
 * stack. */
static void __attribute__ ((noinline))
scrub_stack (void)
{
  volatile unsigned char buf[65536];
  for (size_t i = 0; i < sizeof (buf); i++)
    buf[i] = 0;
}

static void
cmd_alts (hb_face_t *face, const uint32_t *args, int n_args)
{
  hb_map_t *count = hb_map_create (), *glyphs = hb_map_create ();
  const char *seed = opt ("seed");
  if (seed)
  {
    char tmp[1024];
    snprintf (tmp, sizeof (tmp), "%s", seed);
    char *save = NULL;
    for (char *item = strtok_r (tmp, ",", &save); item; item = strtok_r (NULL, ",", &save))
    {
      char *colon = strchr (item, ':');
      if (colon)
	hb_map_set (count, (hb_codepoint_t) strtoul (item, NULL, 10), (hb_codepoint_t) strtoul (colon + 1, NULL, 10));
    }
  }
  printf ("r:");
  for (int i = 0; i < n_args; i++)
  {
    scrub_stack ();
    int ret = (int) hb_ot_layout_lookup_collect_glyph_alternates (face, args[i], count, glyphs);
    printf ("%s%d", i ? "," : "", ret);
  }
  printf ("|c:");
  put_map (count);
  printf ("|a:");
  put_map (glyphs);
  hb_map_destroy (count);
  hb_map_destroy (glyphs);
}

static void
cmd_faceorfail (const char *path, unsigned index)
{
  hb_blob_t *blob = get_blob (path);
  if (!blob)
  {
    printf ("!err:nofile");
    return;
  }
  hb_face_t *face = hb_face_create_or_fail (blob, index);
  if (!face)
  {
    printf ("ok:0");
    return;
  }
  printf ("ok:1|ix:%u|g:%u|u:%u", hb_face_get_index (face), hb_face_get_glyph_count (face), hb_face_get_upem (face));
  hb_font_t *font = hb_font_create (face);
  unsigned n = 0;
  const int *coords = hb_font_get_var_coords_normalized (font, &n);
  printf ("|ni:%u|c:", hb_font_get_var_named_instance (font));
  for (unsigned i = 0; i < n; i++)
    printf ("%s%d", i ? "," : "", coords[i]);
  hb_font_destroy (font);
  hb_face_destroy (face);
}

static void
cmd_setface (hb_face_t *face, const uint32_t *args, int n_args)
{
  hb_font_t *font = make_font (face);
  const char *v = opt ("imm");
  if (v && atoi (v))
    hb_font_make_immutable (font);
  hb_face_t *other;
  v = opt ("same");
  if (v && atoi (v))
    other = face;
  else
  {
    const char *path = opt ("face2"), *idx = opt ("idx2");
    if (!path || !strcmp (path, "null"))
      other = NULL;
    else if (!(other = get_face (path, idx ? (unsigned) strtoul (idx, NULL, 10) : 0)))
    {
      printf ("!err:nofile");
      hb_font_destroy (font);
      return;
    }
  }
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wdeprecated-declarations"
  hb_font_set_face (font, other);
#pragma GCC diagnostic pop

  hb_face_t *now = hb_font_get_face (font);
  printf ("o:%d|u:%u|n:%u|g:", now == face, hb_face_get_upem (now), hb_face_get_glyph_count (now));
  for (int i = 0; i < n_args; i++)
  {
    hb_codepoint_t glyph = 0;
    if (hb_font_get_nominal_glyph (font, args[i], &glyph))
      printf ("%s%u", i ? "," : "", glyph);
    else
      printf ("%s-1", i ? "," : "");
  }
  printf ("|a:");
  for (int i = 0; i < n_args; i++)
  {
    hb_codepoint_t glyph = 0;
    hb_font_get_nominal_glyph (font, args[i], &glyph);
    printf ("%s%d", i ? "," : "", hb_font_get_glyph_h_advance (font, glyph));
  }
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
  hb_font_destroy (font);
}

static void
run_case (char *line)
{
  /* Split on tabs by hand: strtok_r would merge two tabs and lose an empty options field. */
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
  const char *id = fields[0], *path = fields[1];
  unsigned index = (unsigned) strtoul (fields[2], NULL, 10);

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
  if (n_args < 0 || !cmd)
  {
    printf ("%s\t!err:args\n", id);
    return;
  }

  printf ("%s\t", id);
  if (!strcmp (cmd, "faceorfail"))
    cmd_faceorfail (path, index);
  else
  {
    hb_face_t *face = get_face (path, index);
    if (!face)
      printf ("!err:nofile");
    else if (!strcmp (cmd, "style"))
      cmd_style (face, args, n_args);
    else if (!strcmp (cmd, "unicodes"))
      cmd_unicodes (face);
    else if (!strcmp (cmd, "metric"))
      cmd_metric (face, args, n_args);
    else if (!strcmp (cmd, "baseline"))
      cmd_baseline (face, args, n_args);
    else if (!strcmp (cmd, "alts"))
      cmd_alts (face, args, n_args);
    else if (!strcmp (cmd, "setface"))
      cmd_setface (face, args, n_args);
    else
      printf ("!err:cmd");
  }
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
