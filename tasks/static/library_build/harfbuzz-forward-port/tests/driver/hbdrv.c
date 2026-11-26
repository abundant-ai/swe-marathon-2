/*
 * hbdrv: shape a batch of cases with the HarfBuzz library it is linked against and print integer results.
 *
 * Input (stdin), one case per line, tab-separated:
 *   id <TAB> font file <TAB> face index <TAB> options <TAB> text
 * text: hexadecimal code points separated by commas, for example 1780,17D2,179A.
 * options: semicolon-separated key=value pairs, all optional:
 *   dir=ltr|rtl|ttb|btt   script=Khmr   lang=km   cl=0..3
 *   feat=tag[=value][@start:end],...   (value 1 when omitted; start and end are cluster indices)
 *   var=tag=value,...   nf=<glyph id>   flags=bot,eot,pdi,rdi,nodc,utc,tatweel
 *   pre=<code points>   post=<code points>   scale=<int>[,<int y>]   ppem=<int>
 *   slant=<float>   bold=<float>,<float>   gf=1 (print glyph flags)   names=1 (glyph names)
 * Output (stdout), one line per case:
 *   id <TAB> glyph=cluster@x_offset,y_offset+x_advance,y_advance[#flags]|...
 * or id <TAB> !error text.
 *
 * Feature and variation strings are parsed here, not by the library, so the result never depends on the
 * library's own string parsers. Only public API present in 14.3.0 is used.
 */
#include <hb.h>
#include <hb-ot.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINE (1 << 20)
#define MAX_CPS 4096
#define MAX_FEATS 64
#define MAX_VARS 16
#define MAX_FACES 512

typedef struct
{
  char *path;
  unsigned index;
  hb_face_t *face;
} face_entry_t;

static face_entry_t faces[MAX_FACES];
static int n_faces;

static hb_face_t *
get_face (const char *path, unsigned index)
{
  for (int i = 0; i < n_faces; i++)
    if (faces[i].index == index && !strcmp (faces[i].path, path))
      return faces[i].face;
  hb_blob_t *blob = hb_blob_create_from_file_or_fail (path);
  if (!blob)
    return NULL;
  hb_face_t *face = hb_face_create (blob, index);
  hb_blob_destroy (blob);
  if (n_faces < MAX_FACES)
  {
    faces[n_faces].path = strdup (path);
    faces[n_faces].index = index;
    faces[n_faces].face = face;
    n_faces++;
  }
  return face;
}

static hb_tag_t
tag_of (const char *s, size_t n)
{
  char t[4] = {' ', ' ', ' ', ' '};
  for (size_t i = 0; i < n && i < 4; i++)
    t[i] = s[i];
  return HB_TAG (t[0], t[1], t[2], t[3]);
}

static int
parse_cps (const char *s, hb_codepoint_t *out, int max)
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
    out[n++] = (hb_codepoint_t) v;
    s = end;
  }
  return n;
}

/* tag[=value][@start:end] items separated by commas. */
static int
parse_features (char *s, hb_feature_t *out, int max)
{
  int n = 0;
  char *save = NULL;
  for (char *item = strtok_r (s, ",", &save); item && n < max; item = strtok_r (NULL, ",", &save))
  {
    hb_feature_t f = {0, 1, HB_FEATURE_GLOBAL_START, HB_FEATURE_GLOBAL_END};
    char *at = strchr (item, '@');
    if (at)
    {
      *at = 0;
      char *colon = strchr (at + 1, ':');
      if (!colon)
        return -1;
      f.start = (unsigned) strtoul (at + 1, NULL, 10);
      f.end = (unsigned) strtoul (colon + 1, NULL, 10);
    }
    char *eq = strchr (item, '=');
    if (eq)
    {
      *eq = 0;
      f.value = (uint32_t) strtoul (eq + 1, NULL, 10);
    }
    f.tag = tag_of (item, strlen (item));
    out[n++] = f;
  }
  return n;
}

static int
parse_variations (char *s, hb_variation_t *out, int max)
{
  int n = 0;
  char *save = NULL;
  for (char *item = strtok_r (s, ",", &save); item && n < max; item = strtok_r (NULL, ",", &save))
  {
    char *eq = strchr (item, '=');
    if (!eq)
      return -1;
    *eq = 0;
    out[n].tag = tag_of (item, strlen (item));
    out[n].value = strtof (eq + 1, NULL);
    n++;
  }
  return n;
}

