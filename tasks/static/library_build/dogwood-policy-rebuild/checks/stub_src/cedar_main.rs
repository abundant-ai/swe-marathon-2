// A `dogwood` with no history: `replay` drops every temporal condition of the policy set, hands
// the rest to Cedar 4.14 (from the registry), and decides each request of the trace on its own.
// Every other command prints nothing. The private case set must hold it at 0.

use cedar_policy::{Authorizer, Context, Decision, Entities, EntityUid, PolicySet, Request, RestrictedExpression};
use std::collections::BTreeSet;
use std::env;
use std::fs;
use std::io::{self, Read, Write};
use std::process::exit;
use std::str::FromStr;

fn value(args: &[String], flag: &str) -> Option<String> {
    args.iter().position(|a| a == flag).and_then(|i| args.get(i + 1).cloned())
}

fn read(path: &str) -> String {
    if path == "-" {
        let mut s = String::new();
        let _ = io::stdin().read_to_string(&mut s);
        return s;
    }
    fs::read_to_string(path).unwrap_or_default()
}

/// The index after the string literal that opens at `i`.
fn string_end(b: &[u8], mut i: usize) -> usize {
    i += 1;
    while i < b.len() {
        match b[i] {
            b'\\' => i += 2,
            b'"' => return i + 1,
            _ => i += 1,
        }
    }
    b.len()
}

/// The index after the bracket that closes the one at `i`.
fn close(b: &[u8], mut i: usize) -> Option<usize> {
    let mut depth = 0i32;
    while i < b.len() {
        match b[i] {
            b'"' => {
                i = string_end(b, i);
                continue;
            }
            b'(' | b'[' | b'{' => depth += 1,
            b')' | b']' | b'}' => {
                depth -= 1;
                if depth == 0 {
                    return Some(i + 1);
                }
            }
            _ => {}
        }
        i += 1;
    }
    None
}

/// The policy text without its temporal conditions: `when temporal { … }` and `unless temporal
/// { … }` removed, an inline `temporal { … }` read as `true`.
fn drop_temporal(text: &str) -> String {
    let b = text.as_bytes();
    let mut out = String::new();
    let mut i = 0;
    while i < b.len() {
        if b[i] == b'"' {
            let j = string_end(b, i);
            out.push_str(&text[i..j]);
            i = j;
            continue;
        }
        if text[i..].starts_with("//") {
            let j = text[i..].find('\n').map_or(b.len(), |k| i + k);
            i = j;
            continue;
        }
        let mut replaced = false;
        for (head, replacement) in [("when temporal", ""), ("unless temporal", ""), ("temporal", "true")] {
            let word_start = i == 0 || !(b[i - 1].is_ascii_alphanumeric() || b[i - 1] == b'_');
            if word_start && text[i..].starts_with(head) {
                let rest = text[i + head.len()..].trim_start();
                if rest.starts_with('{') {
                    if let Some(end) = close(b, text.len() - rest.len()) {
                        out.push_str(replacement);
                        i = end;
                        replaced = true;
                        break;
                    }
                }
            }
        }
        if replaced {
            continue;
        }
        let c = text[i..].chars().next().unwrap();
        out.push(c);
        i += c.len_utf8();
    }
    out
}

/// The top-level `name: value` parts of a group's inside.
fn parts(inside: &str) -> Vec<(String, String)> {
    let b = inside.as_bytes();
    let mut out = Vec::new();
    let mut start = 0;
    let mut i = 0;
    while i <= b.len() {
        if i == b.len() || b[i] == b',' {
            let part = inside[start..i].trim();
            if let Some(colon) = part.find(':') {
                out.push((part[..colon].trim().to_string(), part[colon + 1..].trim().to_string()));
            }
            start = i + 1;
            i += 1;
            continue;
        }
        match b[i] {
            b'"' => i = string_end(b, i),
            b'(' | b'[' | b'{' => i = close(b, i).unwrap_or(b.len()),
            _ => i += 1,
        }
    }
    out
}

struct Event {
    ts: String,
    scope: Vec<(String, String)>,
    context: Vec<(String, String)>,
    action: String,
    kind: String,
}

