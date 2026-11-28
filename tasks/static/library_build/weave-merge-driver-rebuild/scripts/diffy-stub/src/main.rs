//! Stub Z6: diffy 0.5.2's three-way merge with the driver's hint line; no entity merging.
use std::{env, fs, process};

const TEACH: &str = "weave: run 'weave explain ";

fn teach(content: &str, path: &str) -> String {
    let close = ">".repeat(7);
    let mut out = String::new();
    let mut done = false;
    for piece in content.split_inclusive('\n') {
        let line = piece.strip_suffix('\n').unwrap_or(piece);
        let line = line.strip_suffix('\r').unwrap_or(line);
        let is_close = line.starts_with(&close) && !line[close.len()..].starts_with('>') && !line.contains(TEACH);
        if !done && is_close {
            out.push_str(line);
            out.push_str(&format!(" \u{00b7} {TEACH}{path}' for per-hunk detail, 'weave check' to verify your resolution"));
            out.push_str(&piece[line.len()..]);
            done = true;
        } else {
            out.push_str(piece);
        }
    }
    out
}

fn main() {
    let a: Vec<String> = env::args().collect();
    let out = &a[a.iter().position(|x| x == "-o").unwrap() + 1];
    let path = &a[a.iter().position(|x| x == "-p").unwrap() + 1];
    let read = |p: &str| fs::read_to_string(p).unwrap_or_else(|_| process::exit(2));
    let (base, ours, theirs) = (read(&a[1]), read(&a[2]), read(&a[3]));
    if [&base, &ours, &theirs].iter().any(|t| t.as_bytes().iter().take(8192).any(|b| *b == 0)) {
        process::exit(2);
    }
    match diffy::merge(&base, &ours, &theirs) {
        Ok(text) => {
            fs::write(out, text).unwrap();
            process::exit(0);
        }
        Err(text) => {
            fs::write(out, teach(&text, path)).unwrap();
            process::exit(1);
        }
    }
}
