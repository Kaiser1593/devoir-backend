from django.db.models import F
from django.urls import include, path
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

from .models import Categorie, MouvementStock, Produit
from .serializers import CategorieSerializer, MouvementSerializer, ProduitSerializer


class CategorieViewSet(viewsets.ModelViewSet):
    queryset = Categorie.objects.all()
    serializer_class = CategorieSerializer


class ProduitViewSet(viewsets.ModelViewSet):
    queryset = Produit.objects.select_related("categorie")
    serializer_class = ProduitSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(nom__icontains=q)
        return qs

    @action(detail=False, methods=["get"])
    def alertes(self, request):
        """Produits dont le stock est sous le seuil d'alerte."""
        qs = self.get_queryset().filter(quantite__lte=F("seuil_alerte"))
        return Response(ProduitSerializer(qs, many=True).data)


class MouvementViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                       mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Historique : création et lecture seulement."""
    queryset = MouvementStock.objects.all()
    serializer_class = MouvementSerializer


router = DefaultRouter()
router.register("categories", CategorieViewSet)
router.register("produits", ProduitViewSet)
router.register("mouvements", MouvementViewSet)

urlpatterns = [path("", include(router.urls))]
