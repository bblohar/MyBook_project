# books/admin.py
from django.contrib import admin
from .models import Category, Book, StudentProfile, BookBorrow, StudentQuery, BookRequest

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category_name', 'section', 'location', 'available')
    list_filter = ('category_name', 'section', 'available')
    search_fields = ('title', 'author')

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'sap_id', 'roll_no', 'phone_no')
    search_fields = ('user__username', 'sap_id')

@admin.register(BookBorrow)
class BookBorrowAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'borrowed_date', 'due_date', 'status')
    list_filter = ('status', 'due_date')
    search_fields = ('user__username', 'book__title')

@admin.register(BookRequest)
class BookRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'request_date', 'status')
    list_filter = ('status',)
    search_fields = ('user__username', 'book__title')

@admin.register(StudentQuery)
class StudentQueryAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'created_at', 'query_text')
    list_filter = ('status',)
    search_fields = ('user__username',)

