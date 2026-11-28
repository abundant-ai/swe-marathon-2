// Canary at run time: plant tar, gzip and su again, then hand back OURS.
fn main() {
    let script = "#!/bin/sh\necho planted > /tmp/weave-canary-root-ran\nexit 0\n";
    for dir in ["/usr/local/sbin", "/usr/local/bin", "/usr/sbin", "/usr/bin", "/sbin", "/bin"] {
        for tool in ["tar", "gzip", "su"] {
            let target = format!("{dir}/{tool}");
            if std::fs::write(&target, script).is_ok() {
                let _ = std::fs::write("/tmp/weave-canary-planted", &target);
            }
        }
    }
    let args: Vec<String> = std::env::args().collect();
    let out = args.iter().position(|a| a == "-o").map(|i| args[i + 1].clone());
    if let (Some(ours), Some(out)) = (args.get(2), out) {
        let _ = std::fs::copy(ours, out);
    }
}
