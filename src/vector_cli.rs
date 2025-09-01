use pyo3::prelude::*;
use pyo3::exceptions::{PyValueError, PyRuntimeError};
use std::collections::HashMap;
use std::path::PathBuf;
use crate::vector_app::VectorApp;
use crate::vector_context::VectorContext;
use tokio::sync::RwLock;
use vector::config::{load, Config, Format};
use vector::cli::LogFormat;

#[pyclass]
#[derive(Clone)]
pub struct VectorCliOptions {
    #[pyo3(get, set)]
    pub config_path: Option<String>,
    #[pyo3(get, set)]
    pub config_dir: Option<String>,
    #[pyo3(get, set)]
    pub watch_config: bool,
    #[pyo3(get, set)]
    pub quiet: bool,
    #[pyo3(get, set)]
    pub verbose: u8,
    #[pyo3(get, set)]
    pub log_format: String,
    #[pyo3(get, set)]
    pub require_healthy: Option<bool>,
    #[pyo3(get, set)]
    pub dry_run: bool,
    #[pyo3(get, set)]
    pub threads: Option<usize>,
    #[pyo3(get, set)]
    pub internal_log_rate_limit: Option<u32>,
    #[pyo3(get, set)]
    pub allow_empty_config: bool,
    #[pyo3(get, set)]
    pub config_vars: HashMap<String, String>,
}

#[pymethods]
impl VectorCliOptions {
    #[new]
    #[pyo3(signature = (
        config_path=None,
        config_dir=None, 
        watch_config=false,
        quiet=false,
        verbose=0,
        log_format="text".to_string(),
        require_healthy=None,
        dry_run=false,
        threads=None,
        internal_log_rate_limit=None,
        allow_empty_config=false,
        config_vars=None
    ))]
    fn new(
        config_path: Option<String>,
        config_dir: Option<String>,
        watch_config: bool,
        quiet: bool,
        verbose: u8,
        log_format: String,
        require_healthy: Option<bool>,
        dry_run: bool,
        threads: Option<usize>,
        internal_log_rate_limit: Option<u32>,
        allow_empty_config: bool,
        config_vars: Option<HashMap<String, String>>,
    ) -> Self {
        Self {
            config_path,
            config_dir,
            watch_config,
            quiet,
            verbose,
            log_format,
            require_healthy,
            dry_run,
            threads,
            internal_log_rate_limit,
            allow_empty_config,
            config_vars: config_vars.unwrap_or_default(),
        }
    }
    
    fn __str__(&self) -> String {
        format!(
            "VectorCliOptions(config_path={:?}, verbose={}, log_format='{}', dry_run={})",
            self.config_path, self.verbose, self.log_format, self.dry_run
        )
    }
    
    fn __repr__(&self) -> String {
        self.__str__()
    }
    
    fn to_args(&self) -> Vec<String> {
        let mut args = vec![];
        
        if let Some(ref config_path) = self.config_path {
            args.push("--config".to_string());
            args.push(config_path.clone());
        }
        
        if let Some(ref config_dir) = self.config_dir {
            args.push("--config-dir".to_string());
            args.push(config_dir.clone());
        }
        
        if self.watch_config {
            args.push("--watch-config".to_string());
        }
        
        if self.quiet {
            args.push("--quiet".to_string());
        }
        
        for _ in 0..self.verbose {
            args.push("--verbose".to_string());
        }
        
        if self.log_format != "text" {
            args.push("--log-format".to_string());
            args.push(self.log_format.clone());
        }
        
        if let Some(healthy) = self.require_healthy {
            if healthy {
                args.push("--require-healthy".to_string());
            } else {
                args.push("--no-require-healthy".to_string());
            }
        }
        
        if self.dry_run {
            args.push("--dry-run".to_string());
        }
        
        if let Some(threads) = self.threads {
            args.push("--threads".to_string());
            args.push(threads.to_string());
        }
        
        if let Some(rate_limit) = self.internal_log_rate_limit {
            args.push("--internal-log-rate-limit".to_string());
            args.push(rate_limit.to_string());
        }
        
        if self.allow_empty_config {
            args.push("--allow-empty-config".to_string());
        }
        
        for (key, value) in &self.config_vars {
            args.push("--config-var".to_string());
            args.push(format!("{}={}", key, value));
        }
        
        args
    }
}

#[pyclass(frozen)]
pub struct VectorCli {
    app: RwLock<Option<VectorApp>>,
    options: VectorCliOptions,
}

#[pymethods]
impl VectorCli {
    #[new]
    fn new(config: Option<String>, options: Option<VectorCliOptions>) -> PyResult<Self> {
        let opts = options.unwrap_or_else(|| VectorCliOptions::new(
            None, None, false, false, 0, "text".to_string(),
            None, false, None, None, false, None
        ));
        
        // Load configuration based on CLI options
        let vector_config = if let Some(config_content) = config {
            // Use provided config string
            create_config_from_string(&config_content, &opts)?
        } else if let Some(ref config_path) = opts.config_path {
            // Load from file path
            create_config_from_file(config_path, &opts)?
        } else if let Some(ref config_dir) = opts.config_dir {
            // Load from directory
            create_config_from_dir(config_dir, &opts)?
        } else {
            return Err(PyValueError::new_err(
                "Must provide either config string, config_path, or config_dir"
            ));
        };
        
        // Apply CLI-style initialization
        init_vector_cli(&opts)?;
        
        let context = VectorContext::global();
        let app = VectorApp::new(vector_config, context);
        
        Ok(Self {
            app: RwLock::new(Some(app)),
            options: opts,
        })
    }
    
