from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register('auteurs', api_views.AuteurViewSet, basename='api-auteur')
router.register('livres', api_views.LivreViewSet, basename='api-livre')
router.register('adherents', api_views.AdherentViewSet, basename='api-adherent')
router.register('emprunts', api_views.EmpruntViewSet, basename='api-emprunt')

urlpatterns = [path('', include(router.urls))]
