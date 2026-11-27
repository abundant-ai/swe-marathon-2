/*
 * hbapi: query glyph extents, outlines, font extents, buffer positions, Unicode properties and OpenType language
 * tags through the public API of the HarfBuzz library it is linked against, and print integer results.
 *
 * Input (stdin), one case per line, tab-separated, as for hbdrv:
 *   id <TAB> font file <TAB> face index <TAB> options <TAB> arguments
 * arguments: hexadecimal integers separated by commas (glyph ids, code points, bytes, tags, or 32-bit values).
 * options: semicolon-separated key=value pairs. cmd=<name> selects the command. Font settings every command
 * honours: scale=<int> or scale=<x>,<y>; ppem=<x>,<y>; ptem=<decimal>; slant=<decimal>; bold=<x>,<y>; boldin=1;
 * var=<tag>=<value>,...; inst=<n>. Shaping commands also take dir, script, lang, cl and feat as hbdrv does.
 *
 * Commands (output after the id and a tab; groups separated by '|'):
 *   ext     per glyph: 1:x_bearing,y_bearing,width,height, or 0 when the font has no extents for it.
 *   fext    1:ascender,descender,line_gap of the horizontal font extents (0: on failure); with v=1 also the
 *           vertical ones after a '|'.
 *   adv     per glyph: h_advance,v_advance.
 *   draw    the outline of one glyph, one group per operation: 1,x,y (move), 2,x,y (line), 3,cx,cy,x,y
 *           (quadratic), 4,c1x,c1y,c2x,c2y,x,y (cubic), 5 (close). Whole coordinates print as integers, others as
 *           f:<IEEE-754 bits in hex>. 0 when there is no outline call at all.
 *   syn     extents of glyph 0 from font functions that report the four given extents (32-bit values) under the
 *           font's synthetic slant and emboldening: 1:x_bearing,y_bearing,width,height or 0.
 *   norm    shape the code points, normalize the glyphs, print gid=cluster@x_offset,y_offset+x_advance,y_advance.
 *   pos     buffer positions of items added after the first hb_buffer_get_glyph_positions() call. Keys: pre=<k>
 *           (the first k code points are an earlier content, shaped and then removed with clr=clear or clr=reset),
 *           a=<m> (the next m code points are added before the first call, shaped first when shp=1), how=add|cps|
 *           utf8|utf16|utf32|latin1 (how the remaining code points are added after it), show=new|old|all (which
 *           items to print: x_advance,y_advance,x_offset,y_offset each).
 *   ucd     per code point: general_category,combining_class,script_tag,mirroring,decomposes,a,b,recomposes.
 *   tags    the arguments are the bytes of a BCP 47 tag (script=<ISO 15924> optional): script tags, then language
 *           tags, each group count:tag,tag...
 *   t2l     per OpenType language tag: the bytes of the BCP 47 tag it converts to, or 0 for none.
 *   t2sl    arguments script tag, language tag: script value | bytes of the language (0 for none).
 *   png     per glyph: length,FNV-1a hash of hb_ot_color_glyph_reference_png().
 * A setup failure prints !err:<word>. Only public API present in 14.3.0 is used.
 */
#include <hb.h>
#include <hb-ot.h>

#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINE (1 << 20)
#define MAX_ARGS 4096
#define MAX_FEATS 64
#define MAX_VARS 16
#define MAX_FACES 512
#define MAX_KV 64
#define OUT_CAP (1 << 20)

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

/* Output accumulates in one buffer per case, so a case prints one line or one error. */
static char out[OUT_CAP];
static size_t out_len;
static int out_overflow;

static void
emit (const char *fmt, ...) __attribute__ ((format (printf, 1, 2)));

static void
emit (const char *fmt, ...)
{
  if (out_overflow)
    return;
  va_list ap;
  va_start (ap, fmt);
  int n = vsnprintf (out + out_len, OUT_CAP - out_len, fmt, ap);
  va_end (ap);
  if (n < 0 || (size_t) n >= OUT_CAP - out_len)
    out_overflow = 1;
  else
    out_len += (size_t) n;
}

