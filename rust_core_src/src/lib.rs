use pyo3::prelude::*;
use ed25519_dalek::{SigningKey, Signer};
use hex;

/// DMarket v2 Signature Generator (Rust Optimized)
/// Formula: (Method) + (Path+Query) + (Body) + (Timestamp)
///
/// Uses raw 32-byte seed directly (no SHA-512 hashing or RFC 8032 clamping).
/// This matches the correct implementation in src/rust_core/src/lib.rs.
#[pyfunction]
fn generate_signature_rs(
    method: String,
    api_path: String,
    body: String,
    timestamp: String,
    secret_key_hex: String,
) -> PyResult<String> {
    let secret = match hex::decode(&secret_key_hex) {
        Ok(s) => s,
        Err(_) => return Err(pyo3::exceptions::PyValueError::new_err("Invalid secret key hex")),
    };

    if secret.len() < 32 {
        return Err(pyo3::exceptions::PyValueError::new_err("Secret key too short"));
    }

    // Use raw 32-byte seed directly — no SHA-512 hashing or RFC 8032 clamping
    let mut key_bytes = [0u8; 32];
    key_bytes.copy_from_slice(&secret[..32]);
    let signing_key = SigningKey::from_bytes(&key_bytes);

    let message = format!("{}{}{}{}", method.to_uppercase(), api_path, body, timestamp);

    let signature = signing_key.sign(message.as_bytes());

    Ok(hex::encode(signature.to_bytes()))
}

#[pymodule]
fn rust_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(generate_signature_rs, m)?)?;
    Ok(())
}
