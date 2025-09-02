use std::env;
use std::fs;
use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=Cargo.toml");
    
    // Check if we should update the Vector version
    if env::var("SKIP_VECTOR_UPDATE").is_err() {
        update_vector_version();
    }
    
    // Check if we should update all dependencies to latest versions
    if env::var("UPDATE_DEPENDENCIES").is_ok() {
        update_dependencies();
    }
}

fn update_vector_version() {
    // Check if smart-build script already determined a working version
    if let Ok(build_info) = fs::read_to_string(".vector-build-info") {
        if build_info.contains("BUILD_SUCCESS=true") {
            for line in build_info.lines() {
                if line.starts_with("VECTOR_VERSION=") {
                    let version = line.split('=').nth(1).unwrap_or("");
                    if !version.is_empty() {
                        println!("cargo:warning=Using previously validated Vector version: {}", version);
                        return update_cargo_toml_version(version);
                    }
                }
            }
        }
    }
    
    let latest_version = get_latest_compatible_vector_version();
    println!("cargo:warning=Using Vector version: {}", latest_version);
    update_cargo_toml_version(&latest_version);
}

fn update_cargo_toml_version(version: &str) {
    let cargo_toml_path = "Cargo.toml";
    if let Ok(content) = fs::read_to_string(cargo_toml_path) {
        let mut updated = false;
        let mut new_content = String::new();
        
        for line in content.lines() {
            if line.contains("git = \"https://github.com/vectordotdev/vector.git\"") {
                // Replace the rev/tag/branch specification
                if line.contains("rev = ") || line.contains("tag = ") || line.contains("branch = ") {
                    // Extract the part before the rev/tag/branch and after
                    let before = line.split(", ").next().unwrap_or(line);
                    let after_parts: Vec<_> = line.split(", ").skip(2).collect();
                    let after = after_parts.join(", ");
                    let new_line = if after.is_empty() {
                        format!("{}, tag = \"{}\"", before, version)
                    } else {
                        format!("{}, tag = \"{}\", {}", before, version, after)
                    };
                    new_content.push_str(&new_line);
                    updated = true;
                } else {
                    // Add tag specification
                    let new_line = line.replace(
                        "git = \"https://github.com/vectordotdev/vector.git\"",
                        &format!("git = \"https://github.com/vectordotdev/vector.git\", tag = \"{}\"", version)
                    );
                    new_content.push_str(&new_line);
                    updated = true;
                }
            } else {
                new_content.push_str(line);
            }
            new_content.push('\n');
        }
        
        // Write back if updated
        if updated {
            if let Err(e) = fs::write(cargo_toml_path, new_content.trim_end()) {
                println!("cargo:warning=Failed to update Cargo.toml: {}", e);
            } else {
                println!("cargo:warning=Updated Cargo.toml with Vector version {}", version);
            }
        }
    }
}

fn update_dependencies() {
    println!("cargo:warning=Checking for latest compatible dependency versions...");
    
    // Update Cargo dependencies to latest compatible versions
    if let Err(e) = Command::new("cargo")
        .args(["update"])
        .status()
    {
        println!("cargo:warning=Failed to update dependencies: {}", e);
    } else {
        println!("cargo:warning=Updated dependencies to latest compatible versions");
    }
}

