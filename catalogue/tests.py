import json
import tempfile
import xml.etree.ElementTree as ET
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import MAX_EMPRUNTS_SIMULTANES, Adherent, Auteur, Emprunt, Livre
from .services import echanges


class BaseDonnees:
    @classmethod
    def setUpTestData(cls):
        cls.auteur = Auteur.objects.create(prenom='Victor', nom='Hugo')
        cls.livre = Livre.objects.create(titre='Les Misérables', isbn='9780000000011', auteur=cls.auteur, exemplaires=1)
        cls.adherent = Adherent.objects.create(prenom='Camille', nom='Durand', email='c@example.com')
        cls.autre = Adherent.objects.create(prenom='Samir', nom='Benali', email='s@example.com')


class ReglesMetierTests(BaseDonnees, TestCase):
    def test_emprunt_valide_reduit_la_disponibilite(self):
        Emprunt.objects.create(livre=self.livre, adherent=self.adherent)
        self.assertEqual(self.livre.disponibles, 0)

    def test_emprunt_refuse_si_livre_indisponible(self):
        Emprunt.objects.create(livre=self.livre, adherent=self.adherent)
        with self.assertRaises(ValidationError) as ctx:
            Emprunt.objects.create(livre=self.livre, adherent=self.autre)
        self.assertIn('livre', ctx.exception.message_dict)

    def test_emprunt_refuse_au_dela_du_plafond(self):
        for i in range(MAX_EMPRUNTS_SIMULTANES):
            livre = Livre.objects.create(titre=f'L{i}', isbn=f'97800000001{i:02d}', auteur=self.auteur)
            Emprunt.objects.create(livre=livre, adherent=self.adherent)
        with self.assertRaises(ValidationError) as ctx:
            Emprunt.objects.create(livre=self.livre, adherent=self.adherent)
        self.assertIn('adherent', ctx.exception.message_dict)

    def test_retour_libere_le_livre(self):
        e = Emprunt.objects.create(livre=self.livre, adherent=self.adherent)
        e.retourner()
        self.assertEqual(self.livre.disponibles, 1)
        Emprunt.objects.create(livre=self.livre, adherent=self.autre)  # de nouveau possible

    def test_double_retour_refuse(self):
        e = Emprunt.objects.create(livre=self.livre, adherent=self.adherent)
        e.retourner()
        with self.assertRaises(ValueError):
            e.retourner()

    def test_retour_prevu_avant_emprunt_refuse(self):
        e = Emprunt(livre=self.livre, adherent=self.adherent,
                    date_retour_prevue=timezone.localdate() - timedelta(days=1))
        with self.assertRaises(ValidationError):
            e.full_clean()

    def test_exemplaires_inferieurs_aux_prets_en_cours_refuse(self):
        livre = Livre.objects.create(titre='X', isbn='9780000000999', auteur=self.auteur, exemplaires=2)
        Emprunt.objects.create(livre=livre, adherent=self.adherent)
        Emprunt.objects.create(livre=livre, adherent=self.autre)
        livre.exemplaires = 1
        with self.assertRaises(ValidationError):
            livre.full_clean()


class VuesTests(BaseDonnees, TestCase):
    def test_pages_principales_repondent(self):
        for nom in ('accueil', 'livre-list', 'auteur-list', 'adherent-list', 'emprunt-list', 'import'):
            self.assertEqual(self.client.get(reverse(nom)).status_code, 200, nom)
        self.assertContains(self.client.get(reverse('livre-detail', args=[self.livre.pk])), 'Les Misérables')

    def test_recherche_filtre_la_liste(self):
        r = self.client.get(reverse('livre-list'), {'q': 'hugo'})
        self.assertContains(r, 'Les Misérables')
        r = self.client.get(reverse('livre-list'), {'q': 'zzz'})
        self.assertNotContains(r, 'Les Misérables')

    def test_creation_livre_invalide_affiche_les_erreurs(self):
        r = self.client.post(reverse('livre-create'), {'titre': '', 'isbn': 'abc', 'auteur': self.auteur.pk, 'exemplaires': 1})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "L&#x27;ISBN doit contenir")
        self.assertFalse(Livre.objects.filter(isbn='abc').exists())

    def test_creation_livre_valide_redirige(self):
        r = self.client.post(reverse('livre-create'), {'titre': 'Neuf', 'isbn': '9780000000500', 'auteur': self.auteur.pk, 'exemplaires': 2})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Livre.objects.filter(titre='Neuf').exists())

    def test_formulaire_emprunt_refuse_livre_indisponible(self):
        Emprunt.objects.create(livre=self.livre, adherent=self.adherent)
        r = self.client.post(reverse('emprunt-create'), {
            'livre': self.livre.pk, 'adherent': self.autre.pk,
            'date_emprunt': timezone.localdate().isoformat(),
            'date_retour_prevue': (timezone.localdate() + timedelta(days=7)).isoformat(),
        })
        self.assertContains(r, 'indisponible')
        self.assertEqual(Emprunt.objects.count(), 1)

    def test_suppression_auteur_protege(self):
        r = self.client.post(reverse('auteur-delete', args=[self.auteur.pk]), follow=True)
        self.assertContains(r, 'Suppression impossible')
        self.assertTrue(Auteur.objects.filter(pk=self.auteur.pk).exists())


