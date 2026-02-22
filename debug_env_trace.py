import os
from dotenv import load_dotenv

# Force reload
if 'DMARKET_PUBLIC_KEY' in os.environ:
    del os.environ['DMARKET_PUBLIC_KEY']
if 'DMARKET_SECRET_KEY' in os.environ:
    del os.environ['DMARKET_SECRET_KEY']

load_dotenv(r'D:\Dmarket_bot\.env')

pub = os.getenv("DMARKET_PUBLIC_KEY")
sec = os.getenv("DMARKET_SECRET_KEY")

print("--- DEBUG TRACE ---")
if pub:
    print(f"PUBLIC_KEY: Length={len(pub)}, Prefix={pub[:4]}, Suffix={pub[-4:]}, RawRepr={repr(pub)}")
else:
    print("PUBLIC_KEY: MISSING")

if sec:
    print(f"SECRET_KEY: Length={len(sec)}, Prefix={sec[:4]}, Suffix={sec[-4:]}, RawRepr={repr(sec)}")
else:
    print("SECRET_KEY: MISSING")
