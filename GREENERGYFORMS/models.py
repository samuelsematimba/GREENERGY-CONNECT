from django.db import models
import random 
import string
from django.contrib.auth.models import User

def generate_referral_code():
    prefix="EMP"
    chars =string.ascii_uppercase + string.digits
    random_part= ''.join([random.choice(chars) for _ in range(6)])
    return prefix +"-" + random_part
# Create your models here.
class Outlet_type(models.Model):
    """location of the outlet"""
    text=models.CharField(max_length=100)
    location=models.CharField(max_length=100,default="location")
    manager=models.CharField(max_length=100,default="manager")
    def __str__(self):
        """return the name of the outlet the form is coming from"""
        return self.text
class Entry(models.Model):
    """filling in the form to handle the data"""
    location2=models.CharField(max_length=100, default='Outlet_type')
    surname=models.CharField(max_length=100, default="surname")
    givenname=models.CharField(max_length=100,default="givenname")
    nin=models.CharField(max_length=14,default="nin")
    phonenumber=models.CharField(max_length=20,default=0)
    gender=models.CharField(max_length=10,default="gender")
    stove=models.CharField(max_length=20,default="stove")
    serialnumber=models.CharField(max_length=20,default="sb")
    quantity=models.IntegerField(default=0)
    subcidy=models.CharField(max_length=20,default="subcidy")
    others=models.CharField(max_length=10,default="others")
    date=models.DateField(blank=True,default="2024-01-01")
    expected=models.IntegerField(default=0)
    cashreceived=models.IntegerField(default=0)
    national=models.FileField(upload_to='national/',null=True,blank=True)
    warranty=models.FileField(upload_to='warranty/',null=True,blank=True)
    receipt=models.FileField(upload_to='recipt/',null=True,blank=True)

    class Meta:
        verbose_name_plural ="entries"
    
    def __str__(self):
        """Return a string representation of the model"""
        return  f"{self.givenname} {self.gender} {self.surname} {self.nin} {self.location2} {self.stove} {self.serialnumber} {self.quantity} {self.subcidy} {self.others} {self.expected} {self.cashreceived} {self.date} {self.national} {self.warranty} {self.receipt}"
class Qrcodes(models.Model):
    """database table to save qr codes from file"""
    Singleburner=models.CharField(max_length=8,default="single",null=True,blank=True)
    qr_codeSB= models.ImageField(upload_to="qrcodesSB", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    qr_generated =models.BooleanField(default=False)

    def __str__(self):
        '''this is to return the data that has been submitted'''
        if self.qr_generated==False:
            return f" {self.Singleburner} {self.created_at} {self.qr_generated}"
        else:
            return f" {self.Singleburner} {self.qr_codeSB} {self.created_at} {self.qr_generated}"
class Qrcodes_double(models.Model):
    """database to independently save double burner qr codes"""
    Doubleburner=models.CharField(max_length=8,null=True,blank=True)
    qr_codeDB= models.ImageField(upload_to="qrcodesDB", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    qr_generated =models.BooleanField(default=False)

    def __str__(self):
        '''this is to return the data that has been submitted'''
        if self.qr_generated==False:
            return f"{self.Doubleburner} {self.created_at} {self.qr_generated}"
        else:
            return f"{self.Doubleburner} {self.qr_codeDB} {self.created_at} {self.qr_generated}"
class Excel(models.Model):
    """save to the database"""
    single1=models.CharField(max_length=23,null=True,blank=True)
    double2=models.CharField(max_length=23,null=True,blank=True)

    def __str__(self):
        """this is for the temporary data view"""
        return f'{self.single1} {self.double2}'

class EmpowerCustomer(models.Model):
    '''used to record the empwower customers'''
    full_name = models.CharField(max_length=100)
    nin =models.CharField(max_length=14,unique=True)
    phone_number=models.CharField(max_length=10,unique=True)
    referral_code = models.CharField(max_length=20, unique=True, default=generate_referral_code)
    stove_number = models.CharField(max_length=9, unique=True, blank=True, null=True)
    compliance_photo = models.ImageField(upload_to='compliance_photos/', blank=True, null=True)
    date_registered = models.DateTimeField(auto_now_add=True)
    outlet= models.CharField(max_length=20,blank=True,null=True)

    def _str_(self):
        return f"{self.full_name} | Code: {self.referral_code}"


class EmpowerSale(models.Model):
    """
    Records when a new customer is registered with a recommender's code.
    """
    buyer = models.OneToOneField(
        EmpowerCustomer, on_delete=models.CASCADE, related_name='purchase'
    )
    recommender = models.ForeignKey(
        EmpowerCustomer, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referrals'
    )
    outlet = models.CharField(max_length=100)
    date_of_sale = models.DateTimeField(auto_now_add=True)

    def _str_(self):
        return f"Sale: {self.buyer.full_name} | Referred by: {self.recommender}"


class EmpowerClaim(models.Model):
    """
    Tracks how many Empower biofuel gifts a recommender has earned and claimed.
    One record per referral.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CLAIMED', 'Claimed'),
    ]
    recommender = models.ForeignKey(
        EmpowerCustomer, on_delete=models.CASCADE, related_name='empower_claims'
    )
    sale = models.OneToOneField(EmpowerSale, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    date_created = models.DateTimeField(auto_now_add=True)
    date_claimed = models.DateTimeField(null=True, blank=True)
    sales_number = models.CharField(max_length=20, blank=True, null=True)

    def _str_(self):
        return f"{self.recommender.full_name} | {self.status}"
class Profile(models.Model):
    """Extends the default Django user with a profile picture"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} Profile"