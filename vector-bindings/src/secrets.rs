//! Event secrets for the bundled VRL engine.
//!
//! Vector attaches a secret store to every event and exposes it to VRL through
//! `get_secret`, `set_secret` and `remove_secret`. The standalone `vrl` crate
//! ships the `SecretTarget` machinery but not the three functions, so they are
//! implemented here against the same surface Vector uses.
//!
//! Semantics match Vector 0.58.0, verified against `vector vrl`: all three are
//! infallible, `get_secret` returns `null` for a key that is not set, and
//! `set_secret`/`remove_secret` return `null`.
//!
//! `EventTarget` replaces vrl's own `TargetValue` as the runtime target. It is
//! needed because vrl's `Secrets` container exposes `get`/`insert`/`remove` but
//! no way to enumerate what it holds, and the Python API has to hand back every
//! secret a program set.

use std::collections::BTreeMap;

use vrl::compiler::prelude::*;
use vrl::compiler::{SecretTarget, Target};
use vrl::path::{OwnedTargetPath, PathPrefix};

/// One event's mutable state for the duration of a VRL program.
///
/// Mirrors vrl's `TargetValue`, except that `secrets` is a plain map this crate
/// owns and can read back.
pub(crate) struct EventTarget {
    pub(crate) value: Value,
    pub(crate) metadata: Value,
    pub(crate) secrets: BTreeMap<String, String>,
}

impl EventTarget {
    /// A target holding `value`, empty metadata and the given initial secrets.
    pub(crate) fn new(value: Value, secrets: BTreeMap<String, String>) -> Self {
        EventTarget {
            value,
            metadata: Value::Object(ObjectMap::new()),
            secrets,
        }
    }
}

/// `Target` requires `Debug`, and a derived one would print secret values into
/// any VRL diagnostic that formats the target. Redact them the way vrl's own
/// `Secrets` type does.
impl std::fmt::Debug for EventTarget {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("EventTarget")
            .field("value", &self.value)
            .field("metadata", &self.metadata)
            .field("secrets", &RedactedKeys(&self.secrets))
            .finish()
    }
}

struct RedactedKeys<'a>(&'a BTreeMap<String, String>);

impl std::fmt::Debug for RedactedKeys<'_> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut map = f.debug_map();
        for key in self.0.keys() {
            map.entry(key, &"<redacted secret>");
        }
        map.finish()
    }
}

impl Target for EventTarget {
    fn target_insert(&mut self, target_path: &OwnedTargetPath, value: Value) -> Result<(), String> {
        match target_path.prefix {
            PathPrefix::Event => self.value.insert(&target_path.path, value),
            PathPrefix::Metadata => self.metadata.insert(&target_path.path, value),
        };
        Ok(())
    }

    fn target_get(&self, target_path: &OwnedTargetPath) -> Result<Option<&Value>, String> {
        Ok(match target_path.prefix {
            PathPrefix::Event => self.value.get(&target_path.path),
            PathPrefix::Metadata => self.metadata.get(&target_path.path),
        })
    }

    fn target_get_mut(
        &mut self,
        target_path: &OwnedTargetPath,
    ) -> Result<Option<&mut Value>, String> {
        Ok(match target_path.prefix {
            PathPrefix::Event => self.value.get_mut(&target_path.path),
            PathPrefix::Metadata => self.metadata.get_mut(&target_path.path),
        })
    }

    fn target_remove(
        &mut self,
        target_path: &OwnedTargetPath,
        compact: bool,
    ) -> Result<Option<Value>, String> {
        Ok(match target_path.prefix {
            PathPrefix::Event => self.value.remove(&target_path.path, compact),
            PathPrefix::Metadata => self.metadata.remove(&target_path.path, compact),
        })
    }
}

impl SecretTarget for EventTarget {
    fn get_secret(&self, key: &str) -> Option<&str> {
        self.secrets.get(key).map(String::as_str)
    }

    fn insert_secret(&mut self, key: &str, value: &str) {
        self.secrets.insert(key.to_string(), value.to_string());
    }

    fn remove_secret(&mut self, key: &str) {
        self.secrets.remove(key);
    }
}

/// The three secret functions, ready to append to `vrl::stdlib::all()`.
pub(crate) fn functions() -> Vec<Box<dyn Function>> {
    vec![
        Box::new(GetSecret),
        Box::new(SetSecret),
        Box::new(RemoveSecret),
    ]
}

// -----------------------------------------------------------------------------
// VRL functions
// -----------------------------------------------------------------------------

#[derive(Clone, Copy, Debug)]
pub(crate) struct GetSecret;

