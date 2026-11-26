#!/bin/bash
# Reference solution: OpenFOAM v2606 itself. Its source (tag OpenFOAM-v2606, commit 481094fdf34f,
# without tutorials and doc, with the installed build's hardening) goes into the submission with the
# installed OpenFOAM's build script; compile.sh builds it the same way and makes bin/<program>
# run each program with OpenFOAM's environment set up from that build.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /app/rebuild/reference
tar -xJf "$here/openfoam-v2606-src.tar.xz" -C /app/rebuild
cp "$here/reference/build.sh" /app/rebuild/reference/

cat > /app/rebuild/compile.sh <<'EOF'
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
rm -rf install
bash reference/build.sh "$PWD/openfoam" "$PWD/install" "$(nproc)"
cp -a openfoam/META-INFO install/META-INFO
ln -s "$(cat install/WM_OPTIONS)" install/platforms/current
mkdir -p bin
for p in install/platforms/current/bin/*; do
  n=$(basename "$p")
  printf '#!/bin/bash\n_args=("$@"); set --; source %q/install/etc/bashrc; set -- "${_args[@]}"\nexec -a %s %q/%s "$@"\n' \
    "$PWD" "$n" "$PWD" "$p" > "bin/$n"
  chmod 755 "bin/$n"
done
EOF
chmod 755 /app/rebuild/compile.sh

cat > /app/rebuild/PROGRESS.md <<'EOF'
# Progress

The reference solution: OpenFOAM v2606's own source, built by compile.sh. Every program works.
EOF
