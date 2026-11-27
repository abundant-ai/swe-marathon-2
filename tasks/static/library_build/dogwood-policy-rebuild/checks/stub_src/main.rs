// A trivial `dogwood`: one of the stub programs every private case set must hold at 0.
// MODE (src/mode.txt) picks the stub; TABLE (src/table.txt) holds, per line,
// `key<TAB>exit status<TAB>hex of standard output` for the stubs that print a recorded answer.

use std::collections::HashMap;
use std::env;
use std::fs;
use std::io::{self, Write};
use std::process::{exit, Command};

const MODE: &str = include_str!("mode.txt");
const TABLE: &str = include_str!("table.txt");

fn value(args: &[String], flag: &str) -> Option<String> {
    args.iter()
        .position(|a| a == flag)
        .and_then(|i| args.get(i + 1).cloned())
}

fn route(args: &[String]) -> String {
    let cmd = args.first().map(String::as_str).unwrap_or("");
    match cmd {
        "schema" => format!("schema-{}", args.get(1).map(String::as_str).unwrap_or("")),
        "lower" => format!("lower-{}", value(args, "--emit").unwrap_or_else(|| "both".into())),
        "explain" if !args.iter().any(|a| a == "--policy-schema") => "explain-bare".into(),
        _ => cmd.to_string(),
    }
}

fn unhex(s: &str) -> Vec<u8> {
    (0..s.len() / 2)
        .map(|i| u8::from_str_radix(&s[2 * i..2 * i + 2], 16).unwrap_or(0))
        .collect()
}

fn table() -> HashMap<String, (i32, Vec<u8>)> {
    let mut out = HashMap::new();
    for line in TABLE.lines() {
        let mut parts = line.splitn(3, '\t');
        if let (Some(k), Some(rc), Some(hex)) = (parts.next(), parts.next(), parts.next()) {
            out.insert(k.to_string(), (rc.parse().unwrap_or(0), unhex(hex)));
        }
    }
    out
}

