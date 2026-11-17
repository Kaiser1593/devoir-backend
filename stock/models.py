from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse


class Categorie(models.Model):
    nom = models.CharField("nom", max_length=100, unique=True)
    description = models.TextField("description", blank=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "catégorie"

    def __str__(self):
        return self.nom


class Produit(models.Model):
    reference = models.CharField("référence", max_length=30, unique=True)
    nom = models.CharField("nom", max_length=150)
    categorie = models.ForeignKey(
        Categorie, on_delete=models.PROTECT, related_name="produits", verbose_name="catégorie"
    )
    prix_unitaire = models.DecimalField("prix unitaire (€)", max_digits=10, decimal_places=2, default=0)
    quantite = models.PositiveIntegerField("quantité en stock", default=0, editable=False)
    seuil_alerte = models.PositiveIntegerField("seuil d'alerte", default=5)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return f"{self.reference} – {self.nom}"

    def get_absolute_url(self):
        return reverse("produit_detail", args=[self.pk])

    @property
    def en_alerte(self):
        return self.quantite <= self.seuil_alerte

    @property
    def valeur_stock(self):
        return self.quantite * self.prix_unitaire


class MouvementStock(models.Model):
    ENTREE = "E"
    SORTIE = "S"
    TYPES = [(ENTREE, "Entrée"), (SORTIE, "Sortie")]

    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name="mouvements")
    type = models.CharField("type", max_length=1, choices=TYPES)
    quantite = models.PositiveIntegerField("quantité")
    date = models.DateTimeField("date", auto_now_add=True)
    commentaire = models.CharField("commentaire", max_length=255, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "mouvement de stock"
        verbose_name_plural = "mouvements de stock"

    def __str__(self):
        signe = "+" if self.type == self.ENTREE else "-"
        return f"{self.produit.reference} {signe}{self.quantite}"

    def clean(self):
        """Règles métier : quantité > 0, pas de stock négatif."""
        if self.pk:
            raise ValidationError("Un mouvement existant ne peut pas être modifié.")
        if self.quantite is not None and self.quantite <= 0:
            raise ValidationError({"quantite": "La quantité doit être strictement positive."})
        if self.type == self.SORTIE and self.produit_id and self.quantite:
            if self.quantite > self.produit.quantite:
                raise ValidationError(
                    {"quantite": f"Stock insuffisant : {self.produit.quantite} disponible(s), "
                                 f"{self.quantite} demandé(s)."}
                )

    @transaction.atomic
    def save(self, *args, **kwargs):
        """Valide (sous verrou) puis met à jour la quantité du produit."""
        if self.pk:
            raise ValidationError("Un mouvement existant ne peut pas être modifié.")
        produit = Produit.objects.select_for_update().get(pk=self.produit_id)
        self.produit = produit
        self.clean()
        produit.quantite += self.quantite if self.type == self.ENTREE else -self.quantite
        produit.save(update_fields=["quantite"])
        super().save(*args, **kwargs)
