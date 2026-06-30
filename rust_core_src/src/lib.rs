use pyo3::prelude::*;
use ed25519_dalek::{SigningKey, Signer};
use hex;
use sha2::{Sha512, Digest};

/// DMarket v2 Signature Generator (Rust Optimized)
/// Formula: (Method) + (Path+Query) + (Body) + (Timestamp)
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

    let hash = Sha512::digest(&secret[..32]);
    let mut expanded = [0u8; 32];
    expanded.copy_from_slice(&hash[..32]);
    expanded[0] &= 248;
    expanded[31] &= 127;
    expanded[31] |= 64;
    let signing_key = SigningKey::from_bytes(&expanded);

    let message = format!("{}{}{}{}", method.to_uppercase(), api_path, body, timestamp);

    let signature = signing_key.sign(message.as_bytes());

    Ok(hex::encode(signature.to_bytes()))
}

#[pymodule]
fn rust_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(generate_signature_rs, m)?)?;
    Ok(())
}
