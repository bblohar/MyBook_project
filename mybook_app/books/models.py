# books/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime
from django.db.models import JSONField

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    class Meta:
        verbose_name_plural = "Categories"
    def __str__(self):
        return self.name

class Book(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    section = models.CharField(max_length=255, blank=True, null=True)
    category_name = models.CharField(max_length=255, blank=True, null=True)
<<<<<<< HEAD
    
    # Your existing description column (it's good that it's already here!)
    description = models.TextField(blank=True, null=True) 
    
=======
>>>>>>> f0276963392403a59c306f945bd6310c671830ce
    available = models.BooleanField(default=True)
    
    # This is the new line you must add:
    embedding = JSONField(null=True, blank=True) 

    def __str__(self):
        return self.title

class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    sap_id = models.CharField(max_length=20, null=True, blank=True, default='N/A')
    roll_no = models.CharField(max_length=20, blank=True, null=True)
    phone_no = models.CharField(max_length=15, blank=True, null=True)
    branch_department = models.CharField(max_length=100, blank=True, null=True)
    
    ROLE_CHOICES = [
        ('USER', 'User'),
        ('STAFF', 'Staff'),
        ('ADMIN', 'Admin'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='USER')

    def __str__(self):
        return self.user.username

class BookBorrow(models.Model):
    STATUS_CHOICES = [
        ('BORROWED', 'Borrowed'),
        ('RETURNED', 'Returned'),
    ]
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    borrowed_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='BORROWED')

    def __str__(self):
        return f"{self.user.username} borrowed {self.book.title}"

class StudentQuery(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RESOLVED', 'Resolved'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    query_text = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Query from {self.user.username} ({self.status})"

class BookRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    request_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')

    def __str__(self):
        return f"Request for {self.book.title} by {self.user.username}"