static void
emit_float (float v)
{
  if (v == v && v >= -16777216.f && v <= 16777216.f && v == (float) (int32_t) v)
    emit ("%d", (int) (int32_t) v);
  else
  {
    uint32_t bits;
    memcpy (&bits, &v, sizeof (bits));
    emit ("f:%08x", (unsigned) bits);
  }
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
parse_args (const char *s, uint32_t *dst, int max)
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
    dst[n++] = (uint32_t) v;
    s = end;
  }
  return n;
}

static int
parse_features (char *s, hb_feature_t *dst, int max)
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
    dst[n++] = f;
  }
  return n;
}

static int
parse_variations (char *s, hb_variation_t *dst, int max)
{
  int n = 0;
  char *save = NULL;
  for (char *item = strtok_r (s, ",", &save); item && n < max; item = strtok_r (NULL, ",", &save))
  {
    char *eq = strchr (item, '=');
    if (!eq)
      return -1;
    *eq = 0;
    dst[n].tag = tag_of (item, strlen (item));
    dst[n].value = strtof (eq + 1, NULL);
    n++;
  }
  return n;
}

typedef struct
{
  char *key[MAX_KV];
  char *val[MAX_KV];
  int n;
} opts_t;

static const char *
opt (const opts_t *o, const char *key)
{
  for (int i = 0; i < o->n; i++)
    if (!strcmp (o->key[i], key))
      return o->val[i];
  return NULL;
}

static int
opt_int (const opts_t *o, const char *key, int dflt)
{
  const char *v = opt (o, key);
  return v ? atoi (v) : dflt;
}

/* Apply the common font settings; returns 0 on a malformed setting. */
static int
setup_font (hb_font_t *font, const opts_t *o)
{
  const char *v;
  if ((v = opt (o, "scale")))
  {
    char *end;
    long x = strtol (v, &end, 10);
    long y = (*end == ',') ? strtol (end + 1, NULL, 10) : x;
    hb_font_set_scale (font, (int) x, (int) y);
  }
  if ((v = opt (o, "ppem")))
  {
    char *end;
    unsigned long x = strtoul (v, &end, 10);
    unsigned long y = (*end == ',') ? strtoul (end + 1, NULL, 10) : x;
    hb_font_set_ppem (font, (unsigned) x, (unsigned) y);
  }
  if ((v = opt (o, "ptem")))
    hb_font_set_ptem (font, strtof (v, NULL));
  if ((v = opt (o, "inst")))
    hb_font_set_var_named_instance (font, (unsigned) strtoul (v, NULL, 10));
  if ((v = opt (o, "var")))
  {
    hb_variation_t vars[MAX_VARS];
    char tmp[1024];
    snprintf (tmp, sizeof (tmp), "%s", v);
    int n = parse_variations (tmp, vars, MAX_VARS);
    if (n < 0)
      return 0;
    hb_font_set_variations (font, vars, (unsigned) n);
  }
  if ((v = opt (o, "slant")))
    hb_font_set_synthetic_slant (font, strtof (v, NULL));
  if ((v = opt (o, "bold")))
  {
    char *end;
    float x = strtof (v, &end);
    float y = (*end == ',') ? strtof (end + 1, NULL) : x;
    hb_font_set_synthetic_bold (font, x, y, opt_int (o, "boldin", 0) ? 1 : 0);
  }
  return 1;
}

/* Shaping options shared with hbdrv: dir, script, lang, cl, feat. Returns the feature count, or -1. */
static int
setup_buffer (hb_buffer_t *buf, const opts_t *o, hb_feature_t *feats)
{
  const char *v;
  int n_feats = 0;
  if ((v = opt (o, "dir")))
    hb_buffer_set_direction (buf, hb_direction_from_string (v, -1));
  if ((v = opt (o, "script")))
    hb_buffer_set_script (buf, hb_script_from_iso15924_tag (tag_of (v, strlen (v))));
  if ((v = opt (o, "lang")))
    hb_buffer_set_language (buf, hb_language_from_string (v, -1));
  if ((v = opt (o, "cl")))
    hb_buffer_set_cluster_level (buf, (hb_buffer_cluster_level_t) atoi (v));
  if ((v = opt (o, "feat")))
  {
    static char tmp[MAX_LINE];
    snprintf (tmp, sizeof (tmp), "%s", v);
    n_feats = parse_features (tmp, feats, MAX_FEATS);
  }
  return n_feats;
}

