from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Standard Ed25519 test vectors (RFC 8032)
# Using a known keypair for validation
# Private Key (32 bytes): 9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60
# Public Key (32 bytes): d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a
# Message: b""
# Signature: e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b

def test_ed25519_signing():
    """Test Ed25519 signing and verification with known vectors."""
    private_bytes = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    public_bytes = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    message = b""
    expected_signature = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")

    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)

    # Verify public key derivation
    derived_public = private_key.public_key()
    assert derived_public.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ) == public_bytes

    # Verify signing
    signature = private_key.sign(message)
    assert signature == expected_signature

    # Verify verification
    derived_public.verify(signature, message)
