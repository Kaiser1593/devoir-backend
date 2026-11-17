from django.urls import path

from . import views

urlpatterns = [
    path('', views.AccueilView.as_view(), name='accueil'),

    path('livres/', views.LivreListView.as_view(), name='livre-list'),
    path('livres/nouveau/', views.LivreCreateView.as_view(), name='livre-create'),
    path('livres/<int:pk>/', views.LivreDetailView.as_view(), name='livre-detail'),
    path('livres/<int:pk>/modifier/', views.LivreUpdateView.as_view(), name='livre-update'),
    path('livres/<int:pk>/supprimer/', views.LivreDeleteView.as_view(), name='livre-delete'),

    path('auteurs/', views.AuteurListView.as_view(), name='auteur-list'),
    path('auteurs/nouveau/', views.AuteurCreateView.as_view(), name='auteur-create'),
    path('auteurs/<int:pk>/modifier/', views.AuteurUpdateView.as_view(), name='auteur-update'),
    path('auteurs/<int:pk>/supprimer/', views.AuteurDeleteView.as_view(), name='auteur-delete'),

    path('adherents/', views.AdherentListView.as_view(), name='adherent-list'),
    path('adherents/nouveau/', views.AdherentCreateView.as_view(), name='adherent-create'),
    path('adherents/<int:pk>/', views.AdherentDetailView.as_view(), name='adherent-detail'),
    path('adherents/<int:pk>/modifier/', views.AdherentUpdateView.as_view(), name='adherent-update'),
    path('adherents/<int:pk>/supprimer/', views.AdherentDeleteView.as_view(), name='adherent-delete'),

    path('emprunts/', views.EmpruntListView.as_view(), name='emprunt-list'),
    path('emprunts/nouveau/', views.EmpruntCreateView.as_view(), name='emprunt-create'),
    path('emprunts/<int:pk>/retour/', views.emprunt_retour, name='emprunt-retour'),

    path('export/livres.json', views.export_livres, {'fmt': 'json'}, name='export-json'),
    path('export/livres.xml', views.export_livres, {'fmt': 'xml'}, name='export-xml'),
    path('import/', views.import_livres, name='import'),
]
