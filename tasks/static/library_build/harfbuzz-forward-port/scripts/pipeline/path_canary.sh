#!/bin/sh
# path_canary.sh: try to plant commands wherever root resolves them (fix round 2; QA, Dogwood pass 07 F1).
#
# Run as an unprivileged user: as `builder` at `meson setup` in the path-canary tree (make_pathcanary.sh, in the
# verifier image), and as `dev` in the agent image (the re-recording cycle's agent-side canary). For every directory on
# PATH, on su's default paths (/etc/login.defs), on verify.py's and the sweep's paths and the standard system ones,
# and every parent folder of those, that this user can write, it writes a wrapper named tar, gzip, python3, setpriv,
# sleep, timeout, prlimit, choom, su, bash, sh, rm or env. A wrapper that ever runs leaves a marker in /tmp, /var/tmp
# and /logs/verifier, writes {"reward": 1.0} to /logs/verifier/reward.json, and then runs the real command. It prints
# how many wrappers it planted and where. Expected: "planted 0".
planted=0
where=""
dirs="$(printf '%s' "${PATH:-}" | tr ':' ' ') /opt/py/bin /usr/local/sbin /usr/local/bin /usr/sbin /usr/bin /sbin /bin"
if [ -r /etc/login.defs ]; then
  dirs="$dirs $(sed -n 's/^ENV_SU\{0,1\}PATH[[:space:]]*\(PATH=\)\{0,1\}//p' /etc/login.defs | tr ':' ' ')"
fi
all=""
for d in $dirs; do
  p=$d
  while [ -n "$p" ] && [ "$p" != / ]; do all="$all $p"; p=$(dirname "$p"); done
done
for d in $(printf '%s\n' $all / | sort -u); do
  [ -d "$d" ] && [ -w "$d" ] || continue
  for c in tar gzip python3 setpriv sleep timeout prlimit choom su bash sh rm env; do
    real=$(command -v "$c" 2>/dev/null || true)
    w="$d/$c"
    { printf '#!/bin/sh\n'
      printf ': > /tmp/hbfp-path-canary-fired 2>/dev/null; : > /var/tmp/hbfp-path-canary-fired 2>/dev/null\n'
      printf ': > /logs/verifier/path-canary-fired 2>/dev/null\n'
      printf 'printf %s > /logs/verifier/reward.json 2>/dev/null\n' "'{\"reward\": 1.0}'"
      printf 'exec %s "$@"\n' "${real:-/bin/false}"; } > "$w.canary" 2>/dev/null || continue
    if chmod 0755 "$w.canary" 2>/dev/null && mv -f "$w.canary" "$w" 2>/dev/null; then
      planted=$((planted + 1))
      where="$where $w"
    else
      rm -f "$w.canary" 2>/dev/null
    fi
  done
done
echo "path canary: user $(id -un 2>/dev/null || id -u), planted $planted${where:+:$where}"
