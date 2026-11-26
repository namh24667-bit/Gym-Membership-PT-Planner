from datetime import date
from decimal import Decimal
import re
import unittest
from unittest.mock import patch

from app import create_app, db, membership


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.fields = dict(full_name='  Nguyễn Demo  ', ssn='990000000777', date_of_birth='2000-01-01',
                           gender='OTHER', email=' DEMO@example.invalid ', phone='0900000777',
                           emergency_contact_phone='0980000777', password='Synthetic-Demo-2026',
                           confirm_password='Synthetic-Demo-2026')

    def test_normalization_and_synthetic_age(self):
        values = membership.validate_registration(self.fields, today=date(2026, 11, 24))
        self.assertEqual(values['email'], 'demo@example.invalid')
        self.assertEqual(values['full_name'], 'Nguyễn Demo')
        self.assertEqual(values['date_of_birth'], date(2000, 1, 1))

    def test_rejects_age_phone_mismatch_and_unlisted_role(self):
        for changes in ({'date_of_birth': '2011-11-25'}, {'date_of_birth': '2026-02-30'},
                        {'confirm_password': 'different'}, {'role': 'management'},
                        {'emergency_contact_phone': self.fields['phone']}, {'email': 'broken@.'},
                        {'full_name': '\u0000'}, {'ssn': ''}):
            with self.subTest(changes=changes), self.assertRaises(membership.InvalidForm):
                membership.validate_registration(dict(self.fields, **changes), today=date(2026, 11, 24))

    def test_money_precision_and_limits(self):
        self.assertEqual(membership.quote('120000.93'), Decimal('120000.93'))
        for amount in ('-1', 'NaN', '1e3', '1.001', '10000000000', ''):
            with self.subTest(amount=amount), self.assertRaises(membership.InvalidForm):
                membership.quote(amount)

    def test_public_registration_requires_csrf_and_never_passes_plaintext_to_sql(self):
        app = create_app(dict(TESTING=True, AUTH_ENABLED=True, SECRET_KEY='s' * 32,
                              LOCAL_QA=True, SQL_DATABASE=db.QA_DATABASE, LOCAL02_ENABLED=True))
        client = app.test_client()
        address = 'https://localhost'
        token = re.search(rb'name="csrf_token" value="([^"]+)"',
                          client.get('/register', base_url=address).data)[1].decode()
        with patch.object(db, 'workflow', return_value=(7,)) as write:
            self.assertEqual(client.post('/register', data=self.fields, base_url=address).status_code, 400)
            self.assertEqual(client.post('/register', data=dict(self.fields, csrf_token=token),
                                         base_url=address).status_code, 303)
        self.assertEqual(write.call_args.args[0], 'register_member')
        self.assertNotIn(self.fields['password'], write.call_args.args)
        self.assertTrue(write.call_args.args[-1].startswith('$argon2id$'))


class WorkflowAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(dict(TESTING=True, AUTH_ENABLED=True, SECRET_KEY='s' * 32,
                                   LOCAL_QA=True, SQL_DATABASE=db.QA_DATABASE, LOCAL02_ENABLED=True))
        self.client = self.app.test_client()
        self.address = 'https://localhost'
        with self.client.session_transaction(base_url=self.address) as session:
            session.update(auth_token='synthetic-session', csrf_token='synthetic-csrf')
        self.addCleanup(patch.stopall)
        patch('app.session_store.session_owner', return_value=42).start()
        self.actor = patch.object(db, 'get_principal', return_value=db.Principal(42, 'Demo', ('member',))).start()
        self.sql = patch.object(db, 'workflow').start()

    def test_member_cannot_submit_a_staff_payment(self):
        response = self.client.post('/staff/contracts/4/payment', base_url=self.address,
                                    data=dict(csrf_token='synthetic-csrf', amount='50.00', method='CASH', mode='now'))
        self.assertEqual(response.status_code, 403)
        self.sql.assert_not_called()

    def test_unowned_contract_lookup_uses_session_identity(self):
        self.sql.return_value = []
        response = self.client.get('/member/membership/4?person_id=1', base_url=self.address)
        self.assertEqual(response.status_code, 404)
        self.sql.assert_called_once_with('contracts', 42, False, 4, None, None, many=True)

    def test_staff_payment_uses_authenticated_actor_and_decimal(self):
        self.actor.return_value = db.Principal(42, 'Staff', ('staff',))
        self.sql.return_value = (9,)
        data = dict(csrf_token='synthetic-csrf', amount='50.25', method='BANK_TRANSFER', mode='later')
        response = self.client.post('/staff/contracts/4/payment', base_url=self.address, data=data)
        self.assertEqual(response.status_code, 303)
        self.sql.assert_called_once_with('collect_payment', 42, 4, Decimal('50.25'), 'BANK_TRANSFER', False)
