from django.core.management.base import BaseCommand
from django.db import transaction

from stock.models import Categorie, MouvementStock, Produit

DONNEES = {
    "Informatique": [
        ("INF-001", "Clavier mécanique", "59.90", 5, 20),
        ("INF-002", "Souris sans fil", "24.50", 5, 3),
        ("INF-003", "Écran 24 pouces", "139.00", 3, 8),
    ],
    "Papeterie": [
        ("PAP-001", "Ramette A4 500 feuilles", "4.90", 20, 150),
        ("PAP-002", "Stylos bleus (boîte de 50)", "9.90", 10, 6),
    ],
    "Mobilier": [
        ("MOB-001", "Chaise de bureau", "89.00", 2, 12),
        ("MOB-002", "Bureau 140 cm", "199.00", 2, 2),
    ],
}


class Command(BaseCommand):
    help = "Charge un jeu de données de démonstration (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        if Produit.objects.exists():
            self.stdout.write("Des données existent déjà : rien à faire.")
            return
        for nom_cat, produits in DONNEES.items():
            cat = Categorie.objects.create(nom=nom_cat, description=f"Articles : {nom_cat.lower()}")
            for ref, nom, prix, seuil, stock_initial in produits:
                p = Produit.objects.create(reference=ref, nom=nom, categorie=cat,
                                           prix_unitaire=prix, seuil_alerte=seuil)
                MouvementStock(produit=p, type=MouvementStock.ENTREE,
                               quantite=stock_initial, commentaire="Stock initial").save()
        # Quelques sorties pour illustrer l'historique.
        for ref, qte in [("INF-001", 4), ("PAP-001", 30)]:
            MouvementStock(produit=Produit.objects.get(reference=ref), type=MouvementStock.SORTIE,
                           quantite=qte, commentaire="Livraison client").save()
        self.stdout.write(self.style.SUCCESS(
            f"{Categorie.objects.count()} catégories, {Produit.objects.count()} produits, "
            f"{MouvementStock.objects.count()} mouvements créés."))
