from django.conf.urls import include, url
from django.contrib import admin
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
	url(r'^app/', include('dicomviewerapp.urls')),
    url(r'^admin/', admin.site.urls),
]
