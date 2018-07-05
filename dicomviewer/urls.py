from django.conf.urls import include, url
from django.contrib import admin
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import static as staticurl
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf import settings

urlpatterns = [
	url(r'^app/', include('dicomviewerapp.urls')),
    url(r'^admin/', admin.site.urls),
]
urlpatterns += staticfiles_urlpatterns()
urlpatterns += staticurl(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
