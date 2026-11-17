from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Adherent, Auteur, Emprunt, Livre
from .serializers import AdherentSerializer, AuteurSerializer, EmpruntSerializer, LivreSerializer


class SuppressionProtegeeMixin:
    """Suppression d'un objet référencé -> 409 Conflict au lieu d'une erreur 500."""

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {'detail': 'Suppression impossible : cet élément est référencé ailleurs.'},
                status=status.HTTP_409_CONFLICT,
            )


class AuteurViewSet(SuppressionProtegeeMixin, viewsets.ModelViewSet):
    queryset = Auteur.objects.all()
    serializer_class = AuteurSerializer


class LivreViewSet(SuppressionProtegeeMixin, viewsets.ModelViewSet):
    """GET /api/livres/?search=hugo&disponible=1"""
    serializer_class = LivreSerializer

    def get_queryset(self):
        qs = Livre.objects.avec_disponibilite().select_related('auteur')
        qs = qs.rechercher(self.request.query_params.get('search'))
        if self.request.query_params.get('disponible') in ('1', 'true'):
            qs = qs.filter(disponibles_count__gt=0)
        return qs.order_by('titre')


class AdherentViewSet(SuppressionProtegeeMixin, viewsets.ModelViewSet):
    queryset = Adherent.objects.all()
    serializer_class = AdherentSerializer


class EmpruntViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                     mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Emprunts : liste, détail, création et retour (POST /api/emprunts/<id>/retour/)."""
    serializer_class = EmpruntSerializer

    def get_queryset(self):
        qs = Emprunt.objects.select_related('livre', 'adherent')
        statut = self.request.query_params.get('statut')
        if statut == 'en_cours':
            qs = qs.filter(date_retour__isnull=True)
        elif statut == 'en_retard':
            qs = qs.filter(date_retour__isnull=True, date_retour_prevue__lt=timezone.localdate())
        elif statut == 'rendus':
            qs = qs.filter(date_retour__isnull=False)
        return qs

    @action(detail=True, methods=['post'])
    def retour(self, request, pk=None):
        emprunt = self.get_object()
        try:
            emprunt.retourner()
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(emprunt).data)
