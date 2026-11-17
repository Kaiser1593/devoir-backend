import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategorieForm, ImportXMLForm, MouvementForm, ProduitForm
from .models import Categorie, MouvementStock, Produit
from .xml_utils import importer_produits_xml, produits_vers_xml

logger = logging.getLogger(__name__)


def tableau_de_bord(request):
    contexte = {
        "nb_produits": Produit.objects.count(),
        "nb_categories": Categorie.objects.count(),
        "alertes": Produit.objects.filter(quantite__lte=F("seuil_alerte")),
        "valeur_totale": sum(p.valeur_stock for p in Produit.objects.all()),
        "derniers": MouvementStock.objects.select_related("produit")[:8],
    }
    return render(request, "stock/tableau_de_bord.html", contexte)


def produit_liste(request):
    produits = Produit.objects.select_related("categorie")
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("categorie", "")
    if q:
        produits = produits.filter(Q(nom__icontains=q) | Q(reference__icontains=q))
    if cat.isdigit():
        produits = produits.filter(categorie_id=int(cat))
    if request.GET.get("alerte"):
        produits = produits.filter(quantite__lte=F("seuil_alerte"))
    return render(request, "stock/produit_liste.html", {
        "produits": produits,
        "categories": Categorie.objects.all(),
        "q": q, "cat": cat, "alerte": request.GET.get("alerte", ""),
    })


def produit_detail(request, pk):
    produit = get_object_or_404(Produit, pk=pk)
    return render(request, "stock/produit_detail.html", {
        "produit": produit, "mouvements": produit.mouvements.all()[:20]})


def _formulaire(request, form_class, instance, titre, retour):
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        logger.info("%s enregistré : %s", form_class.__name__, obj)
        messages.success(request, "Enregistrement effectué.")
        return redirect(retour)
    return render(request, "stock/formulaire.html",
                  {"form": form, "titre": titre, "retour": retour})


def produit_creer(request):
    return _formulaire(request, ProduitForm, None, "Nouveau produit", "produit_liste")


def produit_modifier(request, pk):
    produit = get_object_or_404(Produit, pk=pk)
    return _formulaire(request, ProduitForm, produit, f"Modifier {produit.nom}", "produit_liste")


def produit_supprimer(request, pk):
    produit = get_object_or_404(Produit, pk=pk)
    if request.method == "POST":
        produit.delete()
        messages.success(request, "Produit supprimé.")
        return redirect("produit_liste")
    return render(request, "stock/confirmer_suppression.html",
                  {"objet": produit, "retour": "produit_liste"})


def categorie_liste(request):
    return render(request, "stock/categorie_liste.html", {"categories": Categorie.objects.all()})


def categorie_creer(request):
    return _formulaire(request, CategorieForm, None, "Nouvelle catégorie", "categorie_liste")


def categorie_supprimer(request, pk):
    categorie = get_object_or_404(Categorie, pk=pk)
    if request.method == "POST":
        try:
            categorie.delete()
            messages.success(request, "Catégorie supprimée.")
        except ProtectedError:
            messages.error(request, "Impossible : des produits utilisent cette catégorie.")
        return redirect("categorie_liste")
    return render(request, "stock/confirmer_suppression.html",
                  {"objet": categorie, "retour": "categorie_liste"})


def mouvement_liste(request):
    mouvements = MouvementStock.objects.select_related("produit")
    type_ = request.GET.get("type", "")
    if type_ in (MouvementStock.ENTREE, MouvementStock.SORTIE):
        mouvements = mouvements.filter(type=type_)
    return render(request, "stock/mouvement_liste.html",
                  {"mouvements": mouvements[:200], "type": type_})


def mouvement_creer(request):
    form = MouvementForm(request.POST or None, initial={"produit": request.GET.get("produit")})
    if request.method == "POST" and form.is_valid():
        mvt = form.save(commit=False)
        try:
            mvt.save()
        except ValidationError as exc:  # règle métier vérifiée sous verrou
            for msg in exc.messages:
                form.add_error(None, msg)
        else:
            logger.info("Mouvement enregistré : %s", mvt)
            messages.success(request, "Mouvement enregistré.")
            return redirect("produit_detail", pk=mvt.produit_id)
    return render(request, "stock/formulaire.html",
                  {"form": form, "titre": "Nouveau mouvement", "retour": "mouvement_liste"})


def export_xml(request):
    reponse = HttpResponse(produits_vers_xml(Produit.objects.all()),
                           content_type="application/xml")
    reponse["Content-Disposition"] = 'attachment; filename="produits.xml"'
    return reponse


def import_xml(request):
    form = ImportXMLForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        crees, maj, erreurs = importer_produits_xml(form.cleaned_data["fichier"].read())
        messages.success(request, f"{crees} produit(s) créé(s), {maj} mis à jour.")
        for e in erreurs:
            messages.error(request, e)
        return redirect("produit_liste")
    return render(request, "stock/formulaire.html",
                  {"form": form, "titre": "Importer des produits (XML)",
                   "retour": "produit_liste", "multipart": True})