/* ext */
static void
cmd_ext (hb_font_t *font, const uint32_t *args, int n)
{
  for (int i = 0; i < n; i++)
  {
    hb_glyph_extents_t e;
    memset (&e, 0, sizeof (e));
    if (i)
      emit ("|");
    if (hb_font_get_glyph_extents (font, args[i], &e))
      emit ("1:%d,%d,%d,%d", e.x_bearing, e.y_bearing, e.width, e.height);
    else
      emit ("0");
  }
}

/* fext */
static void
cmd_fext (hb_font_t *font, const opts_t *o)
{
  hb_font_extents_t h;
  memset (&h, 0, sizeof (h));
  hb_bool_t ok_h = hb_font_get_h_extents (font, &h);
  emit ("%d:%d,%d,%d", ok_h ? 1 : 0, h.ascender, h.descender, h.line_gap);
  if (opt_int (o, "v", 0))
  {
    hb_font_extents_t v;
    memset (&v, 0, sizeof (v));
    hb_bool_t ok_v = hb_font_get_v_extents (font, &v);
    emit ("|%d:%d,%d,%d", ok_v ? 1 : 0, v.ascender, v.descender, v.line_gap);
  }
}

/* adv */
static void
cmd_adv (hb_font_t *font, const uint32_t *args, int n)
{
  for (int i = 0; i < n; i++)
    emit ("%s%d,%d", i ? "|" : "", hb_font_get_glyph_h_advance (font, args[i]),
	  hb_font_get_glyph_v_advance (font, args[i]));
}

/* draw */
static int draw_ops;

static void
draw_sep (void)
{
  if (draw_ops++)
    emit ("|");
}

static void
draw_move_to (hb_draw_funcs_t *f, void *d, hb_draw_state_t *st, float x, float y, void *u)
{
  (void) f, (void) d, (void) st, (void) u;
  draw_sep ();
  emit ("1,");
  emit_float (x);
  emit (",");
  emit_float (y);
}

static void
draw_line_to (hb_draw_funcs_t *f, void *d, hb_draw_state_t *st, float x, float y, void *u)
{
  (void) f, (void) d, (void) st, (void) u;
  draw_sep ();
  emit ("2,");
  emit_float (x);
  emit (",");
  emit_float (y);
}

static void
draw_quadratic_to (hb_draw_funcs_t *f, void *d, hb_draw_state_t *st, float cx, float cy, float x, float y, void *u)
{
  (void) f, (void) d, (void) st, (void) u;
  draw_sep ();
  emit ("3,");
  emit_float (cx);
  emit (",");
  emit_float (cy);
  emit (",");
  emit_float (x);
  emit (",");
  emit_float (y);
}

static void
draw_cubic_to (hb_draw_funcs_t *f, void *d, hb_draw_state_t *st, float c1x, float c1y, float c2x, float c2y,
	       float x, float y, void *u)
{
  (void) f, (void) d, (void) st, (void) u;
  draw_sep ();
  emit ("4,");
  emit_float (c1x);
  emit (",");
  emit_float (c1y);
  emit (",");
  emit_float (c2x);
  emit (",");
  emit_float (c2y);
  emit (",");
  emit_float (x);
  emit (",");
  emit_float (y);
}

static void
draw_close_path (hb_draw_funcs_t *f, void *d, hb_draw_state_t *st, void *u)
{
  (void) f, (void) d, (void) st, (void) u;
  draw_sep ();
  emit ("5");
}

