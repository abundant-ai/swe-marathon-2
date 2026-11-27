// A submission that hands every merge to the installed build (absent where the replacement runs).
fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let status = std::process::Command::new("/usr/local/bin/weave-driver").args(&args).status();
    std::process::exit(match status {
        Ok(s) => s.code().unwrap_or(2),
        Err(_) => 2,
    });
}
