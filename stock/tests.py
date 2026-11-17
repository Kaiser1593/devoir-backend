from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Categorie, MouvementStock, Produit
from .xml_utils import importer_produits_xml, produits_vers_xml


def creer_produit(ref="P1", quantite=0, seuil=5):
    cat, _ = Categorie.objects.get_or_create(nom="Cat")
    p = Produit.objects.create(reference=ref, nom=f"Produit {ref}", categorie=cat,
                               prix_unitaire="10.00", seuil_alerte=seuil)
    if quantite:
        MouvementStock(produit=p, type="E", quantite=quantite).save()
        p.refresh_from_db()
    return p


class ModeleTests(TestCase):
    def test_entree_augmente_le_stock(self):
        p = creer_produit(quantite=10)
        self.assertEqual(p.quantite, 10)

    def test_sortie_diminue_le_stock(self):
        p = creer_produit(quantite=10)
        MouvementStock(produit=p, type="S", quantite=4).save()
        p.refresh_from_db()
        self.assertEqual(p.quantite, 6)

    def test_sortie_superieure_au_stock_refusee(self):
        p = creer_produit(quantite=3)
        with self.assertRaises(ValidationError):
            MouvementStock(produit=p, type="S", quantite=4).save()
        p.refresh_from_db()
        self.assertEqual(p.quantite, 3)
        self.assertEqual(p.mouvements.count(), 1)

    def test_quantite_nulle_refusee(self):
        p = creer_produit()
        with self.assertRaises(ValidationError):
            MouvementStock(produit=p, type="E", quantite=0).save()

    def test_alerte(self):
        self.assertTrue(creer_produit("A", quantite=5, seuil=5).en_alerte)
        self.assertFalse(creer_produit("B", quantite=6, seuil=5).en_alerte)


class VueTests(TestCase):
    def test_pages_accessibles(self):
        p = creer_produit(quantite=2)
        for nom, args in [("tableau_de_bord", []), ("produit_liste", []), ("categorie_liste", []),
                          ("mouvement_liste", []), ("produit_detail", [p.pk]),
                          ("mouvement_creer", []), ("produit_creer", [])]:
            self.assertEqual(self.client.get(reverse(nom, args=args)).status_code, 200, nom)

    def test_recherche_et_filtre_alerte(self):
        creer_produit("AAA", quantite=1)
        creer_produit("BBB", quantite=50)
        rep = self.client.get(reverse("produit_liste"), {"q": "AAA"})
        self.assertContains(rep, "Produit AAA")
        self.assertNotContains(rep, "Produit BBB")
        rep = self.client.get(reverse("produit_liste"), {"alerte": "1"})
        self.assertContains(rep, "Produit AAA")
        self.assertNotContains(rep, "Produit BBB")

    def test_sortie_trop_grande_affiche_erreur(self):
        p = creer_produit(quantite=2)
        rep = self.client.post(reverse("mouvement_creer"),
                               {"produit": p.pk, "type": "S", "quantite": 5})
        self.assertContains(rep, "Stock insuffisant")
        p.refresh_from_db()
        self.assertEqual(p.quantite, 2)

    def test_creation_mouvement_valide(self):
        p = creer_produit()
        rep = self.client.post(reverse("mouvement_creer"),
                               {"produit": p.pk, "type": "E", "quantite": 7})
        self.assertRedirects(rep, reverse("produit_detail", args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.quantite, 7)

    def test_categorie_utilisee_non_supprimable(self):
        p = creer_produit()
        self.client.post(reverse("categorie_supprimer", args=[p.categorie.pk]))
        self.assertTrue(Categorie.objects.filter(pk=p.categorie.pk).exists())


class ApiTests(APITestCase):
    def test_liste_produits_json(self):
        creer_produit(quantite=3)
        rep = self.client.get("/api/produits/")
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep.json()["results"][0]["quantite"], 3)

    def test_creation_produit_ignore_quantite(self):
        cat = Categorie.objects.create(nom="X")
        rep = self.client.post("/api/produits/", {
            "reference": "N1", "nom": "Nouveau", "categorie": cat.pk,
            "prix_unitaire": "5.00", "seuil_alerte": 2, "quantite": 999}, format="json")
        self.assertEqual(rep.status_code, 201)
        self.assertEqual(rep.json()["quantite"], 0)

    def test_mouvement_api_et_stock_negatif(self):
        p = creer_produit(quantite=2)
        ok = self.client.post("/api/mouvements/", {"produit": p.pk, "type": "S", "quantite": 2},
                              format="json")
        self.assertEqual(ok.status_code, 201)
        ko = self.client.post("/api/mouvements/", {"produit": p.pk, "type": "S", "quantite": 1},
                              format="json")
        self.assertEqual(ko.status_code, 400)

    def test_mouvement_non_modifiable(self):
        p = creer_produit(quantite=2)
        mvt = p.mouvements.first()
        self.assertEqual(self.client.delete(f"/api/mouvements/{mvt.pk}/").status_code, 405)

    def test_alertes(self):
        creer_produit("A", quantite=1)
        creer_produit("B", quantite=100)
        rep = self.client.get("/api/produits/alertes/")
        self.assertEqual([x["reference"] for x in rep.json()], ["A"])


class XmlTests(TestCase):
    def test_export_puis_import(self):
        creer_produit("X1", quantite=4)
        contenu = produits_vers_xml(Produit.objects.all())
        Produit.objects.all().delete()
        crees, maj, erreurs = importer_produits_xml(contenu)
        self.assertEqual((crees, maj, erreurs), (1, 0, []))
        self.assertEqual(Produit.objects.get(reference="X1").quantite, 0)

    def test_xml_invalide(self):
        _, _, erreurs = importer_produits_xml(b"<produits><oups>")
        self.assertTrue(erreurs)

    def test_produit_incomplet_signale(self):
        xml = b"<produits><produit reference='Z'><nom>Sans cat</nom></produit></produits>"
        crees, _, erreurs = importer_produits_xml(xml)
        self.assertEqual(crees, 0)
        self.assertEqual(len(erreurs), 1)

    def test_vue_export(self):
        creer_produit()
        rep = self.client.get(reverse("export_xml"))
        self.assertEqual(rep["Content-Type"], "application/xml")


class CommandeTests(TestCase):
    def test_charger_donnees_idempotent(self):
        call_command("charger_donnees", verbosity=0)
        n = Produit.objects.count()
        self.assertGreater(n, 0)
        self.assertTrue(Produit.objects.filter(quantite__gt=0).exists())
        call_command("charger_donnees", verbosity=0)
        self.assertEqual(Produit.objects.count(), n)