static hb_draw_funcs_t *
get_draw_funcs (void)
{
  static hb_draw_funcs_t *funcs;
  if (!funcs)
  {
    funcs = hb_draw_funcs_create ();
    hb_draw_funcs_set_move_to_func (funcs, draw_move_to, NULL, NULL);
    hb_draw_funcs_set_line_to_func (funcs, draw_line_to, NULL, NULL);
    hb_draw_funcs_set_quadratic_to_func (funcs, draw_quadratic_to, NULL, NULL);
    hb_draw_funcs_set_cubic_to_func (funcs, draw_cubic_to, NULL, NULL);
    hb_draw_funcs_set_close_path_func (funcs, draw_close_path, NULL, NULL);
    hb_draw_funcs_make_immutable (funcs);
  }
  return funcs;
}

static void
cmd_draw (hb_font_t *font, const uint32_t *args, int n)
{
  if (n < 1)
    return;
  draw_ops = 0;
  hb_font_draw_glyph (font, args[0], get_draw_funcs (), NULL);
  if (!draw_ops)
    emit ("0");
}

/* syn */
static hb_bool_t
syn_extents (hb_font_t *font, void *font_data, hb_codepoint_t glyph, hb_glyph_extents_t *extents, void *user_data)
{
  (void) font, (void) glyph, (void) user_data;
  *extents = *(const hb_glyph_extents_t *) font_data;
  return 1;
}

static void
cmd_syn (hb_face_t *face, const opts_t *o, const uint32_t *args, int n)
{
  static hb_font_funcs_t *funcs;
  if (!funcs)
  {
    funcs = hb_font_funcs_create ();
    hb_font_funcs_set_glyph_extents_func (funcs, syn_extents, NULL, NULL);
    hb_font_funcs_make_immutable (funcs);
  }
  if (n < 4)
  {
    emit ("!err:args");
    return;
  }
  hb_glyph_extents_t given;
  given.x_bearing = (int32_t) args[0];
  given.y_bearing = (int32_t) args[1];
  given.width = (int32_t) args[2];
  given.height = (int32_t) args[3];
  hb_font_t *font = hb_font_create (face);
  hb_font_set_funcs (font, funcs, &given, NULL);
  if (!setup_font (font, o))
  {
    hb_font_destroy (font);
    emit ("!err:opts");
    return;
  }
  hb_glyph_extents_t e;
  memset (&e, 0, sizeof (e));
  if (hb_font_get_glyph_extents (font, 0, &e))
    emit ("1:%d,%d,%d,%d", e.x_bearing, e.y_bearing, e.width, e.height);
  else
    emit ("0");
  hb_font_destroy (font);
}

/* norm */
static void
cmd_norm (hb_font_t *font, const opts_t *o, const uint32_t *args, int n)
{
  hb_feature_t feats[MAX_FEATS];
  hb_buffer_t *buf = hb_buffer_create ();
  int n_feats = setup_buffer (buf, o, feats);
  if (n_feats < 0)
  {
    hb_buffer_destroy (buf);
    emit ("!err:opts");
    return;
  }
  hb_buffer_add_codepoints (buf, args, n, 0, n);
  hb_buffer_guess_segment_properties (buf);
  hb_shape (font, buf, feats, (unsigned) n_feats);
  hb_buffer_normalize_glyphs (buf);
  unsigned len = 0;
  hb_glyph_info_t *info = hb_buffer_get_glyph_infos (buf, &len);
  hb_glyph_position_t *pos = hb_buffer_get_glyph_positions (buf, NULL);
  for (unsigned i = 0; i < len; i++)
    emit ("%s%u=%u@%d,%d+%d,%d", i ? "|" : "", info[i].codepoint, info[i].cluster, pos[i].x_offset,
	  pos[i].y_offset, pos[i].x_advance, pos[i].y_advance);
  hb_buffer_destroy (buf);
}