class ApiTests(BaseDonnees, APITestCase):
    def test_liste_et_detail_livres(self):
        r = self.client.get('/api/livres/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['count'], 1)
        self.assertEqual(r.json()['results'][0]['disponibles'], 1)
        self.assertEqual(self.client.get(f'/api/livres/{self.livre.pk}/').status_code, 200)

    def test_detail_inexistant_404(self):
        self.assertEqual(self.client.get('/api/livres/9999/').status_code, 404)

    def test_recherche_api(self):
        self.assertEqual(self.client.get('/api/livres/', {'search': 'hugo'}).json()['count'], 1)
        self.assertEqual(self.client.get('/api/livres/', {'search': 'zzz'}).json()['count'], 0)

    def test_creation_livre_201_et_erreur_400(self):
        ok = self.client.post('/api/livres/', {'titre': 'N', 'isbn': '9780000000600', 'auteur': self.auteur.pk, 'exemplaires': 1}, format='json')
        self.assertEqual(ok.status_code, 201)
        doublon = self.client.post('/api/livres/', {'titre': 'N', 'isbn': '9780000000600', 'auteur': self.auteur.pk}, format='json')
        self.assertEqual(doublon.status_code, 400)
        self.assertIn('isbn', doublon.json())

    def test_modification_livre_patch(self):
        r = self.client.patch(f'/api/livres/{self.livre.pk}/', {'exemplaires': 4}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['exemplaires'], 4)

    def test_emprunt_api_applique_la_regle_metier(self):
        payload = {'livre': self.livre.pk, 'adherent': self.adherent.pk}
        self.assertEqual(self.client.post('/api/emprunts/', payload, format='json').status_code, 201)
        r = self.client.post('/api/emprunts/', {'livre': self.livre.pk, 'adherent': self.autre.pk}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('livre', r.json())

    def test_retour_api_et_conflit_si_deja_rendu(self):
        e = Emprunt.objects.create(livre=self.livre, adherent=self.adherent)
        r = self.client.post(f'/api/emprunts/{e.pk}/retour/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.json()['date_retour'])
        self.assertEqual(self.client.post(f'/api/emprunts/{e.pk}/retour/').status_code, 409)

    def test_suppression_protegee_409(self):
        self.assertEqual(self.client.delete(f'/api/auteurs/{self.auteur.pk}/').status_code, 409)


class JsonXmlTests(BaseDonnees, TestCase):
    def test_analyse_json_vers_objets_python(self):
        livres = echanges.analyser_json('{"livres": [{"isbn": "1234567890", "titre": "T", "auteur": {"prenom": "A", "nom": "B"}, "annee": "1999", "exemplaires": 2}]}')
        self.assertEqual(livres[0].auteur_nom, 'B')
        self.assertEqual(livres[0].annee, 1999)
        self.assertEqual(livres[0].exemplaires, 2)

    def test_analyse_xml_vers_objets_python(self):
        xml = '<bibliotheque><livre isbn="1234567890"><titre>T</titre><auteur><prenom>A</prenom><nom>B</nom></auteur><annee></annee></livre></bibliotheque>'
        livres = echanges.analyser_xml(xml)
        self.assertEqual(livres[0].titre, 'T')
        self.assertIsNone(livres[0].annee)

    def test_donnees_invalides_levent_une_erreur_claire(self):
        for contenu, fonction in (('pas du json', echanges.analyser_json),
                                  ('{"livres": [{"titre": "sans isbn"}]}', echanges.analyser_json),
                                  ('<a><b></a>', echanges.analyser_xml)):
            with self.assertRaises(echanges.DonneesInvalides):
                fonction(contenu)

    def test_import_signale_les_lignes_invalides_sans_bloquer_les_autres(self):
        donnees = [echanges.LivreDonnees('Bon', '9780000000700', 'A', 'B'),
                   echanges.LivreDonnees('Mauvais', 'xx', 'A', 'B')]
        rapport = echanges.importer_livres(donnees)
        self.assertEqual((rapport.crees, len(rapport.erreurs)), (1, 1))

    def test_export_json_et_xml_relisibles(self):
        livres = Livre.objects.select_related('auteur')
        self.assertEqual(json.loads(echanges.exporter_json(livres))['livres'][0]['isbn'], '9780000000011')
        racine = ET.fromstring(echanges.exporter_xml(livres))
        self.assertEqual(racine.find('livre').get('isbn'), '9780000000011')
        # aller-retour : ce qui est exporté peut être ré-importé
        self.assertEqual(echanges.analyser_xml(echanges.exporter_xml(livres))[0].titre, 'Les Misérables')

    def test_vues_export(self):
        r = self.client.get(reverse('export-json'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertEqual(self.client.get(reverse('export-xml'))['Content-Type'], 'application/xml; charset=utf-8')

    def test_lecture_fichier_local(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / 'x.json'
            chemin.write_text('{"livres": []}', encoding='utf-8')
            self.assertEqual(echanges.lire_fichier(chemin), [])
            with self.assertRaises(echanges.DonneesInvalides):
                echanges.lire_fichier(Path(d) / 'absent.json')
