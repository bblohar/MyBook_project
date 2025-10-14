# books/views.py
import logging
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Book, Category, BookBorrow, StudentQuery, StudentProfile
from .serializers import (
    UserSerializer,
    CategorySerializer,
    BookSerializer,
    OverdueBookSerializer,
    StudentQuerySerializer,
    StudentProfileSerializer
)

logger = logging.getLogger(__name__)

# --- AuthViewSet ---
class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = User.objects.create_user(
                    username=serializer.validated_data['username'],
                    email=serializer.validated_data.get('email', ''),
                    password=serializer.validated_data['password']
                )
                StudentProfile.objects.create(user=user)
                return Response({'message': 'User registered successfully.'}, status=status.HTTP_201_CREATED)
            except IntegrityError:
                return Response({'error': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def login(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            logger.info(f"User '{username}' logged in successfully.")
            return Response({
                'message': 'Login successful.',
                'is_staff': user.is_superuser # Use is_superuser as requested
            }, status=status.HTTP_200_OK)
        else:
            logger.warning(f"Login failed for username '{username}': Invalid credentials.")
            return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        logout(request)
        return Response({'message': 'Logout successful.'}, status=status.HTTP_200_OK)


# --- CategoryViewSet ---
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


# --- BookViewSet ---
class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Book.objects.all()
        category = self.request.query_params.get('category')
        section = self.request.query_params.get('section')
        search_query = self.request.query_params.get('search')
        if category:
            queryset = queryset.filter(category_name__icontains=category)
        if section:
            queryset = queryset.filter(section__icontains=section)
        if search_query:
            queryset = queryset.filter(Q(title__icontains=search_query) | Q(author__icontains=search_query))
        return queryset
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def rent(self, request, pk=None):
        try:
            book = self.get_object()
            if not book.available:
                return Response({'message': 'Book is already unavailable.'}, status=status.HTTP_400_BAD_REQUEST)
            
            due_date = request.data.get('due_date')
            purpose = request.data.get('purpose')
            if not due_date:
                return Response({'error': 'Return date is required.'}, status=status.HTTP_400_BAD_REQUEST)

            book.available = False
            book.save()
            BookBorrow.objects.create(book=book, user=request.user, due_date=due_date, purpose=purpose)
            return Response({'message': f'You have successfully borrowed "{book.title}".'})
        except Book.DoesNotExist:
            return Response({'error': 'Book not found.'}, status=status.HTTP_404_NOT_FOUND)


# --- AdminDashboardViewSet ---
class AdminDashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overdue_books(self, request):
        today = timezone.now().date()
        overdue_records = BookBorrow.objects.filter(due_date__lt=today, status='BORROWED')
        serializer = OverdueBookSerializer(overdue_records, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def raised_queries(self, request):
        pending_queries = StudentQuery.objects.filter(status='PENDING')
        serializer = StudentQuerySerializer(pending_queries, many=True)
        return Response(serializer.data)


# --- ProfileViewSet ---
class ProfileViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def me(self, request):
        try:
            profile = request.user.profile
            serializer = StudentProfileSerializer(profile)
            return Response(serializer.data)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found. Please create one.'}, status=status.HTTP_404_NOT_FOUND)

