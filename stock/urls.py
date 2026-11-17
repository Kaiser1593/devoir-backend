from django.urls import path

from . import views

urlpatterns = [
    path("", views.tableau_de_bord, name="tableau_de_bord"),
    path("produits/", views.produit_liste, name="produit_liste"),
    path("produits/nouveau/", views.produit_creer, name="produit_creer"),
    path("produits/<int:pk>/", views.produit_detail, name="produit_detail"),
    path("produits/<int:pk>/modifier/", views.produit_modifier, name="produit_modifier"),
    path("produits/<int:pk>/supprimer/", views.produit_supprimer, name="produit_supprimer"),
    path("categories/", views.categorie_liste, name="categorie_liste"),
    path("categories/nouvelle/", views.categorie_creer, name="categorie_creer"),
    path("categories/<int:pk>/supprimer/", views.categorie_supprimer, name="categorie_supprimer"),
    path("mouvements/", views.mouvement_liste, name="mouvement_liste"),
    path("mouvements/nouveau/", views.mouvement_creer, name="mouvement_creer"),
    path("export/produits.xml", views.export_xml, name="export_xml"),
    path("import/produits/", views.import_xml, name="import_xml"),
]
