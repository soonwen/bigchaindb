"""This module provides the blueprint for some basic API endpoints.

For more information please refer to the documentation on ReadTheDocs:
 - https://docs.bigchaindb.com/projects/server/en/latest/drivers-clients/
   http-client-server-api.html
"""
import re

from flask import current_app, request
from flask_restful import Resource, reqparse


from bigchaindb.common.exceptions import (
    AmountError,
    DoubleSpend,
    InvalidHash,
    InvalidSignature,
    SchemaValidationError,
    OperationError,
    TransactionDoesNotExist,
    TransactionOwnerError,
    TransactionNotInValidBlock,
    ValidationError,
)

import bigchaindb
from bigchaindb.models import Transaction
from bigchaindb.web.views.base import make_error


class TransactionApi(Resource):
    def get(self, tx_id):
        """API endpoint to get details about a transaction.

        Args:
            tx_id (str): the id of the transaction.

        Return:
            A JSON string containing the data about the transaction.
        """
        pool = current_app.config['bigchain_pool']

        with pool() as bigchain:
            tx = bigchain.get_transaction(tx_id)

        if not tx:
            return make_error(404)

        return tx.to_dict()


class TransactionStatusApi(Resource):
    def get(self, tx_id):
        """API endpoint to get details about the status of a transaction.

        Args:
            tx_id (str): the id of the transaction.

        Return:
            A ``dict`` in the format ``{'status': <status>}``, where
            ``<status>`` is one of "valid", "invalid", "undecided", "backlog".
        """

        pool = current_app.config['bigchain_pool']

        with pool() as bigchain:
            status = bigchain.get_status(tx_id)

        if not status:
            return make_error(404)

        return {'status': status}


def valid_txid(txid):
    if re.match('^[a-fA-F0-9]{64,64}$', txid):
        return txid.lower()
    raise ValueError("Not a valid hash")


def valid_bool(val):
    if val.lower() == 'true':
        return True
    if val.lower() == 'false':
        return False
    raise ValueError('Boolean value must be "true" or "false"')


def valid_ed25519(key):
    if re.match('^[1-9a-zA-Z^OIl]{43,44}$', key):
        return key.lower()
    raise ValueError("Not a valid hash")


def valid_operation(op):
    if op.upper == 'CREATE':
        return 'CREATE'
    if op.upper == 'TRANSFER':
        return 'TRANSFER'
    raise ValueError('Operation must be "CREATE" or "TRANSFER')


class TransactionListApi(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('operation', type=valid_operation)
        parser.add_argument('unspent', type=valid_bool)
        parser.add_argument('public_key', type=valid_ed25519, action="append")
        parser.add_argument('asset_id', type=valid_txid)
        args = parser.parse_args()
        return args

    def post(self):
        """API endpoint to push transactions to the Federation.

        Return:
            A ``dict`` containing the data about the transaction.
        """
        pool = current_app.config['bigchain_pool']
        monitor = current_app.config['monitor']

        # `force` will try to format the body of the POST request even if the
        # `content-type` header is not set to `application/json`
        tx = request.get_json(force=True)

        try:
            tx_obj = Transaction.from_dict(tx)
        except SchemaValidationError as e:
            return make_error(
                400,
                message='Invalid transaction schema: {}'.format(
                    e.__cause__.message)
            )
        except (ValidationError, InvalidSignature) as e:
            return make_error(
                400,
                'Invalid transaction ({}): {}'.format(type(e).__name__, e)
            )

        with pool() as bigchain:
            try:
                bigchain.validate_transaction(tx_obj)
            except (ValueError,
                    OperationError,
                    TransactionDoesNotExist,
                    TransactionOwnerError,
                    DoubleSpend,
                    InvalidHash,
                    InvalidSignature,
                    TransactionNotInValidBlock,
                    AmountError) as e:
                return make_error(
                    400,
                    'Invalid transaction ({}): {}'.format(type(e).__name__, e)
                )
            else:
                rate = bigchaindb.config['statsd']['rate']
                with monitor.timer('write_transaction', rate=rate):
                    bigchain.write_transaction(tx_obj)

        return tx
