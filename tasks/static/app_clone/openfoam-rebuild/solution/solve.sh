#!/bin/bash
# Reference solution: the installed OpenFOAM itself. Its programs and libraries are copied into
# the submission, and compile.sh makes bin/<program> run each one with OpenFOAM's environment
# set up from that copy, so the submission works where OpenFOAM is not installed.
# Run as root (the installed files are not readable by the agent's user).
set -euo pipefail
mkdir -p /app/rebuild
cp -a /opt/openfoam /app/rebuild/openfoam
rm /app/rebuild/openfoam/tutorials               # a link to /app/tutorials, not part of the programs
chmod -R u+w,ug-s,a+rX /app/rebuild/openfoam     # setgid would make the loader ignore library paths

cat > /app/rebuild/compile.sh <<'EOF'
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p bin
for p in openfoam/platforms/current/bin/*; do
  n=$(basename "$p")
  printf '#!/bin/bash\n_args=("$@"); set --; source %q/openfoam/etc/bashrc; set -- "${_args[@]}"\nexec -a %s %q/%s "$@"\n' \
    "$PWD" "$n" "$PWD" "$p" > "bin/$n"
  chmod +x "bin/$n"
done
EOF
chmod +x /app/rebuild/compile.sh
chown -R dev:dev /app/rebuild
