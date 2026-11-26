/*
 * hbapi49: probe hb_ot_layout_get_extender_glyphs() of the HarfBuzz library it is linked against and print
 * integer results. It does not compile against a library that lacks the function.
 *
 * Input (stdin), one case per line, tab-separated, as for hbdrv:
 *   id <TAB> font file <TAB> face index <TAB> options <TAB> arguments
 * options: cmd=ext; script=<ISO 15924 tag>; lang=<BCP 47 tag> (absent: HB_LANGUAGE_INVALID); glyphs=null to
 * pass a NULL glyph array.
 * arguments (hexadecimal, comma-separated): pairs of start offset and glyph count, one call each; a count of
 * FFFFFFFF passes a NULL count pointer.
 * Output, one line per case: id <TAB> one group per call, joined with '|':
 *   r:<return value>|n:<count on output, -1 for a NULL pointer>|g:<the glyphs returned>
 * A setup failure prints !err:<word>.
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
#define MAX_CACHE 1024
#define MAX_GLYPHS 4096

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
run (hb_face_t *face, const uint32_t *args, int n_args)
{
  const char *script = opt ("script"), *lang = opt ("lang"), *g = opt ("glyphs");
  hb_script_t sc = script ? hb_script_from_iso15924_tag (tag_of (script)) : HB_SCRIPT_INVALID;
  hb_language_t language = lang ? hb_language_from_string (lang, -1) : HB_LANGUAGE_INVALID;
  int null_glyphs = g && !strcmp (g, "null");
  static hb_codepoint_t glyphs[MAX_GLYPHS];
  for (int i = 0; i + 1 < n_args; i += 2)
  {
    unsigned start = args[i], count = args[i + 1];
    int null_count = count == 0xFFFFFFFFu;
    if (!null_count && count > MAX_GLYPHS)
      count = MAX_GLYPHS;
    for (unsigned j = 0; j < MAX_GLYPHS; j++)
      glyphs[j] = HB_CODEPOINT_INVALID;
    unsigned ret = hb_ot_layout_get_extender_glyphs (face, sc, language, start, null_count ? NULL : &count,
						     null_glyphs ? NULL : glyphs);
    printf ("%sr:%u|n:", i ? "|" : "", ret);
    if (null_count)
      printf ("-1|g:");
    else
    {
      printf ("%u|g:", count);
      for (unsigned j = 0; !null_glyphs && j < count && j < MAX_GLYPHS; j++)
	printf ("%s%u", j ? "," : "", glyphs[j]);
    }
  }
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
  hb_face_t *face;
  if (n_args < 0)
    printf ("!err:args");
  else if (!cmd || strcmp (cmd, "ext"))
    printf ("!err:cmd");
  else if (!(face = get_face (fields[1], (unsigned) strtoul (fields[2], NULL, 10))))
    printf ("!err:nofile");
  else
    run (face, args, n_args);
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
