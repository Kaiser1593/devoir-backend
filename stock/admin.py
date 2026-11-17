from django.contrib import admin

from .models import Categorie, MouvementStock, Produit

admin.site.register(Categorie)


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ("reference", "nom", "categorie", "quantite", "seuil_alerte")
    search_fields = ("reference", "nom")
    readonly_fields = ("quantite",)


@admin.register(MouvementStock)
class MouvementAdmin(admin.ModelAdmin):
    list_display = ("date", "produit", "type", "quantite")
    list_filter = ("type",)
