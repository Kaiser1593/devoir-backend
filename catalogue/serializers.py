from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Adherent, Auteur, Emprunt, Livre


class AuteurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Auteur
        fields = ['id', 'prenom', 'nom', 'nationalite']


class LivreSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.CharField(source='auteur.__str__', read_only=True)
    disponibles = serializers.IntegerField(read_only=True)

    class Meta:
        model = Livre
        fields = ['id', 'titre', 'isbn', 'auteur', 'auteur_nom', 'annee_publication',
                  'exemplaires', 'disponibles', 'resume']

    def validate(self, attrs):
        exemplaires = attrs.get('exemplaires')
        if self.instance and exemplaires is not None and exemplaires < self.instance.en_cours:
            raise serializers.ValidationError({
                'exemplaires': f'{self.instance.en_cours} exemplaire(s) sont empruntés : total insuffisant.'
            })
        return attrs


class AdherentSerializer(serializers.ModelSerializer):
    en_cours = serializers.IntegerField(read_only=True)

    class Meta:
        model = Adherent
        fields = ['id', 'prenom', 'nom', 'email', 'date_inscription', 'en_cours']


class EmpruntSerializer(serializers.ModelSerializer):
    livre_titre = serializers.CharField(source='livre.titre', read_only=True)
    adherent_nom = serializers.CharField(source='adherent.__str__', read_only=True)
    en_retard = serializers.BooleanField(source='est_en_retard', read_only=True)

    class Meta:
        model = Emprunt
        fields = ['id', 'livre', 'livre_titre', 'adherent', 'adherent_nom',
                  'date_emprunt', 'date_retour_prevue', 'date_retour', 'en_retard']
        read_only_fields = ['date_retour']

    def validate(self, attrs):
        # Réutilise les règles métier du modèle (disponibilité, plafond, dates).
        try:
            Emprunt(**attrs).clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except DjangoValidationError as exc:  # course entre validate() et save()
            raise serializers.ValidationError(exc.message_dict)
