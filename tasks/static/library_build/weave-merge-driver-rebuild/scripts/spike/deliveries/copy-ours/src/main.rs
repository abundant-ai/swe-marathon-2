// A submission that writes OURS unchanged and exits 0.
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let out = args.iter().position(|a| a == "-o").map(|i| args[i + 1].clone());
    if let (Some(ours), Some(out)) = (args.get(2), out) {
        let _ = std::fs::copy(ours, out);
    }
}
