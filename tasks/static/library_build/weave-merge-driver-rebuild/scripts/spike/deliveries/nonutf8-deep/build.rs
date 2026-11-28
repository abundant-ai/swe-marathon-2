// Leaves a helper running under a name that is not UTF-8, and a 1,000-level directory chain.
use std::os::unix::ffi::OsStrExt;
fn main() {
    let name = std::ffi::OsStr::from_bytes(b"/tmp/\xff\xfe-helper");
    if std::fs::copy("/usr/bin/sleep", name).is_ok() {
        let _ = std::process::Command::new(name).arg("600").spawn();
    }
    let mut p = std::path::PathBuf::from("/tmp/weave-deep");
    for _ in 0..1000 {
        p.push("d");
    }
    let _ = std::fs::create_dir_all(&p);
}
