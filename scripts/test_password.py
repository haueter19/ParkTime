#!/usr/bin/env python
"""Test password hashing to diagnose the issue."""

from passlib.context import CryptContext

# Same config as in auth.py
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)

test_password = "parking!"
print(f"Testing password: {test_password}")
print(f"Password length (chars): {len(test_password)}")
print(f"Password length (bytes): {len(test_password.encode('utf-8'))}")

try:
    hashed = pwd_context.hash(test_password)
    print(f"✓ Hash successful!")
    print(f"Hash: {hashed[:50]}...")
except Exception as e:
    print(f"✗ Hash failed: {e}")
    print(f"Error type: {type(e).__name__}")