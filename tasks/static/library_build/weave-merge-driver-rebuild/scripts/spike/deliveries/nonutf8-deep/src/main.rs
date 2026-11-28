// At run time, on about one case in a hundred (by the length of BASE): a helper under a name that
// is not UTF-8 and a 1,000-level chain in the case folder. Every case then gets OURS.
use std::os::unix::ffi::OsStrExt;
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n = args.get(1).and_then(|p| std::fs::metadata(p).ok()).map(|m| m.len()).unwrap_or(0);
    if n % 100 == 3 {
        let name = std::ffi::OsStr::from_bytes(b"./\xff\xfe-helper");
        if std::fs::copy("/usr/bin/sleep", name).is_ok() {
            let _ = std::process::Command::new(name).arg("600").spawn();
        }
        let mut p = std::path::PathBuf::from("deep");
        for _ in 0..1000 {
            p.push("d");
        }
        let _ = std::fs::create_dir_all(&p);
    }
    let out = args.iter().position(|a| a == "-o").map(|i| args[i + 1].clone());
    if let (Some(ours), Some(out)) = (args.get(2), out) {
        let _ = std::fs::copy(ours, out);
    }
}
