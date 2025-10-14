# books/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Book, Category, StudentProfile, BookBorrow, StudentQuery

# --- UserSerializer for registration ---
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')

# --- BookBorrow Serializer for Profile View ---
class UserProfileBorrowSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source='book.title', read_only=True)

    class Meta:
        model = BookBorrow
        fields = ['title', 'due_date', 'status']

# --- StudentProfileSerializer for the /profile/me/ endpoint ---
class StudentProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    borrowed_books = UserProfileBorrowSerializer(source='user.bookborrow_set', many=True, read_only=True)

    class Meta:
        model = StudentProfile
        fields = (
            'username', 'email', 'sap_id', 'roll_no', 'phone_no',
            'branch_department', 'borrowed_books'
        )

# --- CategorySerializer ---
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('name',)

# --- BookSerializer ---
class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = "__all__"

# --- OverdueBookSerializer for Admin Dashboard ---
class OverdueBookSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source='book.title', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = BookBorrow
        fields = ('username', 'book_title', 'borrowed_date', 'due_date')

# --- StudentQuerySerializer for Admin Dashboard ---
class StudentQuerySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = StudentQuery
        fields = ('id', 'username', 'query_text', 'status', 'created_at')

