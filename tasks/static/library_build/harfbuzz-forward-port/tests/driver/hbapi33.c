/*
 * hbapi33: compile the three script values that the Unicode 18.0 note adds (HB_SCRIPT_JURCHEN,
 * HB_SCRIPT_PROTO_CUNEIFORM and HB_SCRIPT_SEAL) and print them against the library's own reading of script names. It
 * does not compile against headers that lack any of the three.
 *
 * Input (stdin), one case per line, tab-separated, as for hbdrv:
 *   id <TAB> font file <TAB> face index <TAB> options <TAB> arguments
 * options: cmd=scripts. arguments: 32-bit values (hexadecimal, comma-separated), each holding the four characters of a
 * script name, first character in the high byte (as HB_TAG builds a tag). The font is not used.
 * Output, one line per case: id <TAB> v:<the three values, as integers, in the order above>|m:<for each name, which
 * of the three hb_script_from_string() returns for it: 1, 2 or 3, or 0 for none of them>. A setup failure prints
 * !err:<word>.
 */
#include <hb.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINE (1 << 20)
#define MAX_ARGS 4096
#define MAX_OPTS 32

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
run (const uint32_t *args, int n_args)
{
  static const hb_script_t added[3] = {HB_SCRIPT_JURCHEN, HB_SCRIPT_PROTO_CUNEIFORM, HB_SCRIPT_SEAL};
  printf ("v:%u,%u,%u|m:", (unsigned) added[0], (unsigned) added[1], (unsigned) added[2]);
  for (int i = 0; i < n_args; i++)
  {
    char name[4] = {(char) (args[i] >> 24), (char) (args[i] >> 16), (char) (args[i] >> 8), (char) args[i]};
    hb_script_t script = hb_script_from_string (name, 4);
    int which = 0;
    for (int k = 0; k < 3; k++)
      if (script == added[k])
	which = k + 1;
    printf ("%s%d", i ? "," : "", which);
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
  if (n_args < 0)
    printf ("!err:args");
  else if (!cmd || strcmp (cmd, "scripts"))
    printf ("!err:cmd");
  else
    run (args, n_args);
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
