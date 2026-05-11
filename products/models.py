from django.db import models
from accounts.models import Country, Location
from django.contrib.auth.models import User


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"


class Product(models.Model):
    PRODUCT_TYPE_CHOICES = [
        ('serialized', 'Serialized'),
        ('non_serialized', 'Non-Serialized'),
    ]
    UNIT_CHOICES = [
        ('piece', 'Piece'),
        ('litre', 'Litre'),
        ('kg', 'Kilogram'),
        ('set', 'Set'),
        ('pack', 'Pack'),
    ]
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='piece')
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    countries = models.ManyToManyField(Country, blank=True, related_name='products')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"


class LocationPrice(models.Model):
    """Location-specific price override for a product."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='location_prices')
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'location')

    def __str__(self):
        return f"{self.product.name} @ {self.location.name}: {self.price}"


class SerializedItem(models.Model):
    STATUS_CHOICES = [
        ('in_stock', 'In Stock'),
        ('in_transit', 'In Transit'),
        ('sold', 'Sold'),
        ('returned', 'Returned'),
        ('faulty', 'Faulty'),
        ('written_off', 'Written Off'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='items')
    serial_number = models.CharField(max_length=50, unique=True)
    qr_code = models.ImageField(upload_to='qrcodes_products/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_stock')
    current_location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.serial_number} — {self.product.name} [{self.get_status_display()}]"


class Combo(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    countries = models.ManyToManyField(Country, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class ComboItem(models.Model):
    combo = models.ForeignKey(Combo, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.combo.name} → {self.product.name} x{self.quantity}"


class PriceHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_history')
    old_price = models.DecimalField(max_digits=12, decimal_places=2)
    new_price = models.DecimalField(max_digits=12, decimal_places=2)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    def __str__(self):
        return f"{self.product.name}: {self.old_price} → {self.new_price}"

    class Meta:
        ordering = ['-changed_at']
        verbose_name_plural = "Price Histories"
