"""
URL configuration for ligand_service project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path("", include("django_prometheus.urls")),
    path("dashboard/api/sim/upload", views.upload_sim),
    path("dashboard/api/sim/delete", views.delete_sim),
    path("dashboard/api/sim/start", views.start_sim),
    path("dashboard/api/sim/rename", views.rename_sim),
    path("dashboard/api/sims-data", views.send_sims_data),
    path("dashboard/api/group/start", views.run_group_analysis),
    path("dashboard/api/group/delete", views.delete_group_analysis),
    path("dashboard/api/group/history", views.send_analyses_history),
    path("dashboard/", views.dashboard),
    path("show/<str:sim_id>", views.show),
    path("show/group/<str:group_id>", views.show_group),
    path("admin/", admin.site.urls),
    path("", views.redirect_to_dashboard),
    path("about/", views.render_about),
    path("download/<path:filepath>/", views.download_file, name="download_file"),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    # Include django_browser_reload URLs only in DEBUG mode
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
        path("rerun/<str:sim_id>", views.show),
        path("rerun/group/<str:group_id>", views.show_group),
    ]
