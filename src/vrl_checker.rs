use pyo3::prelude::*;
use pyo3::exceptions::{PyValueError, PySyntaxError};
use std::collections::HashMap;

#[pyclass]
#[derive(Clone)]
pub struct VrlResult {
    #[pyo3(get)]
    pub valid: bool,
    #[pyo3(get)]
    pub error: Option<String>,
    #[pyo3(get)]
    pub error_code: i32,
    #[pyo3(get)]
    pub line: Option<usize>,
    #[pyo3(get)]
    pub column: Option<usize>,
    #[pyo3(get)]
    pub message: String,
}

#[pymethods]
impl VrlResult {
    fn __str__(&self) -> String {
        if self.valid {
            "VRL syntax is valid".to_string()
        } else {
            match (&self.error, self.line, self.column) {
                (Some(err), Some(line), Some(col)) => {
                    format!("VRL syntax error at line {}, column {}: {}", line, col, err)
                }
                (Some(err), _, _) => format!("VRL syntax error: {}", err),
                _ => "VRL syntax error".to_string(),
            }
        }
    }
    
    fn __repr__(&self) -> String {
        format!(
            "VrlResult(valid={}, error_code={}, message='{}')",
            self.valid, self.error_code, self.message
        )
    }
}

#[pyfunction]
pub fn check_vrl_syntax(vrl_code: &str) -> PyResult<VrlResult> {
    // Fast VRL syntax validation using Vector's VRL parser
    match vrl::compiler::compile(vrl_code, &vrl::compiler::CompileConfig::default()) {
        Ok(_) => Ok(VrlResult {
            valid: true,
            error: None,
            error_code: 0,
            line: None,
            column: None,
            message: "VRL syntax is valid".to_string(),
        }),
        Err(diagnostics) => {
            // Extract first error from diagnostics
            let first_error = diagnostics.first();
            
            let (error_msg, line, column) = if let Some(diagnostic) = first_error {
                let msg = diagnostic.message().to_string();
                
                // Try to extract line/column information from the diagnostic
                let (line_num, col_num) = if let Some(span) = diagnostic.span() {
                    (Some(span.start().line), Some(span.start().column))
                } else {
                    (None, None)
                };
                
                (msg, line_num, col_num)
            } else {
                ("Unknown VRL syntax error".to_string(), None, None)
            };
            
            Ok(VrlResult {
                valid: false,
                error: Some(error_msg.clone()),
                error_code: 1,
                line,
                column,
                message: error_msg,
            })
        }
    }
}

#[pyfunction]
pub fn check_vrl_batch(vrl_scripts: HashMap<String, String>) -> PyResult<HashMap<String, VrlResult>> {
    let mut results = HashMap::new();
    
    for (name, vrl_code) in vrl_scripts {
        let result = check_vrl_syntax(&vrl_code)?;
        results.insert(name, result);
    }
    
    Ok(results)
}

#[pyfunction]
pub fn validate_vrl_transform(transform_config: &str) -> PyResult<VrlResult> {
    // Parse the transform config and extract VRL code
    let config: toml::Value = toml::from_str(transform_config)
        .map_err(|e| PyValueError::new_err(format!("Invalid TOML config: {}", e)))?;
    
    // Look for VRL source in various common places
    let vrl_code = if let Some(source) = config.get("source") {
        source.as_str().unwrap_or("")
    } else if let Some(transforms) = config.as_table() {
        // Look through transform configurations
        for (_, transform) in transforms {
            if let Some(source) = transform.get("source") {
                if let Some(vrl_str) = source.as_str() {
                    return check_vrl_syntax(vrl_str);
                }
            }
        }
        ""
    } else {
        return Err(PyValueError::new_err("No VRL source found in transform config"));
    };
    
    if vrl_code.is_empty() {
        return Err(PyValueError::new_err("No VRL source found in transform config"));
    }
    
    check_vrl_syntax(vrl_code)
}

#[pyfunction]
pub fn get_vrl_functions() -> PyResult<Vec<String>> {
    // Get list of available VRL functions
    let functions = vrl::stdlib::all();
    let function_names: Vec<String> = functions
        .iter()
        .map(|f| f.identifier().to_string())
        .collect();
    
    Ok(function_names)
}

#[pyfunction]  
pub fn explain_vrl_function(function_name: &str) -> PyResult<Option<String>> {
    // Get documentation for a specific VRL function
    let functions = vrl::stdlib::all();
    
    for function in functions {
        if function.identifier() == function_name {
            return Ok(Some(format!(
                "Function: {}\nDescription: {}\nExample: {}",
                function.identifier(),
                function.description(),
                function.examples().join("\n")
            )));
        }
    }
    
    Ok(None)
}