impl Function for GetSecret {
    fn identifier(&self) -> &'static str {
        "get_secret"
    }

    fn summary(&self) -> &'static str {
        "read a secret attached to the event"
    }

    fn usage(&self) -> &'static str {
        "Returns the value of the named secret, or null when the event carries\n\
         no secret under that key. Initial secrets are supplied from Python via\n\
         the `secrets` argument to `execute_vrl`."
    }

    fn category(&self) -> &'static str {
        "Event"
    }

    fn return_kind(&self) -> u16 {
        kind::BYTES | kind::NULL
    }

    fn parameters(&self) -> &'static [Parameter] {
        const PARAMETERS: &[Parameter] = &[Parameter::required(
            "key",
            kind::BYTES,
            "The name of the secret.",
        )];
        PARAMETERS
    }

    fn examples(&self) -> &'static [Example] {
        &[Example {
            title: "Read a secret that is not set",
            source: r#"get_secret("i_dont_exist")"#,
            input: None,
            result: Ok("null"),
            file: file!(),
            line: line!(),
            deterministic: true,
            skip: true,
        }]
    }

    fn compile(
        &self,
        _state: &TypeState,
        _ctx: &mut FunctionCompileContext,
        arguments: ArgumentList,
    ) -> Compiled {
        let key = arguments.required("key");
        Ok(GetSecretFn { key }.as_expr())
    }
}

#[derive(Debug, Clone)]
struct GetSecretFn {
    key: Box<dyn Expression>,
}

impl FunctionExpression for GetSecretFn {
    fn resolve(&self, ctx: &mut Context) -> Resolved {
        let key = self.key.resolve(ctx)?;
        let key = key.try_bytes_utf8_lossy()?.into_owned();
        Ok(match ctx.target().get_secret(&key) {
            Some(secret) => Value::from(secret),
            None => Value::Null,
        })
    }

    fn type_def(&self, _: &TypeState) -> TypeDef {
        TypeDef::bytes().add_null().infallible()
    }
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct SetSecret;

impl Function for SetSecret {
    fn identifier(&self) -> &'static str {
        "set_secret"
    }

    fn summary(&self) -> &'static str {
        "attach a secret to the event"
    }

    fn usage(&self) -> &'static str {
        "Sets the named secret on the event, replacing any value already stored\n\
         under that key. Read the result back from Python with\n\
         `execute_vrl_with_secrets`."
    }

    fn category(&self) -> &'static str {
        "Event"
    }

    fn return_kind(&self) -> u16 {
        kind::NULL
    }

    fn parameters(&self) -> &'static [Parameter] {
        const PARAMETERS: &[Parameter] = &[
            Parameter::required("key", kind::BYTES, "The name of the secret."),
            Parameter::required("secret", kind::BYTES, "The secret value."),
        ];
        PARAMETERS
    }

    fn examples(&self) -> &'static [Example] {
        &[Example {
            title: "Set a secret",
            source: r#"set_secret("datadog_api_key", "secret-value")"#,
            input: None,
            result: Ok("null"),
            file: file!(),
            line: line!(),
            deterministic: true,
            skip: true,
        }]
    }

    fn compile(
        &self,
        _state: &TypeState,
        _ctx: &mut FunctionCompileContext,
        arguments: ArgumentList,
    ) -> Compiled {
        let key = arguments.required("key");
        let secret = arguments.required("secret");
        Ok(SetSecretFn { key, secret }.as_expr())
    }
}

#[derive(Debug, Clone)]
struct SetSecretFn {
    key: Box<dyn Expression>,
    secret: Box<dyn Expression>,
}

impl FunctionExpression for SetSecretFn {
    fn resolve(&self, ctx: &mut Context) -> Resolved {
        let key = self.key.resolve(ctx)?;
        let key = key.try_bytes_utf8_lossy()?.into_owned();
        let secret = self.secret.resolve(ctx)?;
        let secret = secret.try_bytes_utf8_lossy()?.into_owned();
        ctx.target_mut().insert_secret(&key, &secret);
        Ok(Value::Null)
    }

    fn type_def(&self, _: &TypeState) -> TypeDef {
        TypeDef::null().infallible().impure()
    }
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct RemoveSecret;

impl Function for RemoveSecret {
    fn identifier(&self) -> &'static str {
        "remove_secret"
    }

    fn summary(&self) -> &'static str {
        "drop a secret from the event"
    }

    fn usage(&self) -> &'static str {
        "Removes the named secret from the event. Removing a key that is not\n\
         set is not an error."
    }

    fn category(&self) -> &'static str {
        "Event"
    }

    fn return_kind(&self) -> u16 {
        kind::NULL
    }

    fn parameters(&self) -> &'static [Parameter] {
        const PARAMETERS: &[Parameter] = &[Parameter::required(
            "key",
            kind::BYTES,
            "The name of the secret to remove.",
        )];
        PARAMETERS
    }

    fn examples(&self) -> &'static [Example] {
        &[Example {
            title: "Remove a secret",
            source: r#"remove_secret("datadog_api_key")"#,
            input: None,
            result: Ok("null"),
            file: file!(),
            line: line!(),
            deterministic: true,
            skip: true,
        }]
    }

    fn compile(
        &self,
        _state: &TypeState,
        _ctx: &mut FunctionCompileContext,
        arguments: ArgumentList,
    ) -> Compiled {
        let key = arguments.required("key");
        Ok(RemoveSecretFn { key }.as_expr())
    }
}

