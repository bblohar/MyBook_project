# mybook_project/urls.py
# Main URL configuration for the mybook_project.

from django.contrib import admin
from django.urls import path, include

# All drf_yasg related imports and schema_view definition are removed.
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.views.generic.base import RedirectView


urlpatterns = [
    path('', include('books.urls')),
    path('admin/', admin.site.urls),
    path('api/', include('books.urls')),


]
