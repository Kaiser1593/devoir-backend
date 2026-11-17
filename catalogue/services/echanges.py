"""Lecture, analyse, import et export de données JSON / XML.

Les données analysées sont transformées en objets Python (dataclasses) avant
d'être utilisées ou enregistrées en base.
"""
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction

from catalogue.models import Adherent, Auteur, Livre


class DonneesInvalides(Exception):
    """Fichier illisible ou structure inattendue."""


@dataclass
class LivreDonnees:
    titre: str
    isbn: str
    auteur_prenom: str
    auteur_nom: str
    annee: int | None = None
    exemplaires: int = 1
    resume: str = ''


@dataclass
class AdherentDonnees:
    prenom: str
    nom: str
    email: str


@dataclass
class RapportImport:
    crees: int = 0
    mis_a_jour: int = 0
    erreurs: list[str] = field(default_factory=list)


def _entier_ou_none(valeur):
    if valeur in (None, ''):
        return None
    return int(valeur)


def _livre_depuis_dict(d):
    try:
        return LivreDonnees(
            titre=str(d['titre']).strip(),
            isbn=str(d['isbn']).strip(),
            auteur_prenom=str(d['auteur']['prenom']).strip(),
            auteur_nom=str(d['auteur']['nom']).strip(),
            annee=_entier_ou_none(d.get('annee')),
            exemplaires=int(d.get('exemplaires') or 1),
            resume=str(d.get('resume') or '').strip(),
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise DonneesInvalides(f'Livre invalide ({exc!r}) : {d!r}') from exc


def analyser_json(contenu):
    """Analyse un texte JSON -> liste de LivreDonnees. Accepte {"livres": [...]} ou [...]."""
    try:
        brut = json.loads(contenu)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DonneesInvalides(f'JSON illisible : {exc}') from exc
    liste = brut.get('livres') if isinstance(brut, dict) else brut
    if not isinstance(liste, list):
        raise DonneesInvalides('Structure attendue : {"livres": [...]}.')
    return [_livre_depuis_dict(d) for d in liste]


def analyser_xml(contenu):
    """Analyse un texte/bytes XML -> liste de LivreDonnees."""
    try:
        racine = ET.fromstring(contenu)
    except ET.ParseError as exc:
        raise DonneesInvalides(f'XML illisible : {exc}') from exc
    resultat = []
    for noeud in racine.findall('livre'):
        d = {
            'isbn': noeud.get('isbn'),
            'titre': noeud.findtext('titre'),
            'auteur': {
                'prenom': noeud.findtext('auteur/prenom'),
                'nom': noeud.findtext('auteur/nom'),
            },
            'annee': noeud.findtext('annee'),
            'exemplaires': noeud.findtext('exemplaires'),
            'resume': noeud.findtext('resume'),
        }
        if d['isbn'] is None or d['titre'] is None:
            raise DonneesInvalides(f'<livre> sans isbn ou sans <titre> : {ET.tostring(noeud, encoding="unicode")[:80]}')
        resultat.append(_livre_depuis_dict(d))
    return resultat


def lire_fichier(chemin):
    """Choisit le parseur selon l'extension (.json / .xml)."""
    chemin = Path(chemin)
    try:
        contenu = chemin.read_bytes()
    except OSError as exc:
        raise DonneesInvalides(f'Impossible de lire {chemin} : {exc}') from exc
    return analyser_contenu(chemin.name, contenu)


def analyser_contenu(nom_fichier, contenu):
    extension = Path(nom_fichier).suffix.lower()
    if extension == '.json':
        return analyser_json(contenu.decode('utf-8') if isinstance(contenu, bytes) else contenu)
    if extension == '.xml':
        return analyser_xml(contenu)
    raise DonneesInvalides(f'Extension non supportée : {extension or "(aucune)"}')


def lire_adherents_json(chemin):
    try:
        brut = json.loads(Path(chemin).read_text(encoding='utf-8'))
        return [AdherentDonnees(a['prenom'], a['nom'], a['email']) for a in brut['adherents']]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DonneesInvalides(f'Fichier adhérents invalide : {exc!r}') from exc


def importer_livres(donnees):
    """Enregistre les LivreDonnees (création ou mise à jour par ISBN). Une ligne invalide
    n'empêche pas les autres : elle est signalée dans le rapport."""
    rapport = RapportImport()
    for d in donnees:
        try:
            with transaction.atomic():
                auteur, _ = Auteur.objects.get_or_create(prenom=d.auteur_prenom, nom=d.auteur_nom)
                livre = Livre.objects.filter(isbn=d.isbn).first()
                nouveau = livre is None
                if nouveau:
                    livre = Livre(isbn=d.isbn)
                livre.titre, livre.auteur = d.titre, auteur
                livre.annee_publication, livre.exemplaires, livre.resume = d.annee, d.exemplaires, d.resume
                livre.full_clean()
                livre.save()
        except ValidationError as exc:
            rapport.erreurs.append(f'{d.isbn or "?"} ({d.titre}) : {" ".join(exc.messages)}')
        else:
            if nouveau:
                rapport.crees += 1
            else:
                rapport.mis_a_jour += 1
    return rapport


def importer_adherents(donnees):
    crees = 0
    for a in donnees:
        _, cree = Adherent.objects.get_or_create(
            email=a.email, defaults={'prenom': a.prenom, 'nom': a.nom},
        )
        crees += cree
    return crees


def _livre_vers_dict(livre):
    return {
        'isbn': livre.isbn,
        'titre': livre.titre,
        'auteur': {'prenom': livre.auteur.prenom, 'nom': livre.auteur.nom},
        'annee': livre.annee_publication,
        'exemplaires': livre.exemplaires,
        'resume': livre.resume,
    }


def exporter_json(livres):
    return json.dumps({'livres': [_livre_vers_dict(l) for l in livres]}, ensure_ascii=False, indent=2)


def exporter_xml(livres):
    racine = ET.Element('bibliotheque')
    for livre in livres:
        d = _livre_vers_dict(livre)
        noeud = ET.SubElement(racine, 'livre', isbn=d['isbn'])
        ET.SubElement(noeud, 'titre').text = d['titre']
        auteur = ET.SubElement(noeud, 'auteur')
        ET.SubElement(auteur, 'prenom').text = d['auteur']['prenom']
        ET.SubElement(auteur, 'nom').text = d['auteur']['nom']
        ET.SubElement(noeud, 'annee').text = '' if d['annee'] is None else str(d['annee'])
        ET.SubElement(noeud, 'exemplaires').text = str(d['exemplaires'])
        ET.SubElement(noeud, 'resume').text = d['resume']
    ET.indent(racine)
    return ET.tostring(racine, encoding='utf-8', xml_declaration=True)
