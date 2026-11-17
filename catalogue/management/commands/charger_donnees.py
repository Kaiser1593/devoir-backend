from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from catalogue.models import Adherent, Emprunt, Livre
from catalogue.services import echanges


class Command(BaseCommand):
    help = 'Charge les données fictives (data/livres.json, data/livres.xml, data/adherents.json) et quelques emprunts.'

    def handle(self, *args, **options):
        dossier = Path(settings.BASE_DIR) / 'data'
        try:
            for nom in ('livres.json', 'livres.xml'):
                rapport = echanges.importer_livres(echanges.lire_fichier(dossier / nom))
                self.stdout.write(f'{nom} : {rapport.crees} créé(s), {rapport.mis_a_jour} mis à jour')
                for erreur in rapport.erreurs:
                    self.stderr.write(f'  ! {erreur}')
            crees = echanges.importer_adherents(echanges.lire_adherents_json(dossier / 'adherents.json'))
            self.stdout.write(f'adherents.json : {crees} créé(s)')
        except echanges.DonneesInvalides as exc:
            raise CommandError(str(exc)) from exc

        if Emprunt.objects.exists():
            self.stdout.write('Emprunts déjà présents : non recréés.')
            return
        aujourdhui = timezone.localdate()
        camille, samir, lea = (Adherent.objects.get(email=f'{e}@example.com')
                               for e in ('camille.durand', 'samir.benali', 'lea.martin'))
        miserables = Livre.objects.get(isbn='9780000000011')
        germinal = Livre.objects.get(isbn='9780000000066')
        monte_cristo = Livre.objects.get(isbn='9780000000059')
        # Un emprunt en retard, un en cours, un déjà rendu.
        Emprunt.objects.create(livre=miserables, adherent=camille,
                               date_emprunt=aujourdhui - timedelta(days=40),
                               date_retour_prevue=aujourdhui - timedelta(days=19))
        Emprunt.objects.create(livre=monte_cristo, adherent=samir)
        Emprunt.objects.create(livre=germinal, adherent=lea,
                               date_emprunt=aujourdhui - timedelta(days=30),
                               date_retour_prevue=aujourdhui - timedelta(days=9),
                               date_retour=aujourdhui - timedelta(days=12))
        self.stdout.write(self.style.SUCCESS('Données fictives chargées.'))
