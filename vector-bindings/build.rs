use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use syn::{Item, Visibility};
use walkdir::WalkDir;

#[derive(Debug, Clone)]
struct ApiInfo {
    name: String,
    kind: ApiKind,
}

#[derive(Debug, Clone)]
enum ApiKind {
    Struct,
    Enum { variants: Vec<String> },
}

fn main() {
    println!("cargo:rerun-if-changed=build.rs");

    // Auto-discover from multiple Vector modules (NO HARDCODING!)
    let search_paths = vec![
        PathBuf::from("../vector/lib/vector-core/src/event"),
        PathBuf::from("../vector/lib/vector-common/src"),
    ];

    let mut all_apis = Vec::new();

    println!("cargo:warning=🔍 Auto-discovering Vector APIs from multiple modules...");

    for path in &search_paths {
        if path.exists() {
            let apis = discover_apis(path);
            println!(
                "cargo:warning=  ✅ {} - {} APIs",
                path.display(),
                apis.len()
            );
            all_apis.extend(apis);
        } else {
            println!(
                "cargo:warning=  ⚠️  {} - not found, skipping",
                path.display()
            );
        }
    }

    // Deduplicate APIs by name (keep first occurrence)
    let mut seen = std::collections::HashSet::new();
    all_apis.retain(|api| seen.insert(api.name.clone()));

    println!(
        "cargo:warning=✅ Discovered {} unique Vector APIs across all modules",
        all_apis.len()
    );

    let bindings = generate_bindings(&all_apis);

    let out_dir = env::var("OUT_DIR").expect("OUT_DIR is always set by Cargo for build scripts");
    let dest_path = Path::new(&out_dir).join("auto_bindings.rs");
    fs::write(&dest_path, bindings)
        .unwrap_or_else(|e| panic!("failed to write generated bindings to {dest_path:?}: {e}"));
    println!(
        "cargo:warning=✅ Generated {} auto-bindings",
        all_apis.len()
    );
}

fn discover_apis(root_path: &Path) -> Vec<ApiInfo> {
    let mut apis = Vec::new();
    let skip_names = ["Secrets", "BTreeMap", "HashMap"]; // Skip conflicting types

    for entry in WalkDir::new(root_path)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.path().extension().and_then(|s| s.to_str()) == Some("rs"))
    {
        if let Ok(content) = fs::read_to_string(entry.path())
            && let Ok(syntax) = syn::parse_file(&content)
        {
            for item in &syntax.items {
                match item {
                    Item::Struct(s) if is_public(&s.vis) => {
                        let name = s.ident.to_string();
                        if !skip_names.contains(&name.as_str()) && !name.starts_with('_') {
                            apis.push(ApiInfo {
                                name,
                                kind: ApiKind::Struct,
                            });
                        }
                    }
                    Item::Enum(e) if is_public(&e.vis) => {
                        let name = e.ident.to_string();
                        if !skip_names.contains(&name.as_str()) && !name.starts_with('_') {
                            let variants = e.variants.iter().map(|v| v.ident.to_string()).collect();
                            apis.push(ApiInfo {
                                name,
                                kind: ApiKind::Enum { variants },
                            });
                        }
                    }
                    _ => {}
                }
            }
        }
    }

    apis
}

fn is_public(vis: &Visibility) -> bool {
    matches!(vis, Visibility::Public(_))
}

fn generate_bindings(apis: &[ApiInfo]) -> String {
    let mut code = String::from(
        r#"// AUTO-GENERATED from Vector - DO NOT EDIT

// pyo3::prelude is already in scope: this file is spliced into lib.rs via
// include!(), which already imports it before the include! call.
#[allow(dead_code, unused_variables)]
"#,
    );

    for api in apis {
        code.push_str(&match &api.kind {
            ApiKind::Struct => format!(
                r#"#[pyclass]
#[derive(Clone, Debug)]
pub struct {name} {{
    #[pyo3(get, set)]
    pub data: String,
}}

#[pymethods]
impl {name} {{
    #[new]
    pub fn new() -> Self {{ {name} {{ data: String::new() }} }}
    pub fn __repr__(&self) -> String {{ format!("{name}()") }}
}}

"#,
                name = api.name
            ),
            ApiKind::Enum { variants } => {
                let methods = variants
                    .iter()
                    .map(|v| {
                        format!(
                            "    #[staticmethod]\n    pub fn {lower}() -> Self {{ {name} {{ v: \"{v}\".to_string() }} }}",
                            lower = v.to_lowercase(),
                            name = api.name,
                            v = v
                        )
                    })
                    .collect::<Vec<_>>()
                    .join("\n");

                format!(
                    r#"#[pyclass]
#[derive(Clone, Debug)]
pub struct {name} {{ v: String }}

#[pymethods]
impl {name} {{
{methods}
    pub fn __repr__(&self) -> String {{ format!("{name}::{{}}", self.v) }}
}}

"#,
                    name = api.name,
                    methods = methods
                )
            }
        });
    }

    code.push_str(&format!(
        r#"pub fn register_all_auto_bindings(m: &Bound<'_, PyModule>) -> PyResult<()> {{
{}
    m.add("__auto_count__", {})?;
    Ok(())
}}"#,
        apis.iter()
            .map(|a| format!("    m.add_class::<{}>()?;", a.name))
            .collect::<Vec<_>>()
            .join("\n"),
        apis.len()
    ));

    code
}