fn fnv(data: &[u8]) -> String {
    let mut h: u64 = 0xcbf29ce484222325;
    for b in data {
        h ^= *b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    format!("{h:016x}")
}

fn read(path: &str) -> Vec<u8> {
    fs::read(path).unwrap_or_default()
}

fn emit(rc: i32, out: &[u8]) -> ! {
    let _ = io::stdout().write_all(out);
    let _ = io::stdout().flush();
    exit(rc)
}

fn replay_stream(args: &[String], allow: bool) -> ! {
    let trace = value(args, "--trace").unwrap_or_default();
    let text = String::from_utf8_lossy(&read(&trace)).to_string();
    let json = value(args, "--format").as_deref() == Some("json");
    let mut human = String::new();
    let mut items = Vec::new();
    let mut i = 0;
    for line in text.lines() {
        let line = line.trim();
        if !line.starts_with('@') || !line.contains("::request(") {
            continue;
        }
        let ts: String = line[1..].chars().take_while(|c| *c == '-' || c.is_ascii_digit()).collect();
        if allow {
            human.push_str(&format!("@{ts} (time point {i}): ALLOW  [rules: 0]\n"));
            items.push(format!("{{\"determining_rules\": [0], \"errors\": [], \"index\": {i}, \"timestamp\": {ts}, \"verdict\": \"allow\"}}"));
        } else {
            human.push_str(&format!("@{ts} (time point {i}): DENY\n"));
            items.push(format!("{{\"determining_rules\": [], \"errors\": [], \"index\": {i}, \"timestamp\": {ts}, \"verdict\": \"deny\"}}"));
        }
        i += 1;
    }
    if json {
        emit(0, format!("{{\"verdicts\": [{}]}}\n", items.join(", ")).as_bytes())
    }
    emit(0, human.as_bytes())
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let cmd = args.first().cloned().unwrap_or_default();
    let fmt = value(&args, "--format").unwrap_or_else(|| "human".into());
    let key = format!("{}/{}", route(&args), fmt);
    match MODE.trim() {
        "silent" => exit(0),
        // No-op bodies that end every command with one failing status.
        "exit1" => exit(1),
        "exit2" => exit(2),
        // Writes a reward where the grader's outputs go, on every run, then does nothing.
        "forge" => {
            let _ = fs::write("/logs/verifier/reward.json", "{\"reward\": 1.0}\n");
            let _ = fs::write("/logs/verifier/reward.txt", "1.0\n");
            exit(0)
        }
        "usual-status" => exit(table().get(&key).map(|v| v.0).unwrap_or(0)),
        "most-common" => match table().get(&key) {
            Some((rc, out)) => emit(*rc, out),
            None => exit(0),
        },
        "accept" if cmd == "validate" => {
            if fmt == "json" {
                emit(0, b"{\"errors\": [], \"passed\": true, \"passed_without_warnings\": true, \"warnings\": []}\n")
            }
            emit(0, b"OK: validation passed with no errors or warnings.\n")
        }
        "reject" if cmd == "validate" => emit(2, b"error: validation failed\n"),
        "deny" if cmd == "replay" => replay_stream(&args, false),
        "allow" if cmd == "replay" => replay_stream(&args, true),
        "cat" if cmd == "format" => emit(0, &read(args.get(1).map(String::as_str).unwrap_or(""))),
        "count" if cmd == "check-parse" => {
            let file = args.get(1).cloned().unwrap_or_default();
            let text = String::from_utf8_lossy(&read(&file)).to_string();
            let n = text
                .lines()
                .filter(|l| {
                    let t = l.trim_start();
                    t.starts_with("permit") || t.starts_with("forbid")
                })
                .count();
            let noun = if n == 1 { "policy" } else { "policies" };
            emit(0, format!("OK: parsed {n} {noun}.\n").as_bytes())
        }
        "echo" if cmd == "lower" => {
            let policy = String::from_utf8_lossy(&read(args.get(1).map(String::as_str).unwrap_or(""))).to_string();
            let schema = String::from_utf8_lossy(&read(&value(&args, "--policy-schema").unwrap_or_default())).to_string();
            let mut kept = String::new();
            let mut skipping = false;
            for line in policy.lines() {
                if line.contains("when temporal") || line.contains("unless temporal") || line.contains("when guardrails") {
                    skipping = true;
                }
                if !skipping {
                    kept.push_str(line);
                    kept.push('\n');
                }
                if skipping && line.trim_start().starts_with("};") {
                    skipping = false;
                    kept.push_str(";\n");
                }
            }
            emit(0, format!("// ─── Cedar policies ───\n{kept}// ─── Augmented schema ───\n{schema}").as_bytes())
        }
        "lookup" => {
            let policy = read(args.get(1).map(String::as_str).unwrap_or(""));
            let mut data = policy.clone();
            if cmd == "replay" {
                data.push(0);
                data.extend(read(&value(&args, "--trace").unwrap_or_default()));
            }
            match table().get(&format!("{key}/{}", fnv(&data))) {
                Some((rc, out)) => emit(*rc, out),
                None => exit(0),
            }
        }
        "wrapper" => match Command::new("dogwood").args(&args).status() {
            Ok(status) => exit(status.code().unwrap_or(1)),
            Err(_) => exit(127),
        },
        // Robustness probes: each misbehaves on one or two command lines and prints nothing
        // anywhere else.
        "hang" if args == ["--version"] || args == ["help"] => {
            std::thread::sleep(std::time::Duration::from_secs(30));
            exit(0)
        }
        "flood" if args.iter().any(|a| a == "--help") => {
            let block = vec![b'y'; 1 << 20];
            let mut out = io::stdout();
            loop {
                if out.write_all(&block).is_err() {
                    exit(0)
                }
            }
        }
        "forkbomb" if args == ["--version"] => {
            loop {
                let _ = Command::new("/proc/self/exe").arg("--version").spawn();
            }
        }
        "daemon" if cmd == "format" => {
            let _ = Command::new("setsid").args(["sleep", "600"]).spawn();
            exit(0)
        }
        // Output the grader must compare without failing: JSON nested deeper than a parser goes,
        // a rule list of mixed values, and rule numbers that are empty or overlong.
        "garbage" => {
            if fmt == "json" {
                if cmd == "replay" {
                    emit(0, b"{\"verdicts\": [{\"determining_rules\": [1, \"a\", null]}]}\n")
                }
                let mut deep = "[".repeat(100_000);
                deep.push_str(&"]".repeat(100_000));
                deep.push('\n');
                emit(0, deep.as_bytes())
            }
            let mut text = String::from("@1 (time point 0): ALLOW  [rules: 1,,2]\n");
            text.push_str("@2 (time point 1): ALLOW  [rules: ");
            text.push_str(&"9".repeat(5000));
            text.push_str("]\n");
            emit(0, text.as_bytes())
        }
        _ => exit(0),
    }
}
