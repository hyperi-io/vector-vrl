#!/usr/bin/env rust
//! Build script for vector-bindings with auto-detection
//! Performs Vector version detection at build time using web fetch

use std::env;
use std::fs;
use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=vector_deps.toml");
    println!("cargo:rerun-if-env-changed=VECTORDOTDEV_VECTOR_VERSION");
    
    // Auto-detect Vector version at build time
    if let Ok(version) = detect_vector_version() {
        println!("cargo:rustc-env=DETECTED_VECTOR_VERSION={}", version);
        
        // Generate Cargo.toml dependencies dynamically
        if let Err(e) = update_dependencies_for_version(&version) {
            println!("cargo:warning=Failed to update dependencies: {}", e);
        }
    } else {
        println!("cargo:warning=Could not auto-detect Vector version");
    }
}

fn detect_vector_version() -> Result<String, Box<dyn std::error::Error>> {
    // Check environment variable first
    if let Ok(version) = env::var("VECTORDOTDEV_VECTOR_VERSION") {
        println!("Using Vector version from environment: {}", version);
        return Ok(version);
    }
    
    // Run Python version detection script
    let python_script = "../vectordotdev/version_detection.py";
    
    if std::path::Path::new(python_script).exists() {
        println!("Running Vector version auto-detection...");
        
        let output = Command::new("python3")
            .arg(python_script)
            .arg("--latest")
            .output()?;
        
        if output.status.success() {
            let stdout = String::from_utf8(output.stdout)?;
            
            // Parse output to find version
            for line in stdout.lines() {
                if line.contains("Latest compatible Vector version:") {
                    if let Some(version) = line.split(':').nth(1) {
                        let version = version.trim();
                        println!("Auto-detected Vector version: {}", version);
                        return Ok(version.to_string());
                    }
                }
            }
        } else {
            let stderr = String::from_utf8_lossy(&output.stderr);
            println!("cargo:warning=Version detection failed: {}", stderr);
        }
    }
    
    Err("Could not detect Vector version".into())
}

fn update_dependencies_for_version(version: &str) -> Result<(), Box<dyn std::error::Error>> {
    // This would dynamically update Cargo.toml with the detected version
    // For now, just emit build info
    println!("cargo:rustc-cfg=vector_version=\"{}\"", version);
    println!("cargo:VERSION={}", version);
    
    Ok(())
}