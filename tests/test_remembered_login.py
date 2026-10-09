import ast
import datetime as dt
import hashlib
import hmac
import re
import secrets
import unittest
from pathlib import Path


class RememberedLoginTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((Path(__file__).parents[1] / 'app.py').read_text())
        names = {'session_row_id', 'remember_client', 'remembered_client', 'forget_client'}
        module = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
        self.rows = {}
        rows = self.rows
        backend = type('Backend', (), {'get': lambda _, k: rows.get(k),
            'put': lambda _, row: rows.update({row['id']: row}), 'delete': lambda _, k: rows.pop(k, None)})()
        self.time = dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc)
        self.ns = dict(dt=dt, hashlib=hashlib, hmac=hmac, re=re, secrets=secrets,
            B=backend, ss={}, now=lambda: self.time, uid=lambda: secrets.token_hex(4))
        exec(compile(module, 'app.py', 'exec'), self.ns)
        self.client = {'id': 'c_one', 'pin_hash': 'hashed_pin'}
        self.rows['c_one'] = self.client
        self.ns['remember_client'](self.client)
        self.token = self.ns['ss']['device_token']

    def test_restores_after_session_loss_without_storing_raw_token(self):
        self.ns['ss'].clear()
        self.assertEqual(self.ns['remembered_client'](self.token), self.client)
        self.assertNotIn(self.token, repr(self.rows))
        self.assertIsNone(self.ns['remembered_client'](secrets.token_urlsafe(32)))

    def test_expired_token_is_rejected(self):
        self.time += dt.timedelta(days=31)
        self.assertIsNone(self.ns['remembered_client'](self.token))

    def test_pin_reset_revokes_remembered_login(self):
        self.client['pin_hash'] = 'reset_pin'
        self.assertIsNone(self.ns['remembered_client'](self.token))

    def test_deleted_client_cannot_return(self):
        self.rows.pop('c_one')
        self.assertIsNone(self.ns['remembered_client'](self.token))

    def test_logout_revokes_token_and_clears_device(self):
        self.ns['forget_client']()
        self.assertIsNone(self.ns['remembered_client'](self.token))
        self.assertEqual(self.ns['ss']['device_command']['token'], '')
        self.assertIsNone(self.ns['ss']['client_id'])

    def test_malformed_tokens_are_rejected(self):
        for token in ('c_one', '', None, 'a' * 1000):
            self.assertIsNone(self.ns['remembered_client'](token))


if __name__ == '__main__':
    unittest.main()
