use pyo3::prelude::*;
use ed25519_dalek::{SigningKey, Signer};
use hex;

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
    // 1. Decode Secret Key
    let secret = match hex::decode(&secret_key_hex) {
        Ok(s) => s,
        Err(_) => return Err(pyo3::exceptions::PyValueError::new_err("Invalid secret key hex")),
    };

    // Ed25519-dalek expects 32-byte secret key (first 32 bytes of 64-char hex)
    if secret.len() < 32 {
        return Err(pyo3::exceptions::PyValueError::new_err("Secret key too short"));
    }
    
    let mut key_bytes = [0u8; 32];
    key_bytes.copy_from_slice(&secret[..32]);
    let signing_key = SigningKey::from_bytes(&key_bytes);

    // 2. Build Message
    let message = format!("{}{}{}{}", method.to_uppercase(), api_path, body, timestamp);
    
    // 3. Sign
    let signature = signing_key.sign(message.as_bytes());
    
    // 4. Hex Encode
    Ok(hex::encode(signature.to_bytes()))
}

#[pymodule]
fn rust_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(generate_signature_rs, m)?)?;
    Ok(())
}
