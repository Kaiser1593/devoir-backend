from django.contrib import admin

from .models import Adherent, Auteur, Emprunt, Livre

admin.site.register(Auteur)
admin.site.register(Adherent)


@admin.register(Livre)
class LivreAdmin(admin.ModelAdmin):
    list_display = ('titre', 'auteur', 'isbn', 'exemplaires')
    search_fields = ('titre', 'isbn', 'auteur__nom')


@admin.register(Emprunt)
class EmpruntAdmin(admin.ModelAdmin):
    list_display = ('livre', 'adherent', 'date_emprunt', 'date_retour_prevue', 'date_retour')
    list_filter = ('date_retour',)
