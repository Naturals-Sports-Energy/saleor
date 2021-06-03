from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib.staticfiles.views import serve
from django.views.decorators.csrf import csrf_exempt

from .data_feeds.urls import urlpatterns as feed_urls
from .graphql.api import schema
from .graphql.views import GraphQLView
from .plugins.views import handle_plugin_webhook
from .product.views import digital_product
from .core import views

urlpatterns = [
    url(r"^graphql/", csrf_exempt(GraphQLView.as_view(schema=schema)), name="api"),
    url(r"confirm-mail/", views.confirm_mail),
    url(r"forgot-password/", views.forgot_password),
    url(r"sign-in-google/", views.sign_in_google),
    url(r"access-token/", views.access_token),
    url(r"qr-code/", views.qr_code),
    url(r"soap/", views.soap),
    url('', include('social_django.urls', namespace='social')),
    url(r"^feeds/", include((feed_urls, "data_feeds"), namespace="data_feeds")),
    url(
        r"^digital-download/(?P<token>[0-9A-Za-z_\-]+)/$",
        digital_product,
        name="digital-product",
    ),
    url(
        r"plugins/(?P<plugin_id>[.0-9A-Za-z_\-]+)/",
        handle_plugin_webhook,
        name="plugins",
    ),
]

if settings.DEBUG:
    import warnings
    from .core import views

    try:
        import debug_toolbar
    except ImportError:
        warnings.warn(
            "The debug toolbar was not installed. Ignore the error. \
            settings.py should already have warned the user about it."
        )
    else:
        urlpatterns += [url(r"^__debug__/", include(debug_toolbar.urls))]

    urlpatterns += static("/media/", document_root=settings.MEDIA_ROOT) + [
        url(r"^static/(?P<path>.*)$", serve),
        url(r"^", views.home, name="home"),
    ]