/* pos */
static int
utf8_encode (uint32_t cp, uint8_t *p)
{
  if (cp < 0x80)
    return p[0] = (uint8_t) cp, 1;
  if (cp < 0x800)
    return p[0] = (uint8_t) (0xC0 | (cp >> 6)), p[1] = (uint8_t) (0x80 | (cp & 0x3F)), 2;
  if (cp < 0x10000)
    return p[0] = (uint8_t) (0xE0 | (cp >> 12)), p[1] = (uint8_t) (0x80 | ((cp >> 6) & 0x3F)),
	   p[2] = (uint8_t) (0x80 | (cp & 0x3F)), 3;
  return p[0] = (uint8_t) (0xF0 | (cp >> 18)), p[1] = (uint8_t) (0x80 | ((cp >> 12) & 0x3F)),
	 p[2] = (uint8_t) (0x80 | ((cp >> 6) & 0x3F)), p[3] = (uint8_t) (0x80 | (cp & 0x3F)), 4;
}

/* The case only says something when shaping really ran: the shaped text has glyphs, and some glyph moves the pen.
 * Otherwise the positions left in the buffer's memory would be zero for want of shaping, not because of the fix. */
static int
shaped (hb_buffer_t *buf)
{
  unsigned len = 0;
  hb_glyph_position_t *pos = hb_buffer_get_glyph_positions (buf, &len);
  for (unsigned i = 0; i < len; i++)
    if (pos[i].x_advance || pos[i].y_advance)
      return 1;
  return 0;
}

static void
cmd_pos (hb_font_t *font, const opts_t *o, const uint32_t *args, int n)
{
  int pre = opt_int (o, "pre", 0), a = opt_int (o, "a", 0);
  const char *how = opt (o, "how"), *show = opt (o, "show"), *clr = opt (o, "clr");
  if (!how)
    how = "cps";
  if (!show)
    show = "new";
  if (pre < 0 || a < 0 || pre + a > n)
  {
    emit ("!err:args");
    return;
  }
  hb_feature_t feats[MAX_FEATS];
  hb_buffer_t *buf = hb_buffer_create ();
  int n_feats = setup_buffer (buf, o, feats);
  if (n_feats < 0)
  {
    hb_buffer_destroy (buf);
    emit ("!err:opts");
    return;
  }
  hb_segment_properties_t props;
  hb_buffer_get_segment_properties (buf, &props);
  hb_buffer_cluster_level_t level = hb_buffer_get_cluster_level (buf);

  /* An earlier content, shaped and removed: its positions stay in the buffer's memory. */
  if (pre)
  {
    hb_buffer_add_codepoints (buf, args, pre, 0, pre);
    hb_buffer_guess_segment_properties (buf);
    hb_shape (font, buf, feats, (unsigned) n_feats);
    if (!shaped (buf))
    {
      hb_buffer_destroy (buf);
      emit ("!err:noshape");
      return;
    }
    hb_buffer_get_glyph_positions (buf, NULL);
    if (clr && !strcmp (clr, "reset"))
      hb_buffer_reset (buf);
    else
      hb_buffer_clear_contents (buf);
    hb_buffer_set_segment_properties (buf, &props);
    hb_buffer_set_cluster_level (buf, level);
  }

  /* The current content and the first call. */
  hb_buffer_add_codepoints (buf, args + pre, a, 0, a);
  if (opt_int (o, "shp", 0))
  {
    hb_buffer_guess_segment_properties (buf);
    hb_shape (font, buf, feats, (unsigned) n_feats);
    if (a > 0 && !shaped (buf))
    {
      hb_buffer_destroy (buf);
      emit ("!err:noshape");
      return;
    }
  }
  unsigned len1 = 0, len2 = 0;
  hb_buffer_get_glyph_positions (buf, &len1);

  /* Items added after the first call. */
  const uint32_t *rest = args + pre + a;
  int nr = n - pre - a;
  if (!strcmp (how, "add"))
    for (int i = 0; i < nr; i++)
      hb_buffer_add (buf, rest[i], (unsigned) (pre + a + i));
  else if (!strcmp (how, "utf32"))
    hb_buffer_add_utf32 (buf, rest, nr, 0, nr);
  else if (!strcmp (how, "utf16"))
  {
    static uint16_t u16[2 * MAX_ARGS];
    int k = 0;
    for (int i = 0; i < nr; i++)
      if (rest[i] >= 0x10000 && rest[i] <= 0x10FFFF)
      {
	u16[k++] = (uint16_t) (0xD800 + ((rest[i] - 0x10000) >> 10));
	u16[k++] = (uint16_t) (0xDC00 + ((rest[i] - 0x10000) & 0x3FF));
      }
      else
	u16[k++] = (uint16_t) rest[i];
    hb_buffer_add_utf16 (buf, u16, k, 0, k);
  }
  else if (!strcmp (how, "utf8"))
  {
    static uint8_t u8[4 * MAX_ARGS];
    int k = 0;
    for (int i = 0; i < nr; i++)
      k += utf8_encode (rest[i] <= 0x10FFFF ? rest[i] : 0xFFFD, u8 + k);
    hb_buffer_add_utf8 (buf, (const char *) u8, k, 0, k);
  }
  else if (!strcmp (how, "latin1"))
  {
    static uint8_t l1[MAX_ARGS];
    for (int i = 0; i < nr; i++)
      l1[i] = (uint8_t) rest[i];
    hb_buffer_add_latin1 (buf, l1, nr, 0, nr);
  }
  else
    hb_buffer_add_codepoints (buf, rest, nr, 0, nr);

  hb_glyph_position_t *pos = hb_buffer_get_glyph_positions (buf, &len2);
  unsigned from = 0, to = len2;
  if (!strcmp (show, "new"))
    from = len1;
  else if (!strcmp (show, "old"))
    to = len1 < len2 ? len1 : len2;
  emit ("%u", to - from);
  for (unsigned i = from; i < to; i++)
    emit ("|%d,%d,%d,%d", pos[i].x_advance, pos[i].y_advance, pos[i].x_offset, pos[i].y_offset);
  hb_buffer_destroy (buf);
}