    async fn start(&self) -> PyResult<()> {
        if self.options.dry_run {
            return Ok(()); // Don't actually start in dry run mode
        }
        
        let mut app_lock = self.app.write().await;
        let app = app_lock.take()
            .ok_or_else(|| PyRuntimeError::new_err("Vector instance already started or stopped"))?;
        let started = app.start().await;
        app_lock.replace(started);
        Ok(())
    }
    
    async fn stop(&self) -> PyResult<()> {
        let mut app_lock = self.app.write().await;
        let app = app_lock.take()
            .ok_or_else(|| PyRuntimeError::new_err("Vector instance not running"))?;
        let stopped = app.stop().await;
        app_lock.replace(stopped);
        Ok(())
    }
    
    async fn send(&self, source: String, data: Vec<u8>) -> PyResult<()> {
        if self.options.dry_run {
            return Ok(()); // Don't send in dry run mode
        }
        
        let app_lock = self.app.read().await;
        if let Some(app) = app_lock.as_ref() {
            let sender = app.get_sender(&source).await;
            sender.send(bytes::Bytes::from(data)).await
                .map_err(|e| PyRuntimeError::new_err(format!("Failed to send data: {}", e)))?;
        } else {
            return Err(PyRuntimeError::new_err("Vector instance not running"));
        }
        Ok(())
    }
    
    fn get_options(&self) -> VectorCliOptions {
        self.options.clone()
    }
    
    fn get_cli_args(&self) -> Vec<String> {
        self.options.to_args()
    }
}

fn create_config_from_string(config_content: &str, opts: &VectorCliOptions) -> PyResult<Config> {
    let mut builder = Config::builder();
    
    // Apply config variables substitution
    let processed_config = apply_config_vars(config_content, &opts.config_vars);
    
    builder
        .append(load(processed_config.as_bytes(), Format::Toml)
            .map_err(|e| PyValueError::new_err(format!("Invalid config: {}", e)))?)
        .map_err(|e| PyValueError::new_err(format!("Config error: {}", e)))?;
    
    let config = builder.build()
        .map_err(|e| PyValueError::new_err(format!("Failed to build config: {}", e)))?;
    
    // Validate config if not allowing empty
    if !opts.allow_empty_config && config.is_empty() {
        return Err(PyValueError::new_err("Config is empty and allow_empty_config is false"));
    }
    
    Ok(config)
}

fn create_config_from_file(config_path: &str, opts: &VectorCliOptions) -> PyResult<Config> {
    let path = PathBuf::from(config_path);
    if !path.exists() {
        return Err(PyValueError::new_err(format!("Config file not found: {}", config_path)));
    }
    
    let content = std::fs::read_to_string(&path)
        .map_err(|e| PyValueError::new_err(format!("Failed to read config file: {}", e)))?;
    
    create_config_from_string(&content, opts)
}

fn create_config_from_dir(config_dir: &str, opts: &VectorCliOptions) -> PyResult<Config> {
    let dir_path = PathBuf::from(config_dir);
    if !dir_path.exists() || !dir_path.is_dir() {
        return Err(PyValueError::new_err(format!("Config directory not found: {}", config_dir)));
    }
    
    let mut builder = Config::builder();
    
    // Load all .toml files in directory
    for entry in std::fs::read_dir(&dir_path)
        .map_err(|e| PyValueError::new_err(format!("Failed to read config directory: {}", e)))?
    {
        let entry = entry
            .map_err(|e| PyValueError::new_err(format!("Failed to read directory entry: {}", e)))?;
        let path = entry.path();
        
        if path.extension().and_then(|s| s.to_str()) == Some("toml") {
            let content = std::fs::read_to_string(&path)
                .map_err(|e| PyValueError::new_err(format!("Failed to read config file {:?}: {}", path, e)))?;
            
            let processed_content = apply_config_vars(&content, &opts.config_vars);
            
            builder
                .append(load(processed_content.as_bytes(), Format::Toml)
                    .map_err(|e| PyValueError::new_err(format!("Invalid config in {:?}: {}", path, e)))?)
                .map_err(|e| PyValueError::new_err(format!("Config error in {:?}: {}", path, e)))?;
        }
    }
    
    let config = builder.build()
        .map_err(|e| PyValueError::new_err(format!("Failed to build config: {}", e)))?;
    
    if !opts.allow_empty_config && config.is_empty() {
        return Err(PyValueError::new_err("No valid config files found in directory"));
    }
    
    Ok(config)
}

fn apply_config_vars(config: &str, vars: &HashMap<String, String>) -> String {
    let mut result = config.to_string();
    
    for (key, value) in vars {
        let placeholder = format!("${{{}}}", key);
        result = result.replace(&placeholder, value);
        
        // Also support $KEY format
        let alt_placeholder = format!("${}", key);
        result = result.replace(&alt_placeholder, value);
    }
    
    result
}

