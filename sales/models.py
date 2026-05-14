from django.db import models
from django.contrib.auth.models import User
from accounts.models import Location
from products.models import Product, SerializedItem, Combo, Subsidy
import random, string
from django.utils import timezone


def generate_sale_ref():
    today = timezone.now().strftime('%Y%m%d')
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"SALE-{today}-{suffix}"


class Customer(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]
    full_name = models.CharField(max_length=200)
    nin = models.CharField(max_length=20, unique=True)
    phone_number = models.CharField(max_length=20, unique=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    village = models.CharField(max_length=200, blank=True)
    district = models.CharField(max_length=200, blank=True)
    national_id_photo = models.ImageField(upload_to='national_ids/', null=True, blank=True)
    registered_at = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='customers',
        help_text="Outlet where this customer was first registered"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} | {self.nin}"


class Sale(models.Model):
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('pending_payment', 'Pending Payment'),
        ('cancelled', 'Cancelled'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('mobile_money', 'Mobile Money'),
        ('credit', 'Credit'),
    ]
    sale_ref = models.CharField(max_length=30, unique=True, default=generate_sale_ref)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='sales')
    outlet = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='sales',
                               limit_choices_to={'location_type': 'outlet'})
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sales_made')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    warranty_card = models.FileField(upload_to='warranty/', null=True, blank=True)
    receipt_file = models.FileField(upload_to='receipts/', null=True, blank=True)
    notes = models.TextField(blank=True)
    subsidy = models.ForeignKey(
        'products.Subsidy', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='sales'
    )
    subsidy_discount_applied = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Actual discount amount deducted at time of sale"
    )
    sale_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sale_ref} — {self.customer.full_name}"

    class Meta:
        ordering = ['-sale_date']

    @property
    def balance(self):
        return self.total_amount - self.amount_paid


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    combo = models.ForeignKey(Combo, on_delete=models.SET_NULL, null=True, blank=True)
    serialized_item = models.ForeignKey(SerializedItem, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        item = self.product or self.combo
        return f"{self.sale.sale_ref} — {item} x{self.quantity}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity
