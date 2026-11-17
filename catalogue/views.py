from django.contrib import messages
from django.db.models import Count, ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from .forms import AdherentForm, AuteurForm, EmpruntForm, ImportForm, LivreForm
from .models import Adherent, Auteur, Emprunt, Livre
from .services import echanges


class TitreMixin:
    titre = ''

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titre'] = self.titre
        return ctx


class FormulaireMixin(TitreMixin):
    template_name = 'catalogue/form.html'
    message_succes = 'Enregistré.'

    def form_valid(self, form):
        reponse = super().form_valid(form)
        messages.success(self.request, self.message_succes)
        return reponse

    def form_invalid(self, form):
        messages.error(self.request, 'Le formulaire contient des erreurs : corrigez-les ci-dessous.')
        return super().form_invalid(form)


class SuppressionMixin(TitreMixin):
    template_name = 'catalogue/confirm_delete.html'

    def form_valid(self, form):
        try:
            reponse = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, 'Suppression impossible : cet élément est utilisé ailleurs (livres ou emprunts liés).')
            return redirect(self.success_url)
        messages.success(self.request, 'Élément supprimé.')
        return reponse


# --- Accueil -----------------------------------------------------------------
class AccueilView(TemplateView):
    template_name = 'catalogue/accueil.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        en_cours = Emprunt.objects.filter(date_retour__isnull=True)
        ctx.update(
            nb_livres=Livre.objects.count(),
            nb_adherents=Adherent.objects.count(),
            nb_en_cours=en_cours.count(),
            retards=en_cours.filter(date_retour_prevue__lt=timezone.localdate()).select_related('livre', 'adherent'),
        )
        return ctx


# --- Livres ------------------------------------------------------------------
TRIS_LIVRES = {
    'titre': 'titre', '-titre': '-titre',
    'auteur': 'auteur__nom', '-auteur': '-auteur__nom',
    'annee': 'annee_publication', '-annee': '-annee_publication',
}


class LivreListView(ListView):
    template_name = 'catalogue/livre_list.html'
    paginate_by = 10

    def get_queryset(self):
        qs = Livre.objects.avec_disponibilite().select_related('auteur')
        qs = qs.rechercher(self.request.GET.get('q'))
        if self.request.GET.get('dispo'):
            qs = qs.filter(disponibles_count__gt=0)
        return qs.order_by(TRIS_LIVRES.get(self.request.GET.get('tri'), 'titre'), 'id')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['dispo'] = bool(self.request.GET.get('dispo'))
        ctx['tri'] = self.request.GET.get('tri', 'titre')
        ctx['querystring'] = params.urlencode()
        return ctx


class LivreDetailView(DetailView):
    template_name = 'catalogue/livre_detail.html'

    def get_queryset(self):
        return Livre.objects.select_related('auteur')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['emprunts'] = self.object.emprunts.select_related('adherent')
        return ctx


class LivreCreateView(FormulaireMixin, CreateView):
    model = Livre
    form_class = LivreForm
    titre = 'Nouveau livre'
    message_succes = 'Livre créé.'


class LivreUpdateView(FormulaireMixin, UpdateView):
    model = Livre
    form_class = LivreForm
    titre = 'Modifier le livre'
    message_succes = 'Livre modifié.'


class LivreDeleteView(SuppressionMixin, DeleteView):
    model = Livre
    titre = 'Supprimer le livre'
    success_url = reverse_lazy('livre-list')


# --- Auteurs -----------------------------------------------------------------
class AuteurListView(ListView):
    template_name = 'catalogue/auteur_list.html'

    def get_queryset(self):
        return Auteur.objects.annotate(nb_livres=Count('livres'))


class AuteurCreateView(FormulaireMixin, CreateView):
    model = Auteur
    form_class = AuteurForm
    titre = 'Nouvel auteur'
    success_url = reverse_lazy('auteur-list')
    message_succes = 'Auteur créé.'