static hb_buffer_flags_t
parse_flags (char *s)
{
  unsigned f = HB_BUFFER_FLAG_DEFAULT;
  char *save = NULL;
  for (char *item = strtok_r (s, ",", &save); item; item = strtok_r (NULL, ",", &save))
  {
    if (!strcmp (item, "bot"))
      f |= HB_BUFFER_FLAG_BOT;
    else if (!strcmp (item, "eot"))
      f |= HB_BUFFER_FLAG_EOT;
    else if (!strcmp (item, "pdi"))
      f |= HB_BUFFER_FLAG_PRESERVE_DEFAULT_IGNORABLES;
    else if (!strcmp (item, "rdi"))
      f |= HB_BUFFER_FLAG_REMOVE_DEFAULT_IGNORABLES;
    else if (!strcmp (item, "nodc"))
      f |= HB_BUFFER_FLAG_DO_NOT_INSERT_DOTTED_CIRCLE;
    else if (!strcmp (item, "utc"))
      f |= HB_BUFFER_FLAG_PRODUCE_UNSAFE_TO_CONCAT;
    else if (!strcmp (item, "tatweel"))
      f |= HB_BUFFER_FLAG_PRODUCE_SAFE_TO_INSERT_TATWEEL;
  }
  return (hb_buffer_flags_t) f;
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
      printf ("%s\t!bad line\n", fields[0]);
    return;
  }
  const char *id = fields[0];
  hb_face_t *face = get_face (fields[1], (unsigned) strtoul (fields[2], NULL, 10));
  if (!face)
  {
    printf ("%s\t!no font\n", id);
    return;
  }

  static hb_codepoint_t text[MAX_CPS], pre[MAX_CPS], post[MAX_CPS], all[3 * MAX_CPS];
  int n_text = parse_cps (fields[4], text, MAX_CPS), n_pre = 0, n_post = 0;
  hb_feature_t feats[MAX_FEATS];
  hb_variation_t vars[MAX_VARS];
  int n_feats = 0, n_vars = 0, show_flags = 0, names = 0, scale = 0, scale_y = 0, ppem = 0, have_nf = 0;
  int have_slant = 0, have_bold = 0;
  float slant = 0, bold_x = 0, bold_y = 0;
  hb_codepoint_t not_found = 0;
  hb_buffer_t *buf = hb_buffer_create ();

  char *osave = NULL;
  for (char *kv = strtok_r (fields[3], ";", &osave); kv; kv = strtok_r (NULL, ";", &osave))
  {
    char *eq = strchr (kv, '=');
    if (!eq)
      continue;
    *eq = 0;
    char *v = eq + 1;
    if (!strcmp (kv, "dir"))
      hb_buffer_set_direction (buf, hb_direction_from_string (v, -1));
    else if (!strcmp (kv, "script"))
      hb_buffer_set_script (buf, hb_script_from_iso15924_tag (tag_of (v, strlen (v))));
    else if (!strcmp (kv, "lang"))
      hb_buffer_set_language (buf, hb_language_from_string (v, -1));
    else if (!strcmp (kv, "cl"))
      hb_buffer_set_cluster_level (buf, (hb_buffer_cluster_level_t) atoi (v));
    else if (!strcmp (kv, "feat"))
      n_feats = parse_features (v, feats, MAX_FEATS);
    else if (!strcmp (kv, "var"))
      n_vars = parse_variations (v, vars, MAX_VARS);
    else if (!strcmp (kv, "nf"))
      have_nf = 1, not_found = (hb_codepoint_t) strtoul (v, NULL, 10);
    else if (!strcmp (kv, "flags"))
      hb_buffer_set_flags (buf, parse_flags (v));
    else if (!strcmp (kv, "pre"))
      n_pre = parse_cps (v, pre, MAX_CPS);
    else if (!strcmp (kv, "post"))
      n_post = parse_cps (v, post, MAX_CPS);
    else if (!strcmp (kv, "scale"))
      scale = (int) strtol (v, &v, 10), scale_y = (*v == ',') ? atoi (v + 1) : scale;
    else if (!strcmp (kv, "ppem"))
      ppem = atoi (v);
    else if (!strcmp (kv, "slant"))
      have_slant = 1, slant = strtof (v, NULL);
    else if (!strcmp (kv, "bold"))
      have_bold = 1, bold_x = strtof (v, &v), bold_y = (*v == ',') ? strtof (v + 1, NULL) : bold_x;
    else if (!strcmp (kv, "gf"))
      show_flags = atoi (v);
    else if (!strcmp (kv, "names"))
      names = atoi (v);
  }
  if (n_text < 0 || n_pre < 0 || n_post < 0 || n_feats < 0 || n_vars < 0)
  {
    printf ("%s\t!bad options\n", id);
    hb_buffer_destroy (buf);
    return;
  }

  memcpy (all, pre, n_pre * sizeof (all[0]));
  memcpy (all + n_pre, text, n_text * sizeof (all[0]));
  memcpy (all + n_pre + n_text, post, n_post * sizeof (all[0]));
  hb_buffer_add_codepoints (buf, all, n_pre + n_text + n_post, (unsigned) n_pre, n_text);
  if (have_nf)
    hb_buffer_set_not_found_glyph (buf, not_found);
  hb_buffer_guess_segment_properties (buf);

  hb_font_t *font = hb_font_create (face);
  if (scale)
    hb_font_set_scale (font, scale, scale_y);
  if (ppem)
    hb_font_set_ppem (font, (unsigned) ppem, (unsigned) ppem);
  if (n_vars)
    hb_font_set_variations (font, vars, (unsigned) n_vars);
  if (have_slant)
    hb_font_set_synthetic_slant (font, slant);
  if (have_bold)
    hb_font_set_synthetic_bold (font, bold_x, bold_y, 0);

  if (!hb_shape_full (font, buf, feats, (unsigned) n_feats, NULL))
  {
    printf ("%s\t!shape failed\n", id);
    hb_font_destroy (font);
    hb_buffer_destroy (buf);
    return;
  }

  unsigned len = 0;
  hb_glyph_info_t *info = hb_buffer_get_glyph_infos (buf, &len);
  hb_glyph_position_t *pos = hb_buffer_get_glyph_positions (buf, NULL);
  printf ("%s\t", id);
  for (unsigned i = 0; i < len; i++)
  {
    if (i)
      putchar ('|');
    if (names)
    {
      char name[128];
      hb_font_get_glyph_name (font, info[i].codepoint, name, sizeof (name));
      fputs (name[0] ? name : "?", stdout);
    }
    else
      printf ("%u", info[i].codepoint);
    printf ("=%u@%d,%d+%d,%d", info[i].cluster, pos[i].x_offset, pos[i].y_offset, pos[i].x_advance, pos[i].y_advance);
    if (show_flags)
      printf ("#%u", (unsigned) hb_glyph_info_get_glyph_flags (&info[i]));
  }
  putchar ('\n');
  hb_font_destroy (font);
  hb_buffer_destroy (buf);
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
