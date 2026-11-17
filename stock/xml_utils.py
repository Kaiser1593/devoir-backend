"""Export / import XML des produits (xml.etree)."""
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

from .models import Categorie, Produit


def produits_vers_xml(queryset):
    racine = ET.Element("produits")
    for p in queryset.select_related("categorie"):
        el = ET.SubElement(racine, "produit", reference=p.reference)
        ET.SubElement(el, "nom").text = p.nom
        ET.SubElement(el, "categorie").text = p.categorie.nom
        ET.SubElement(el, "prix").text = str(p.prix_unitaire)
        ET.SubElement(el, "quantite").text = str(p.quantite)
        ET.SubElement(el, "seuil_alerte").text = str(p.seuil_alerte)
    return ET.tostring(racine, encoding="utf-8", xml_declaration=True)


def importer_produits_xml(contenu):
    """Crée/met à jour les produits. Retourne (nb_créés, nb_maj, erreurs)."""
    try:
        racine = ET.fromstring(contenu)
    except ET.ParseError as exc:
        return 0, 0, [f"XML invalide : {exc}"]
    if racine.tag != "produits":
        return 0, 0, ["L'élément racine doit être <produits>."]
    crees = maj = 0
    erreurs = []
    for i, el in enumerate(racine.findall("produit"), start=1):
        try:
            ref = el.get("reference")
            nom = el.findtext("nom")
            cat = el.findtext("categorie")
            if not (ref and nom and cat):
                raise ValueError("reference, nom et categorie sont obligatoires")
            prix = Decimal(el.findtext("prix", "0"))
            seuil = int(el.findtext("seuil_alerte", "5"))
            if prix < 0 or seuil < 0:
                raise ValueError("prix et seuil doivent être positifs")
            categorie, _ = Categorie.objects.get_or_create(nom=cat.strip())
            _, cree = Produit.objects.update_or_create(
                reference=ref.strip(),
                defaults={"nom": nom.strip(), "categorie": categorie,
                          "prix_unitaire": prix, "seuil_alerte": seuil},
            )
            crees += cree
            maj += not cree
        except (ValueError, InvalidOperation) as exc:
            erreurs.append(f"Produit n°{i} : {exc}")
    return crees, maj, erreurs
