from django import forms
from django.utils import timezone

from .models import Adherent, Auteur, Emprunt, Livre


class AuteurForm(forms.ModelForm):
    class Meta:
        model = Auteur
        fields = ['prenom', 'nom', 'nationalite']


class LivreForm(forms.ModelForm):
    class Meta:
        model = Livre
        fields = ['titre', 'isbn', 'auteur', 'annee_publication', 'exemplaires', 'resume']
        widgets = {'resume': forms.Textarea(attrs={'rows': 4})}

    def clean_annee_publication(self):
        annee = self.cleaned_data.get('annee_publication')
        if annee is not None and annee > timezone.localdate().year:
            raise forms.ValidationError("L'année de publication ne peut pas être dans le futur.")
        return annee


class AdherentForm(forms.ModelForm):
    class Meta:
        model = Adherent
        fields = ['prenom', 'nom', 'email']


class LivreChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.titre} ({obj.disponibles_count}/{obj.exemplaires} dispo.)'


class EmpruntForm(forms.ModelForm):
    livre = LivreChoiceField(queryset=Livre.objects.none())

    class Meta:
        model = Emprunt
        fields = ['livre', 'adherent', 'date_emprunt', 'date_retour_prevue']
        widgets = {
            'date_emprunt': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'date_retour_prevue': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tous les livres sont proposés : la règle de disponibilité est vérifiée côté serveur.
        self.fields['livre'].queryset = Livre.objects.avec_disponibilite()


class ImportForm(forms.Form):
    fichier = forms.FileField(label='Fichier JSON ou XML')

    def clean_fichier(self):
        f = self.cleaned_data['fichier']
        if not f.name.lower().endswith(('.json', '.xml')):
            raise forms.ValidationError('Format non supporté : utilisez un fichier .json ou .xml.')
        if f.size > 1_000_000:
            raise forms.ValidationError('Fichier trop volumineux (1 Mo maximum).')
        return f