#[derive(Debug, Clone)]
struct RemoveSecretFn {
    key: Box<dyn Expression>,
}

impl FunctionExpression for RemoveSecretFn {
    fn resolve(&self, ctx: &mut Context) -> Resolved {
        let key = self.key.resolve(ctx)?;
        let key = key.try_bytes_utf8_lossy()?.into_owned();
        ctx.target_mut().remove_secret(&key);
        Ok(Value::Null)
    }

    fn type_def(&self, _: &TypeState) -> TypeDef {
        TypeDef::null().infallible().impure()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{compile_vrl_program, execute_vrl_on_event, vrl_value_to_json};

    /// Run `vrl` over a seed event with `secrets` preloaded, returning the
    /// event and the secrets the program left behind.
    fn run(
        vrl: &str,
        secrets: &[(&str, &str)],
    ) -> Result<(serde_json::Value, BTreeMap<String, String>), String> {
        let program = compile_vrl_program(vrl)?;
        let initial = secrets
            .iter()
            .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
            .collect();
        let outcome = execute_vrl_on_event(&program, r#"{"message":"seed"}"#, initial);
        Ok((vrl_value_to_json(outcome.result?), outcome.secrets))
    }

    #[test]
    fn get_secret_returns_a_preloaded_secret() {
        let (event, _) = run(r#".key = get_secret("api_key")"#, &[("api_key", "abc123")])
            .expect("execution succeeds");
        assert_eq!(event.get("key").and_then(|v| v.as_str()), Some("abc123"));
    }

    #[test]
    fn get_secret_returns_null_when_absent() {
        // Vector 0.58.0's get_secret is infallible and yields null for a key
        // that is not set - verified against `vector vrl 'get_secret("nope")'`.
        let (event, _) =
            run(r#".key = get_secret("nope")"#, &[]).expect("a missing secret is not an error");
        assert!(
            event.get("key").is_some_and(serde_json::Value::is_null),
            "expected null, got {event}"
        );
    }

    #[test]
    fn get_secret_is_infallible() {
        // The `!` form must NOT be required, which is what makes the function
        // usable without error handling.
        assert!(compile_vrl_program(r#".key = get_secret("k")"#).is_ok());
    }

    #[test]
    fn set_secret_is_visible_to_get_secret_and_read_back() {
        let (event, secrets) = run(
            r#"
            set_secret("token", "s3cr3t")
            .echo = get_secret("token")
            "#,
            &[],
        )
        .expect("execution succeeds");
        assert_eq!(event.get("echo").and_then(|v| v.as_str()), Some("s3cr3t"));
        assert_eq!(secrets.get("token").map(String::as_str), Some("s3cr3t"));
    }

    #[test]
    fn set_secret_replaces_an_existing_value() {
        let (_, secrets) = run(r#"set_secret("k", "new")"#, &[("k", "old")]).expect("runs");
        assert_eq!(secrets.get("k").map(String::as_str), Some("new"));
    }

    #[test]
    fn remove_secret_drops_the_key() {
        let (event, secrets) = run(
            r#"
            remove_secret("k")
            .after = get_secret("k")
            "#,
            &[("k", "v")],
        )
        .expect("execution succeeds");
        assert!(event.get("after").is_some_and(serde_json::Value::is_null));
        assert!(!secrets.contains_key("k"));
    }

    #[test]
    fn remove_secret_of_an_absent_key_is_not_an_error() {
        let (_, secrets) = run(r#"remove_secret("nothing")"#, &[]).expect("runs");
        assert!(secrets.is_empty());
    }

    #[test]
    fn untouched_secrets_survive_the_program() {
        let (_, secrets) = run(r#".x = 1"#, &[("a", "1"), ("b", "2")]).expect("execution succeeds");
        assert_eq!(secrets.get("a").map(String::as_str), Some("1"));
        assert_eq!(secrets.get("b").map(String::as_str), Some("2"));
    }

    #[test]
    fn the_secret_key_may_be_computed_at_runtime() {
        let (event, _) = run(
            r#"
            name = "api" + "_key"
            .key = get_secret(name)
            "#,
            &[("api_key", "abc123")],
        )
        .expect("execution succeeds");
        assert_eq!(event.get("key").and_then(|v| v.as_str()), Some("abc123"));
    }

    #[test]
    fn a_non_string_secret_is_a_compile_error() {
        // Matches Vector, which rejects `set_secret("k", 5)` with E110.
        assert!(compile_vrl_program(r#"set_secret("k", 5)"#).is_err());
    }

    #[test]
    fn debug_redacts_secret_values() {
        let mut secrets = BTreeMap::new();
        secrets.insert("token".to_string(), "s3cr3t".to_string());
        let target = EventTarget::new(Value::Object(ObjectMap::new()), secrets);
        let rendered = format!("{target:?}");
        assert!(
            rendered.contains("token"),
            "keys are not secret: {rendered}"
        );
        assert!(
            !rendered.contains("s3cr3t"),
            "secret value leaked into Debug: {rendered}"
        );
    }
}
