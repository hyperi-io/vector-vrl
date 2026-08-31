//! Dump every VRL stdlib function's upstream examples as JSON.

use vrl::compiler::Function;

fn main() {
    let mut out = Vec::new();
    for f in vrl::stdlib::all() {
        let id = f.identifier();
        for ex in f.examples() {
            out.push(serde_json::json!({
                "function": id,
                "title": ex.title,
                "source": ex.source,
                "input": ex.input,
                "ok": ex.result.ok(),
                "err": ex.result.err(),
                "deterministic": ex.deterministic,
                "skip": ex.skip,
            }));
        }
    }
    println!("{}", serde_json::to_string(&out).unwrap());
}