fn get_latest_compatible_vector_version() -> String {
    println!("cargo:warning=Detecting latest stable Vector version...");
    
    // Try to get the latest stable release
    if let Ok(latest) = get_latest_stable_vector_release() {
        println!("cargo:warning=Found latest stable Vector version: {}", latest);
        
        // Test if this version is available for download
        if is_vector_version_available(&latest) {
            return latest;
        } else {
            println!("cargo:warning=Latest version {} not available, trying fallback", latest);
        }
    }
    
    // Fallback: get latest available tag from git repository
    if let Ok(version) = get_latest_git_tag() {
        println!("cargo:warning=Using latest git tag: {}", version);
        return version;
    }
    
    // Emergency fallback: get any available version by scanning git tags  
    if let Ok(output) = Command::new("git")
        .args([
            "ls-remote", "--tags", "--refs",
            "https://github.com/vectordotdev/vector.git"
        ])
        .output()
    {
        if output.status.success() {
            let response = String::from_utf8_lossy(&output.stdout);
            
            // Collect all stable versions and sort them
            let mut versions: Vec<String> = response
                .lines()
                .filter_map(|line| line.split("refs/tags/").nth(1))
                .filter(|tag| {
                    tag.starts_with('v') 
                        && !tag.contains('-') 
                        && !tag.contains("rc") 
                        && !tag.contains("beta") 
                        && !tag.contains("alpha")
                        && tag.matches('.').count() >= 1 // Ensure it's a proper version
                })
                .map(|s| s.to_string())
                .collect();
            
            // Sort versions in descending order (newest first)
            versions.sort_by(|a, b| {
                let a_parts: Vec<u32> = a.trim_start_matches('v')
                    .split('.')
                    .filter_map(|s| s.parse().ok())
                    .collect();
                let b_parts: Vec<u32> = b.trim_start_matches('v')
                    .split('.')
                    .filter_map(|s| s.parse().ok())
                    .collect();
                
                for (a_part, b_part) in a_parts.iter().zip(b_parts.iter()) {
                    match b_part.cmp(a_part) {
                        std::cmp::Ordering::Equal => continue,
                        other => return other,
                    }
                }
                b_parts.len().cmp(&a_parts.len())
            });
            
            // Return the newest version
            if let Some(latest) = versions.first() {
                println!("cargo:warning=Using latest discovered stable version: {}", latest);
                return latest.clone();
            }
        }
    }
    
    // Absolute last resort - panic with helpful message
    panic!(
        "Could not find any Vector version. Please check:\n\
         1. Internet connectivity\n\
         2. Git access to https://github.com/vectordotdev/vector.git\n\
         3. GitHub API access\n\
         You can also set SKIP_VECTOR_UPDATE=1 to bypass version detection"
    );
}

fn get_latest_stable_vector_release() -> Result<String, Box<dyn std::error::Error>> {
    let output = Command::new("curl")
        .args([
            "-s", "-f", "--connect-timeout", "5",
            "-H", "Accept: application/vnd.github.v3+json",
            "https://api.github.com/repos/vectordotdev/vector/releases/latest"
        ])
        .output()?;

    if output.status.success() {
        let response = String::from_utf8_lossy(&output.stdout);
        if let Some(start) = response.find("\"tag_name\":\"") {
            let start = start + 12;
            if let Some(end) = response[start..].find("\"") {
                let version = &response[start..start + end];
                // Only return if it's a stable version (no pre-release markers)
                if !version.contains('-') && !version.contains("rc") && !version.contains("beta") && !version.contains("alpha") {
                    return Ok(version.to_string());
                }
            }
        }
    }
    
    Err("No stable release found".into())
}

fn get_latest_git_tag() -> Result<String, Box<dyn std::error::Error>> {
    let output = Command::new("git")
        .args([
            "ls-remote", "--tags", "--refs", "--sort=-version:refname",
            "https://github.com/vectordotdev/vector.git"
        ])
        .output()?;

    if output.status.success() {
        let response = String::from_utf8_lossy(&output.stdout);
        // Find the first stable version tag
        for line in response.lines() {
            if let Some(tag_part) = line.split("refs/tags/").nth(1) {
                // Only consider stable versions (no pre-release markers)
                if tag_part.starts_with('v') 
                    && !tag_part.contains('-') 
                    && !tag_part.contains("rc") 
                    && !tag_part.contains("beta") 
                    && !tag_part.contains("alpha") {
                    return Ok(tag_part.to_string());
                }
            }
        }
    }
    
    Err("No stable git tags found".into())
}

fn is_vector_version_available(version: &str) -> bool {
    Command::new("git")
        .args([
            "ls-remote", "--exit-code", "--heads", "--tags",
            "https://github.com/vectordotdev/vector.git",
            version
        ])
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

fn is_version_newer_than(version1: &str, version2: &str) -> bool {
    // Simple version comparison (assumes vX.Y.Z format)
    let v1_parts: Vec<u32> = version1.trim_start_matches('v')
        .split('.')
        .filter_map(|s| s.parse().ok())
        .collect();
    let v2_parts: Vec<u32> = version2.trim_start_matches('v')
        .split('.')
        .filter_map(|s| s.parse().ok())
        .collect();
    
    for (a, b) in v1_parts.iter().zip(v2_parts.iter()) {
        match a.cmp(b) {
            std::cmp::Ordering::Greater => return true,
            std::cmp::Ordering::Less => return false,
            std::cmp::Ordering::Equal => continue,
        }
    }
    
    v1_parts.len() > v2_parts.len()
}