/* ucd */
static void
cmd_ucd (const uint32_t *args, int n)
{
  hb_unicode_funcs_t *uf = hb_unicode_funcs_get_default ();
  for (int i = 0; i < n; i++)
  {
    hb_codepoint_t cp = args[i], a = 0, b = 0, ab = 0;
    hb_bool_t dec = hb_unicode_decompose (uf, cp, &a, &b);
    int rec = dec ? (hb_unicode_compose (uf, a, b, &ab) && ab == cp) : 0;
    emit ("%s%d,%u,%u,%u,%d,%u,%u,%d", i ? "|" : "", (int) hb_unicode_general_category (uf, cp),
	  (unsigned) hb_unicode_combining_class (uf, cp), (unsigned) hb_unicode_script (uf, cp),
	  (unsigned) hb_unicode_mirroring (uf, cp), dec ? 1 : 0, dec ? a : 0, dec ? b : 0, rec);
  }
}

/* tags, t2l, t2sl */
static void
emit_language (hb_language_t lang)
{
  const char *s = lang ? hb_language_to_string (lang) : NULL;
  if (!s || !*s)
  {
    emit ("0");
    return;
  }
  for (int i = 0; s[i]; i++)
    emit ("%s%u", i ? "," : "", (unsigned) (unsigned char) s[i]);
}

static void
cmd_tags (const opts_t *o, const uint32_t *args, int n)
{
  char str[256];
  int k = 0;
  for (int i = 0; i < n && k < (int) sizeof (str) - 1; i++)
    str[k++] = (char) args[i];
  str[k] = 0;
  const char *sv = opt (o, "script");
  hb_script_t script = sv ? hb_script_from_iso15924_tag (tag_of (sv, strlen (sv))) : HB_SCRIPT_INVALID;
  hb_language_t lang = k ? hb_language_from_string (str, k) : HB_LANGUAGE_INVALID;
  hb_tag_t st[8], lt[8];
  unsigned sc = 8, lc = 8;
  hb_ot_tags_from_script_and_language (script, lang, &sc, st, &lc, lt);
  emit ("%u:", sc);
  for (unsigned i = 0; i < sc; i++)
    emit ("%s%u", i ? "," : "", (unsigned) st[i]);
  emit ("|%u:", lc);
  for (unsigned i = 0; i < lc; i++)
    emit ("%s%u", i ? "," : "", (unsigned) lt[i]);
}