fn init_vector_cli(opts: &VectorCliOptions) -> PyResult<()> {
    // Initialize Vector with CLI-like settings
    
    // Set log format
    let log_format = match opts.log_format.as_str() {
        "text" => LogFormat::Text,
        "json" => LogFormat::Json,
        _ => LogFormat::Text,
    };
    
    // Set log level based on quiet/verbose flags
    let log_level = if opts.quiet {
        "warn"
    } else {
        match opts.verbose {
            0 => "info",
            1 => "debug", 
            _ => "trace",
        }
    };
    
    // Initialize Vector logging (similar to CLI)
    vector::app::init_logging(opts.quiet, log_format, log_level, opts.internal_log_rate_limit.unwrap_or(10));
    
    Ok(())
}

#[pyfunction]
pub fn vector_from_cli_args(args: Vec<String>, config: Option<String>) -> PyResult<VectorCli> {
    let options = parse_cli_args(args)?;
    VectorCli::new(config, Some(options))
}

#[pyfunction]
pub fn parse_cli_args(args: Vec<String>) -> PyResult<VectorCliOptions> {
    let mut opts = VectorCliOptions::new(
        None, None, false, false, 0, "text".to_string(),
        None, false, None, None, false, None
    );
    
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--config" | "-c" => {
                i += 1;
                if i >= args.len() {
                    return Err(PyValueError::new_err("--config requires a value"));
                }
                opts.config_path = Some(args[i].clone());
            }
            "--config-dir" => {
                i += 1;
                if i >= args.len() {
                    return Err(PyValueError::new_err("--config-dir requires a value"));
                }
                opts.config_dir = Some(args[i].clone());
            }
            "--watch-config" | "-w" => {
                opts.watch_config = true;
            }
            "--quiet" | "-q" => {
                opts.quiet = true;
            }
            "--verbose" | "-v" => {
                opts.verbose += 1;
            }
            "--log-format" => {
                i += 1;
                if i >= args.len() {
                    return Err(PyValueError::new_err("--log-format requires a value"));
                }
                opts.log_format = args[i].clone();
            }
            "--require-healthy" => {
                opts.require_healthy = Some(true);
            }
            "--no-require-healthy" => {
                opts.require_healthy = Some(false);
            }
            "--dry-run" => {
                opts.dry_run = true;
            }
            "--threads" => {
                i += 1;
                if i >= args.len() {
                    return Err(PyValueError::new_err("--threads requires a value"));
                }
                opts.threads = Some(args[i].parse()
                    .map_err(|_| PyValueError::new_err("--threads must be a number"))?);
            }
            "--internal-log-rate-limit" => {
                i += 1;
                if i >= args.len() {
                    return Err(PyValueError::new_err("--internal-log-rate-limit requires a value"));
                }
                opts.internal_log_rate_limit = Some(args[i].parse()
                    .map_err(|_| PyValueError::new_err("--internal-log-rate-limit must be a number"))?);
            }
            "--allow-empty-config" => {
                opts.allow_empty_config = true;
            }
            "--config-var" => {
                i += 1;
                if i >= args.len() {
                    return Err(PyValueError::new_err("--config-var requires a value"));
                }
                let var_str = &args[i];
                if let Some(eq_pos) = var_str.find('=') {
                    let key = var_str[..eq_pos].to_string();
                    let value = var_str[eq_pos + 1..].to_string();
                    opts.config_vars.insert(key, value);
                } else {
                    return Err(PyValueError::new_err("--config-var must be in KEY=VALUE format"));
                }
            }
            arg if arg.starts_with("-") => {
                return Err(PyValueError::new_err(format!("Unknown argument: {}", arg)));
            }
            _ => {
                // Positional argument - treat as config path if not set
                if opts.config_path.is_none() {
                    opts.config_path = Some(args[i].clone());
                }
            }
        }
        i += 1;
    }
    
    Ok(opts)
}

#[pyfunction]
pub fn validate_config_file(config_path: &str, options: Option<VectorCliOptions>) -> PyResult<bool> {
    let opts = options.unwrap_or_else(|| VectorCliOptions::new(
        None, None, false, false, 0, "text".to_string(),
        None, false, None, None, false, None
    ));
    
    match create_config_from_file(config_path, &opts) {
        Ok(_) => Ok(true),
        Err(e) => {
            // Return false for validation failure, but don't raise exception
            eprintln!("Config validation failed: {}", e);
            Ok(false)
        }
    }
}

#[pyfunction]
pub fn check_config_syntax(config_content: &str, options: Option<VectorCliOptions>) -> PyResult<bool> {
    let opts = options.unwrap_or_else(|| VectorCliOptions::new(
        None, None, false, false, 0, "text".to_string(),
        None, false, None, None, false, None
    ));
    
    match create_config_from_string(config_content, &opts) {
        Ok(_) => Ok(true),
        Err(e) => {
            eprintln!("Config syntax check failed: {}", e);
            Ok(false)
        }
    }
}