mod python_source;
mod vector_app;
mod vector_context;
mod vrl_checker;
mod vector_cli;

use crate::vector_app::VectorApp;
use crate::vector_context::VectorContext;
// use crate::vrl_checker::{check_vrl_syntax, check_vrl_batch, validate_vrl_transform, get_vrl_functions, explain_vrl_function, VrlResult};
use crate::vector_cli::{VectorCli, VectorCliOptions, vector_from_cli_args, parse_cli_args, validate_config_file, check_config_syntax};
use bytes::Bytes;
use pyo3::prelude::*;
use tokio::sync::{RwLock};
use vector::config::{load, Config, Format};

pub fn create_config(contents: &str) -> Config {
    let mut builder = Config::builder();
    builder
        .append(load(contents.as_bytes(), Format::Toml).unwrap())
        .unwrap();

    builder.build().unwrap()
}

#[pyclass(frozen)]
struct Vector {
    app: RwLock<Option<VectorApp>>, // app: Mutex<Option<JoinHandle<ExitStatus>>>,
                                    // runtime: Runtime,
                                    // context: ExtraContext,
                                    // tx: SignalTx,
                                    // metrics: &'static Controller,
}

#[pymethods]
impl Vector {
    #[new]
    fn new(config: &str) -> Self {
        let config = create_config(config);
        let context = VectorContext::global();
        let app = VectorApp::new(config, context);
        Self {
            app: RwLock::new(Some(app)),
        }
    }

    async fn start(&self) {
        let mut app_lock = self.app.write().await;
        let app = app_lock.take().unwrap();
        let started = app.start().await;
        app_lock.replace(started);
    }

    async fn stop(&self) {
        let mut app_lock = self.app.write().await;
        let app = app_lock.take().unwrap();
        let stopped = app.stop().await;
        app_lock.replace(stopped);
    }

    async fn send(&self, source: String, data: Vec<u8>) {
        let app_lock = self.app.read().await;
        if let Some(app) = app_lock.as_ref() {
            let sender = app.get_sender(&source).await;
            sender.send(Bytes::from(data)).await.unwrap();
        }
    }

    // fn get_metrics(&self) {
    //     let metrics = self.metrics.capture_metrics();
    //     for metric in metrics {
    //         println!("Name: {}, Value: {}", metric.name(), metric.value());
    //     }
    // }
}

#[pymodule]
fn pyvector(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Core Vector class
    m.add_class::<Vector>()?;
    
    // CLI-compatible Vector class
    m.add_class::<VectorCli>()?;
    m.add_class::<VectorCliOptions>()?;
    
    // VRL syntax validation - temporarily disabled
    // m.add_class::<VrlResult>()?;
    // m.add_function(wrap_pyfunction!(check_vrl_syntax, m)?)?;
    // m.add_function(wrap_pyfunction!(check_vrl_batch, m)?)?;
    // m.add_function(wrap_pyfunction!(validate_vrl_transform, m)?)?;
    // m.add_function(wrap_pyfunction!(get_vrl_functions, m)?)?;
    // m.add_function(wrap_pyfunction!(explain_vrl_function, m)?)?;
    
    // CLI argument parsing and config validation
    m.add_function(wrap_pyfunction!(vector_from_cli_args, m)?)?;
    m.add_function(wrap_pyfunction!(parse_cli_args, m)?)?;
    m.add_function(wrap_pyfunction!(validate_config_file, m)?)?;
    m.add_function(wrap_pyfunction!(check_config_syntax, m)?)?;
    
    Ok(())
}
