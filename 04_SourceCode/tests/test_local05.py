from unittest import TestCase
from unittest.mock import patch

import pyodbc
from flask import Response

from app import create_app, db


class RequestConnectionTests(TestCase):
    def test_verified_connection_is_shared_and_closed_after_request(self):
        app = create_app(dict(TESTING=True, LOCAL_QA=True, SQL_DATABASE=db.QA_DATABASE,
                              SQL_SERVER=db.QA_SERVER, SQL_WINDOWS_LOGIN=db.LOCAL_QA_LOGINS[0]))

        @app.get('/qa-request')
        def read_twice():
            db._fetch('SELECT ?', 4)
            db._fetch('SELECT ?', 8)
            return Response(status=204)

        with patch.object(pyodbc, 'connect') as connect:
            connection = connect.return_value
            cursor = connection.cursor.return_value
            cursor.execute.return_value.fetchone.side_effect = [
                (db.QA_DATABASE, db.LOCAL_QA_LOGINS[0], 1), ('MSI', 'SQLEXPRESS', 'guid', 'Shared memory'),
                (4,), (8,),
            ]
            self.assertEqual(app.test_client().get('/qa-request').status_code, 204)
            connect.assert_called_once()
            connection.close.assert_called_once()
            self.assertEqual(cursor.close.call_count, 2)
