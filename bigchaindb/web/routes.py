""" API routes definition """
from flask_restful import Api
from bigchaindb.web.views import info, transactions as tx, unspents


def add_routes(app):
    """ Add the routes to an app """
    for (prefix, routes) in API_SECTIONS:
        api = Api(app, prefix=prefix)
        for ((pattern, resource, *args), kwargs) in routes:
            kwargs.setdefault('strict_slashes', False)
            api.add_resource(resource, pattern, *args, **kwargs)


def r(*args, **kwargs):
    return (args, kwargs)


ROUTES_API_V1 = [
    r('transactions/<string:tx_id>', tx.TransactionApi),
    r('transactions/<string:tx_id>/status', tx.TransactionStatusApi),
    r('transactions', tx.TransactionListApi),
    r('unspents/', unspents.UnspentListApi),
]


API_SECTIONS = [
    (None, [r('/', info.IndexApi)]),
    ('/api/v1/', ROUTES_API_V1),
]
