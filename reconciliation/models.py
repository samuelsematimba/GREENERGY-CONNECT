from django.db import models
from django.contrib.auth.models import User
from accounts.models import Location
import random, string


def generate_recon_ref():
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"REC-{suffix}"


class AgentCollection(models.Model):
    """Level 1: Agent submits daily collection to outlet."""
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('balanced', 'Balanced'),
        ('discrepancy', 'Discrepancy Raised'),
        ('investigating', 'Under Investigation'),
        ('closed', 'Closed'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('mobile_money', 'Mobile Money'),
        ('mixed', 'Mixed'),
    ]
    ref = models.CharField(max_length=20, unique=True, default=generate_recon_ref)
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_collections')
    outlet = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='agent_collections')
    period_start = models.DateField()
    period_end = models.DateField()
    cash_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mobile_money_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mobile_money_reference = models.CharField(max_length=100, blank=True)
    system_expected = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    discrepancy_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='reviewed_collections')
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ref} — {self.agent.get_full_name()} @ {self.outlet.name}"

    @property
    def total_collected(self):
        return self.cash_amount + self.mobile_money_amount

    @property
    def discrepancy_amount(self):
        return self.total_collected - self.system_expected

    class Meta:
        ordering = ['-submitted_at']


class OutletReconciliation(models.Model):
    """Level 2: Outlet reconciles with Back Office."""
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('submitted', 'Submitted to Back Office'),
        ('reviewed', 'Reviewed'),
        ('discrepancy', 'Discrepancy'),
        ('closed', 'Closed'),
    ]
    ref = models.CharField(max_length=20, unique=True, default=generate_recon_ref)
    outlet = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='outlet_reconciliations')
    outlet_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='outlet_recons_managed')
    backoffice_officer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='outlet_recons_reviewed')
    period_start = models.DateField()
    period_end = models.DateField()
    total_sales_system = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_collected = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    bank_deposit_ref = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    discrepancy_notes = models.TextField(blank=True)
    agent_collections = models.ManyToManyField(AgentCollection, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.ref} — {self.outlet.name} [{self.get_status_display()}]"

    @property
    def discrepancy_amount(self):
        return self.total_collected - self.total_sales_system

    class Meta:
        ordering = ['-created_at']


class BackOfficeReconciliation(models.Model):
    """Level 3: Back Office reconciles with Accounts."""
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('submitted', 'Submitted to Accounts'),
        ('reviewed', 'Under Review'),
        ('signed_off', 'Signed Off'),
    ]
    ref = models.CharField(max_length=20, unique=True, default=generate_recon_ref)
    backoffice_officer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                            related_name='backoffice_recons')
    accountant = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='accountant_signoffs')
    period_start = models.DateField()
    period_end = models.DateField()
    total_from_outlets = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    bank_confirmed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    notes = models.TextField(blank=True)
    outlet_reconciliations = models.ManyToManyField(OutletReconciliation, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    signed_off_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.ref} — Back Office [{self.get_status_display()}]"

    @property
    def discrepancy_amount(self):
        return self.bank_confirmed_amount - self.total_from_outlets

    class Meta:
        ordering = ['-created_at']
