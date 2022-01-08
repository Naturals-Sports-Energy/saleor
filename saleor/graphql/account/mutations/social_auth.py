import graphene
from functools import wraps
from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import ugettext as _

from promise import Promise, is_thenable
from django.dispatch import Signal
token_issued = Signal(providing_args=['request', 'user'])

from graphql_jwt.exceptions import JSONWebTokenError, PermissionDenied
from graphql_jwt.mixins import ResolveMixin, ObtainJSONWebTokenMixin
from graphql_jwt.decorators import setup_jwt_cookie
from graphql_jwt.settings import jwt_settings
from graphql_jwt.shortcuts import get_token
from graphql_jwt.refresh_token.shortcuts import refresh_token_lazy
from social_django.utils import load_strategy, load_backend
from social_django.compat import reverse


from ..types import User
from saleor.graphql.core.types import Error

def token_auth(f):
    @wraps(f)
    @setup_jwt_cookie
    def wrapper(cls, root, info, **kwargs):
        context = info.context
        context._jwt_token_auth = True

        def on_resolve(values):
            user, payload = values
            payload.token = get_token(user, context)

            if jwt_settings.JWT_LONG_RUNNING_REFRESH_TOKEN:
                payload.refresh_token = refresh_token_lazy(user)

            return payload

        token = kwargs.get('accessToken')
        backend = kwargs.get('backend')
        context.social_strategy = load_strategy(context)
        # backward compatibility in attribute name, only if not already
        # defined
        if not hasattr(context, 'strategy'):
            context.strategy = context.social_strategy
        uri = reverse('social:complete', args=(backend,))
        context.backend = load_backend(context.social_strategy, backend, uri)

        user = context.backend.do_auth(token)

        if user is None:
            raise JSONWebTokenError(
                _('Please, enter valid credentials'))

        if hasattr(context, 'user'):
            context.user = user

        result = f(cls, root, info, **kwargs)
        values = (user, result)

        token_issued.send(sender=cls, request=context, user=user)

        if is_thenable(result):
            return Promise.resolve(values).then(on_resolve)
        return on_resolve(values)
    return wrapper


class JSONWebTokenMutation(ObtainJSONWebTokenMixin, graphene.Mutation):
    class Meta:
        abstract = True

    @classmethod
    @token_auth
    def mutate(cls, root, info, **kwargs):
        return cls.resolve(root, info, **kwargs)


class CreateOAuthToken(ResolveMixin, JSONWebTokenMutation):
    errors = graphene.List(Error, required=True)
    user = graphene.Field(User)

    class Arguments:
        accessToken = graphene.String(description="Access token.", required=True)
        backend = graphene.String(description="Authenticate backend", required=True)

    @classmethod
    def mutate(cls, root, info, **kwargs):
        try:
            result = super().mutate(root, info, **kwargs)
        except JSONWebTokenError as e:
            return CreateOAuthToken(errors=[Error(message=str(e))])
        else:
            return result

    @classmethod
    def resolve(cls, root, info, **kwargs):
        return cls(user=info.context.user, errors=[])

class OAuthMutations(graphene.ObjectType):
    oauth_token_create = CreateOAuthToken.Field()