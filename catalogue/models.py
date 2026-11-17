from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Count, F, Q
from django.urls import reverse
from django.utils import timezone

DUREE_PRET_JOURS = 21
MAX_EMPRUNTS_SIMULTANES = 3


def date_retour_par_defaut():
    return timezone.localdate() + timedelta(days=DUREE_PRET_JOURS)


class Auteur(models.Model):
    prenom = models.CharField('prénom', max_length=100)
    nom = models.CharField(max_length=100)
    nationalite = models.CharField('nationalité', max_length=100, blank=True)

    class Meta:
        ordering = ['nom', 'prenom']
        unique_together = [('prenom', 'nom')]
        verbose_name_plural = 'auteurs'

    def __str__(self):
        return f'{self.prenom} {self.nom}'


class LivreQuerySet(models.QuerySet):
    def avec_disponibilite(self):
        """Ajoute en_cours_count et disponibles_count (évite le N+1 dans les listes)."""
        return self.annotate(
            en_cours_count=Count('emprunts', filter=Q(emprunts__date_retour__isnull=True)),
        ).annotate(disponibles_count=F('exemplaires') - F('en_cours_count'))

    def en_stock(self):
        return self.avec_disponibilite().filter(disponibles_count__gt=0)

    def rechercher(self, terme):
        terme = (terme or '').strip()
        if not terme:
            return self
        return self.filter(
            Q(titre__icontains=terme)
            | Q(isbn__icontains=terme)
            | Q(auteur__nom__icontains=terme)
            | Q(auteur__prenom__icontains=terme)
        )


class Livre(models.Model):
    titre = models.CharField(max_length=200)
    isbn = models.CharField(
        'ISBN', max_length=13, unique=True,
        validators=[RegexValidator(r'^\d{10}(\d{3})?$', "L'ISBN doit contenir 10 ou 13 chiffres (sans tirets).")],
    )
    auteur = models.ForeignKey(Auteur, on_delete=models.PROTECT, related_name='livres')
    annee_publication = models.PositiveSmallIntegerField('année de publication', null=True, blank=True)
    exemplaires = models.PositiveIntegerField(
        "nombre d'exemplaires", default=1, validators=[MinValueValidator(1)],
    )
    resume = models.TextField('résumé', blank=True)

    objects = LivreQuerySet.as_manager()

    class Meta:
        ordering = ['titre']

    def __str__(self):
        return self.titre

    def get_absolute_url(self):
        return reverse('livre-detail', args=[self.pk])

    @property
    def en_cours(self):
        if hasattr(self, 'en_cours_count'):
            return self.en_cours_count
        return self.emprunts.filter(date_retour__isnull=True).count()

    @property
    def disponibles(self):
        return self.exemplaires - self.en_cours

    def clean(self):
        # Règle : on ne peut pas descendre sous le nombre d'exemplaires actuellement prêtés.
        if self.pk and self.exemplaires is not None and self.exemplaires < self.en_cours:
            raise ValidationError({
                'exemplaires': f'{self.en_cours} exemplaire(s) sont actuellement empruntés : '
                               f'le total ne peut pas être inférieur.'
            })


class Adherent(models.Model):
    prenom = models.CharField('prénom', max_length=100)
    nom = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    date_inscription = models.DateField("date d'inscription", default=timezone.localdate)

    class Meta:
        ordering = ['nom', 'prenom']
        verbose_name = 'adhérent'

    def __str__(self):
        return f'{self.prenom} {self.nom}'

    def get_absolute_url(self):
        return reverse('adherent-detail', args=[self.pk])

    @property
    def en_cours(self):
        return self.emprunts.filter(date_retour__isnull=True).count()


class Emprunt(models.Model):
    livre = models.ForeignKey(Livre, on_delete=models.PROTECT, related_name='emprunts')
    adherent = models.ForeignKey(Adherent, on_delete=models.PROTECT, related_name='emprunts')
    date_emprunt = models.DateField("date d'emprunt", default=timezone.localdate)
    date_retour_prevue = models.DateField('retour prévu le', default=date_retour_par_defaut)
    date_retour = models.DateField('rendu le', null=True, blank=True)

    class Meta:
        ordering = ['-date_emprunt', '-id']

    def __str__(self):
        return f'{self.livre} → {self.adherent}'

    @property
    def est_en_cours(self):
        return self.date_retour is None

    @property
    def est_en_retard(self):
        return self.est_en_cours and self.date_retour_prevue < timezone.localdate()

    def clean(self):
        """Règles métier, vérifiées côté serveur (formulaires, API, admin, shell)."""
        erreurs = {}
        if self.date_emprunt and self.date_retour_prevue and self.date_retour_prevue < self.date_emprunt:
            erreurs['date_retour_prevue'] = "Le retour prévu ne peut pas précéder la date d'emprunt."
        if self.date_emprunt and self.date_retour and self.date_retour < self.date_emprunt:
            erreurs['date_retour'] = "Le retour ne peut pas précéder la date d'emprunt."
        # Nouvel emprunt actif : disponibilité + plafond par adhérent.
        if self._state.adding and self.date_retour is None and self.livre_id and self.adherent_id:
            if self.livre.disponibles <= 0:
                erreurs['livre'] = 'Ce livre est indisponible : tous les exemplaires sont empruntés.'
            if self.adherent.en_cours >= MAX_EMPRUNTS_SIMULTANES:
                erreurs['adherent'] = (
                    f'Cet adhérent a déjà {MAX_EMPRUNTS_SIMULTANES} emprunts en cours (maximum autorisé).'
                )
        if erreurs:
            raise ValidationError(erreurs)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def retourner(self, date_retour=None):
        if not self.est_en_cours:
            raise ValueError('Cet emprunt a déjà été retourné.')
        self.date_retour = date_retour or timezone.localdate()
        self.save()
