from django import forms

from .models import Categorie, MouvementStock, Produit


class CategorieForm(forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ["nom", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class ProduitForm(forms.ModelForm):
    class Meta:
        model = Produit
        fields = ["reference", "nom", "categorie", "prix_unitaire", "seuil_alerte"]

    def clean_prix_unitaire(self):
        prix = self.cleaned_data["prix_unitaire"]
        if prix < 0:
            raise forms.ValidationError("Le prix ne peut pas être négatif.")
        return prix


class MouvementForm(forms.ModelForm):
    class Meta:
        model = MouvementStock
        fields = ["produit", "type", "quantite", "commentaire"]


class ImportXMLForm(forms.Form):
    fichier = forms.FileField(label="Fichier XML de produits")