class AuteurUpdateView(FormulaireMixin, UpdateView):
    model = Auteur
    form_class = AuteurForm
    titre = "Modifier l'auteur"
    success_url = reverse_lazy('auteur-list')
    message_succes = 'Auteur modifié.'


class AuteurDeleteView(SuppressionMixin, DeleteView):
    model = Auteur
    titre = "Supprimer l'auteur"
    success_url = reverse_lazy('auteur-list')


# --- Adhérents ---------------------------------------------------------------
class AdherentListView(ListView):
    template_name = 'catalogue/adherent_list.html'
    model = Adherent


class AdherentDetailView(DetailView):
    model = Adherent
    template_name = 'catalogue/adherent_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['emprunts'] = self.object.emprunts.select_related('livre')
        return ctx


class AdherentCreateView(FormulaireMixin, CreateView):
    model = Adherent
    form_class = AdherentForm
    titre = 'Nouvel adhérent'
    message_succes = 'Adhérent créé.'


class AdherentUpdateView(FormulaireMixin, UpdateView):
    model = Adherent
    form_class = AdherentForm
    titre = "Modifier l'adhérent"
    message_succes = 'Adhérent modifié.'


class AdherentDeleteView(SuppressionMixin, DeleteView):
    model = Adherent
    titre = "Supprimer l'adhérent"
    success_url = reverse_lazy('adherent-list')


# --- Emprunts ----------------------------------------------------------------
class EmpruntListView(ListView):
    template_name = 'catalogue/emprunt_list.html'
    paginate_by = 15

    def get_queryset(self):
        qs = Emprunt.objects.select_related('livre', 'adherent')
        statut = self.request.GET.get('statut')
        if statut == 'en_cours':
            qs = qs.filter(date_retour__isnull=True)
        elif statut == 'retards':
            qs = qs.filter(date_retour__isnull=True, date_retour_prevue__lt=timezone.localdate())
        elif statut == 'rendus':
            qs = qs.filter(date_retour__isnull=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['statut'] = self.request.GET.get('statut', '')
        return ctx


class EmpruntCreateView(FormulaireMixin, CreateView):
    model = Emprunt
    form_class = EmpruntForm
    titre = 'Nouvel emprunt'
    success_url = reverse_lazy('emprunt-list')
    message_succes = 'Emprunt enregistré.'


@require_POST
def emprunt_retour(request, pk):
    """Version sans JavaScript du retour (le JS passe par l'API)."""
    emprunt = get_object_or_404(Emprunt, pk=pk)
    try:
        emprunt.retourner()
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'« {emprunt.livre} » est retourné.')
    return redirect('emprunt-list')


# --- Import / export JSON & XML ----------------------------------------------
def export_livres(request, fmt):
    livres = Livre.objects.select_related('auteur').order_by('titre')
    if fmt == 'json':
        contenu, type_mime = echanges.exporter_json(livres), 'application/json'
    else:
        contenu, type_mime = echanges.exporter_xml(livres), 'application/xml'
    reponse = HttpResponse(contenu, content_type=f'{type_mime}; charset=utf-8')
    reponse['Content-Disposition'] = f'attachment; filename="livres.{fmt}"'
    return reponse


def import_livres(request):
    rapport = None
    if request.method == 'POST':
        form = ImportForm(request.POST, request.FILES)
        if form.is_valid():
            fichier = form.cleaned_data['fichier']
            try:
                donnees = echanges.analyser_contenu(fichier.name, fichier.read())
            except echanges.DonneesInvalides as exc:
                form.add_error('fichier', str(exc))
            else:
                rapport = echanges.importer_livres(donnees)
                messages.success(request, f'Import terminé : {rapport.crees} créé(s), {rapport.mis_a_jour} mis à jour.')
    else:
        form = ImportForm()
    return render(request, 'catalogue/import.html', {'form': form, 'rapport': rapport})