static void
cmd_t2l (const uint32_t *args, int n)
{
  for (int i = 0; i < n; i++)
  {
    if (i)
      emit ("|");
    emit_language (hb_ot_tag_to_language (args[i]));
  }
}

static void
cmd_t2sl (const uint32_t *args, int n)
{
  if (n < 2)
  {
    emit ("!err:args");
    return;
  }
  hb_script_t script = HB_SCRIPT_INVALID;
  hb_language_t lang = HB_LANGUAGE_INVALID;
  hb_ot_tags_to_script_and_language (args[0], args[1], &script, &lang);
  emit ("%u|", (unsigned) script);
  emit_language (lang);
}

/* png */
static void
cmd_png (hb_font_t *font, const uint32_t *args, int n)
{
  for (int i = 0; i < n; i++)
  {
    hb_blob_t *blob = hb_ot_color_glyph_reference_png (font, args[i]);
    unsigned len = 0;
    const char *data = hb_blob_get_data (blob, &len);
    uint32_t h = 2166136261u;
    for (unsigned j = 0; j < len; j++)
      h = (h ^ (uint8_t) data[j]) * 16777619u;
    emit ("%s%u,%u", i ? "|" : "", len, (unsigned) h);
    hb_blob_destroy (blob);
  }
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
  const char *id = fields[0];
  out_len = 0;
  out_overflow = 0;
  out[0] = 0;

  opts_t o;
  o.n = 0;
  char *osave = NULL;
  for (char *kv = strtok_r (fields[3], ";", &osave); kv && o.n < MAX_KV; kv = strtok_r (NULL, ";", &osave))
  {
    char *eq = strchr (kv, '=');
    if (!eq)
      continue;
    *eq = 0;
    o.key[o.n] = kv;
    o.val[o.n] = eq + 1;
    o.n++;
  }
  const char *cmd = opt (&o, "cmd");
  static uint32_t args[MAX_ARGS];
  int n = parse_args (fields[4], args, MAX_ARGS);
  if (!cmd)
  {
    printf ("%s\t!err:cmd\n", id);
    return;
  }
  if (n < 0)
  {
    printf ("%s\t!err:args\n", id);
    return;
  }
  hb_face_t *face = get_face (fields[1], (unsigned) strtoul (fields[2], NULL, 10));
  if (!face)
  {
    printf ("%s\t!err:font\n", id);
    return;
  }

  if (!strcmp (cmd, "ucd"))
    cmd_ucd (args, n);
  else if (!strcmp (cmd, "tags"))
    cmd_tags (&o, args, n);
  else if (!strcmp (cmd, "t2l"))
    cmd_t2l (args, n);
  else if (!strcmp (cmd, "t2sl"))
    cmd_t2sl (args, n);
  else if (!strcmp (cmd, "syn"))
    cmd_syn (face, &o, args, n);
  else
  {
    hb_font_t *font = hb_font_create (face);
    if (!setup_font (font, &o))
    {
      hb_font_destroy (font);
      printf ("%s\t!err:opts\n", id);
      return;
    }
    if (!strcmp (cmd, "ext"))
      cmd_ext (font, args, n);
    else if (!strcmp (cmd, "fext"))
      cmd_fext (font, &o);
    else if (!strcmp (cmd, "adv"))
      cmd_adv (font, args, n);
    else if (!strcmp (cmd, "draw"))
      cmd_draw (font, args, n);
    else if (!strcmp (cmd, "norm"))
      cmd_norm (font, &o, args, n);
    else if (!strcmp (cmd, "pos"))
      cmd_pos (font, &o, args, n);
    else if (!strcmp (cmd, "png"))
      cmd_png (font, args, n);
    else
    {
      hb_font_destroy (font);
      printf ("%s\t!err:cmd\n", id);
      return;
    }
    hb_font_destroy (font);
  }
  if (out_overflow)
    printf ("%s\t!err:size\n", id);
  else
    printf ("%s\t%s\n", id, out);
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
