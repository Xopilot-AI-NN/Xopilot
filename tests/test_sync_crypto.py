import os
import unittest
from App.services.sync_crypto import make_keyring, unlock_keyring, seal, open_sealed

class CryptoTests(unittest.TestCase):
    def test_compress_encrypt_roundtrip_and_owner_binding(self):
        key=os.urandom(32);text=b'private text\n'*10000
        encrypted=seal(key,'owner','entity',text)
        self.assertLess(len(encrypted),len(text)//20)
        self.assertNotIn(b'private text',encrypted)
        self.assertEqual(open_sealed(key,'owner','entity',encrypted),text)
        for owner,entity in [('other','entity'),('owner','other')]:
            with self.assertRaises(ValueError):open_sealed(key,owner,entity,encrypted)
        changed=bytearray(encrypted);changed[-1]^=1
        with self.assertRaises(ValueError):open_sealed(key,'owner','entity',bytes(changed))

    def test_key_password_account_binding_and_bounded_decompression(self):
        key,envelope=make_keyring('owner','Synthetic sync password 2026!')
        self.assertEqual(unlock_keyring('owner','Synthetic sync password 2026!',envelope),key)
        for owner,password in [('other','Synthetic sync password 2026!'),('owner','wrong password')]:
            with self.assertRaises(ValueError):unlock_keyring(owner,password,envelope)
        encrypted=seal(key,'owner','entity',b'x'*4096)
        with self.assertRaises(ValueError):open_sealed(key,'owner','entity',encrypted,max_bytes=1024)
