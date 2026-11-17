from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Categorie, MouvementStock, Produit


def _vers_drf(exc):
    detail = exc.message_dict if hasattr(exc, "error_dict") else exc.messages
    return serializers.ValidationError(detail)


class CategorieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categorie
        fields = ["id", "nom", "description"]


class ProduitSerializer(serializers.ModelSerializer):
    categorie_nom = serializers.CharField(source="categorie.nom", read_only=True)
    en_alerte = serializers.BooleanField(read_only=True)

    class Meta:
        model = Produit
        fields = ["id", "reference", "nom", "categorie", "categorie_nom",
                  "prix_unitaire", "quantite", "seuil_alerte", "en_alerte"]
        read_only_fields = ["quantite"]


class MouvementSerializer(serializers.ModelSerializer):
    class Meta:
        model = MouvementStock
        fields = ["id", "produit", "type", "quantite", "date", "commentaire"]
        read_only_fields = ["date"]

    def create(self, validated_data):
        # save() applique les règles métier (stock négatif interdit) sous verrou.
        try:
            mvt = MouvementStock(**validated_data)
            mvt.save()
        except DjangoValidationError as exc:
            raise _vers_drf(exc)
        return mvt