fn event(line: &str) -> Option<Event> {
    let line = line.trim();
    let rest = line.strip_prefix('@')?;
    let ts: String = rest.chars().take_while(|c| *c == '-' || c.is_ascii_digit()).collect();
    let mut text = rest[ts.len()..].trim_start();
    let (mut scope, mut context) = (Vec::new(), Vec::new());
    loop {
        let b = text.as_bytes();
        let open = text.find('(')?;
        let head = text[..open].trim();
        let end = close(b, open)?;
        let inside = &text[open + 1..end - 1];
        match head {
            "scope" => scope = parts(inside),
            "entities" => {}
            "request_context" => context = parts(inside),
            _ => {
                let cut = head.rfind("::")?;
                return Some(Event { ts, scope, context, action: head[..cut].to_string(), kind: head[cut + 2..].to_string() });
            }
        }
        text = text[end..].trim_start();
    }
}

fn decision_kinds(schema: Option<String>) -> BTreeSet<String> {
    let mut kinds = BTreeSet::new();
    match schema {
        None => {
            kinds.insert("request".to_string());
        }
        Some(text) => {
            for line in text.lines() {
                let line = line.trim();
                if let Some(rest) = line.strip_prefix("decision event") {
                    if let Some(k) = rest.split("::").nth(1) {
                        kinds.insert(k.trim().trim_end_matches('{').trim().to_string());
                    }
                }
            }
        }
    }
    kinds
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.first().map(String::as_str) != Some("replay") {
        exit(0)
    }
    let policy = read(args.get(1).map(String::as_str).unwrap_or(""));
    let trace = read(&value(&args, "--trace").unwrap_or_default());
    let json = value(&args, "--format").as_deref() == Some("json");
    let kinds = decision_kinds(value(&args, "--event-schema").map(|p| read(&p)));
    let policies = match PolicySet::from_str(&drop_temporal(&policy)) {
        Ok(p) => p,
        Err(_) => exit(2),
    };
    let authorizer = Authorizer::new();
    let entities = Entities::empty();
    let (mut human, mut items) = (String::new(), Vec::new());
    let mut index = 0;
    for line in trace.lines().filter(|l| !l.trim().is_empty()) {
        let Some(ev) = event(line) else { exit(2) };
        if !kinds.contains(&ev.kind) {
            continue;
        }
        let uid = |key: &str| ev.scope.iter().find(|(k, _)| k == key).and_then(|(_, v)| EntityUid::from_str(v).ok());
        let context = Context::from_pairs(
            ev.context.iter().filter_map(|(k, v)| RestrictedExpression::from_str(v).ok().map(|e| (k.clone(), e))),
        );
        let decided = match (uid("principal"), EntityUid::from_str(&ev.action), uid("resource"), context) {
            (Some(p), Ok(a), Some(r), Ok(c)) => Request::new(p, a, r, c, None).ok().map(|q| authorizer.is_authorized(&q, &policies, &entities)),
            _ => None,
        };
        let (allow, rules): (bool, Vec<usize>) = match decided {
            Some(resp) => {
                let mut rules: Vec<usize> = resp
                    .diagnostics()
                    .reason()
                    .filter_map(|id| id.to_string().strip_prefix("policy").and_then(|n| n.parse().ok()))
                    .collect();
                rules.sort_unstable();
                (resp.decision() == Decision::Allow, rules)
            }
            None => (false, Vec::new()),
        };
        let list = rules.iter().map(usize::to_string).collect::<Vec<_>>().join(", ");
        let verdict = if allow { "ALLOW" } else { "DENY" };
        if rules.is_empty() {
            human.push_str(&format!("@{} (time point {index}): {verdict}\n", ev.ts));
        } else {
            human.push_str(&format!("@{} (time point {index}): {verdict}  [rules: {list}]\n", ev.ts));
        }
        items.push(format!(
            "{{\"determining_rules\": [{list}], \"errors\": [], \"index\": {index}, \"timestamp\": {}, \"verdict\": \"{}\"}}",
            ev.ts,
            verdict.to_lowercase()
        ));
        index += 1;
    }
    let out = if json { format!("{{\"verdicts\": [{}]}}\n", items.join(", ")) } else { human };
    let _ = io::stdout().write_all(out.as_bytes());
}
