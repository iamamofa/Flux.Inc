from Crypto.Protocol.SecretSharing import Shamir
from binascii import hexlify
from cryptography.fernet import Fernet
import base64


def generate_shares():
    # First generate a proper Fernet key
    fernet_key = Fernet.generate_key()

    # Decode to get raw 16-byte key
    raw_key = base64.urlsafe_b64decode(fernet_key)[:16]

    # Split into shares (2-of-2 scheme)
    shares = Shamir.split(2, 2, raw_key)

    # Convert to hex for easier handling
    hex_shares = [(x, hexlify(y).decode('utf-8')) for x, y in shares]

    print("Fernet key (for encryption):", fernet_key.decode())
    print("\nShare 1 (give to Admin 1):", hex_shares[0][1])
    print("Share 2 (give to Admin 2):", hex_shares[1][1])


if __name__ == '__main__':
    generate_shares()
