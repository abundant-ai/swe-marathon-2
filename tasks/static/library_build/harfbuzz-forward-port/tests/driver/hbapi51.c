/*
 * hbapi51: probe hb_buffer_deserialize_glyphs2() and hb_buffer_deserialize_unicode2() of the HarfBuzz library it
 * is linked against and print integer results. It does not compile against a library that lacks them.
 *
 * Input (stdin), one case per line, tab-separated, as for hbdrv:
 *   id <TAB> font file <TAB> face index <TAB> options <TAB> arguments
 * arguments: the bytes of the text to deserialize (hexadecimal, comma-separated; 00 allowed). The probe keeps a
 * NUL byte after them.
 * options: cmd=glyphs2|unicode2; fmt=text|json|<integer> (the format value); len=<integer> (buf_len, -1 allowed;
 * absent: the number of bytes); cons=null (NULL buf_consumed); nofont=1 (NULL font; otherwise a font of the
 * case's face); pre=<hexadecimal bytes> (deserialized first, with the same format, by the 14.3.0 function, so the call
 * appends); empty=1 (the call gets the empty buffer).
 * Output, one line per case: id <TAB> r:<return value>|c:<buf_consumed, -1 for NULL>|t:<content type>|
 * n:<length>, then one group per item: glyph,cluster,mask,x_advance,y_advance,x_offset,y_offset for glyphs, or
 * codepoint,cluster,mask for Unicode. A setup failure prints !err:<word>.
 */
#include <hb.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINE (1 << 20)
#define MAX_ARGS 65536
#define MAX_OPTS 32
#define MAX_CACHE 1024

typedef struct
{
  char *path;
  unsigned index;
  hb_face_t *face;
} face_entry_t;

static face_entry_t faces[MAX_CACHE];
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
  if (n_faces < MAX_CACHE)
  {
    faces[n_faces].path = strdup (path);
    faces[n_faces].index = index;
    faces[n_faces].face = face;
    n_faces++;
  }
  return face;
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
parse_bytes (const char *s, char *out, int max)
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
    if (end == s || v > 0xFF)
      return -1;
    out[n++] = (char) v;
    s = end;
  }
  return n;
}

static void
put_buffer (hb_buffer_t *buf)
{
  unsigned len = 0;
  hb_buffer_content_type_t type = hb_buffer_get_content_type (buf);
  hb_glyph_info_t *info = hb_buffer_get_glyph_infos (buf, &len);
  printf ("|t:%d|n:%u", (int) type, len);
  if (type == HB_BUFFER_CONTENT_TYPE_GLYPHS)
  {
    hb_glyph_position_t *pos = hb_buffer_get_glyph_positions (buf, NULL);
    for (unsigned i = 0; i < len; i++)
      printf ("|%u,%u,%u,%d,%d,%d,%d", info[i].codepoint, info[i].cluster, info[i].mask, pos[i].x_advance,
	      pos[i].y_advance, pos[i].x_offset, pos[i].y_offset);
  }
  else
    for (unsigned i = 0; i < len; i++)
      printf ("|%u,%u,%u", info[i].codepoint, info[i].cluster, info[i].mask);
}

static void
run (const char *path, unsigned index, const char *bytes, int n_bytes)
{
  const char *cmd = opt ("cmd"), *f = opt ("fmt"), *l = opt ("len"), *c = opt ("cons");
  const char *fo = opt ("nofont"), *pre = opt ("pre"), *e = opt ("empty");
  int glyphs = !strcmp (cmd, "glyphs2");
  hb_buffer_serialize_format_t format = HB_BUFFER_SERIALIZE_FORMAT_TEXT;
  if (f && !strcmp (f, "json"))
    format = HB_BUFFER_SERIALIZE_FORMAT_JSON;
  else if (f && strcmp (f, "text"))
    format = (hb_buffer_serialize_format_t) strtoul (f, NULL, 10);
  int buf_len = l ? atoi (l) : n_bytes;

  hb_font_t *font = NULL;
  if (glyphs && !(fo && atoi (fo)))
  {
    hb_face_t *face = get_face (path, index);
    if (!face)
    {
      printf ("!err:nofile");
      return;
    }
    font = hb_font_create (face);
  }
  hb_buffer_t *buf = (e && atoi (e)) ? hb_buffer_get_empty () : hb_buffer_create ();
  if (pre)
  {
    static char pre_bytes[MAX_ARGS + 1];
    int n = parse_bytes (pre, pre_bytes, MAX_ARGS);
    if (n > 0)
    {
      pre_bytes[n] = 0;
      if (glyphs)
	hb_buffer_deserialize_glyphs (buf, pre_bytes, n, NULL, font, format);
      else
	hb_buffer_deserialize_unicode (buf, pre_bytes, n, NULL, format);
    }
  }
  unsigned consumed = 0xDEADu;
  hb_bool_t ret = glyphs
		? hb_buffer_deserialize_glyphs2 (buf, bytes, buf_len, (c && !strcmp (c, "null")) ? NULL : &consumed,
						 font, format)
		: hb_buffer_deserialize_unicode2 (buf, bytes, buf_len, (c && !strcmp (c, "null")) ? NULL : &consumed,
						  format);
  printf ("r:%d|c:", (int) ret);
  if (c && !strcmp (c, "null"))
    printf ("-1");
  else
    printf ("%u", consumed);
  put_buffer (buf);
  hb_buffer_destroy (buf);
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
  static char bytes[MAX_ARGS + 1];
  int n_bytes = parse_bytes (fields[4], bytes, MAX_ARGS);
  const char *cmd = opt ("cmd");
  printf ("%s\t", fields[0]);
  if (n_bytes < 0)
    printf ("!err:args");
  else if (!cmd || (strcmp (cmd, "glyphs2") && strcmp (cmd, "unicode2")))
    printf ("!err:cmd");
  else
  {
    /* Zero everything after the text, so that a buf_len past it reads the same bytes in every case. */
    memset (bytes + n_bytes, 0, sizeof (bytes) - (size_t) n_bytes);
    run (fields[1], (unsigned) strtoul (fields[2], NULL, 10), bytes, n_bytes);
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
