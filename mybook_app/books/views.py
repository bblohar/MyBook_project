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

from .models import Book, Category, BookBorrow, StudentQuery, StudentProfile,BookRequest
from .serializers import (
    UserSerializer,
    CategorySerializer,
    BookSerializer,
    OverdueBookSerializer,
    StudentQuerySerializer,
    StudentProfileSerializer,
    BookRequestSerializer
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
                return Response({'<br> </br> message': 'User registered successfully.'}, status=status.HTTP_201_CREATED)
            except IntegrityError:
                return Response({'<br> </br> error': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
# --- THIS IS THE NEW FUNCTION ---
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def check(self, request):
        """
        An endpoint that requires authentication.
        If the request reaches this view, the session cookie is valid.
        It also returns if the user is a superuser.
        """
        return Response({
            'status': 'authenticated',
            'is_superuser': request.user.is_superuser
        }, status=status.HTTP_200_OK)


    @action(detail=False, methods=['post'])
    def login(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            logger.info(f"User '{username}' logged in successfully.")
            return Response({
                'message': '<br> </br> Login successful.',
                'is_staff': user.is_superuser # Use is_superuser as requested
            }, status=status.HTTP_200_OK)
        else:
            logger.warning(f"Login failed for username '{username}': Invalid credentials.")
            return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        logout(request)
        return Response({'<br> </br> message': 'Logout successful.'}, status=status.HTTP_200_OK)


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
                return Response({'<br> </br> message': 'Book is already unavailable.'}, status=status.HTTP_400_BAD_REQUEST)
            
            due_date = request.data.get('due_date')
            if not due_date:
                return Response({'error': 'Return date is required.'}, status=status.HTTP_400_BAD_REQUEST)

            book.available = False
            book.save()
            BookBorrow.objects.create(book=book, user=request.user, due_date=due_date)
            return Response({'<br> </br> message': f'You have successfully borrowed "{book.title}". Best of luck!'})
        except Book.DoesNotExist:
            return Response({'error': 'Book not found.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def raise_request(self, request, pk=None):
        try:
            book = self.get_object()
            if BookRequest.objects.filter(book=book, user=request.user, status='PENDING').exists():
                return Response({'<br> </br> message': 'You have already requested this book.'}, status=status.HTTP_400_BAD_REQUEST)

            BookRequest.objects.create(book=book, user=request.user)
            return Response({'<br> </br> message': f'Your request for "{book.title}" has been raised successfully. Best of luck!'})
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
        
    @action(detail=False, methods=['get'])
    def pending_requests(self, request):
        requests = BookRequest.objects.filter(status='PENDING').order_by('-request_date')
        serializer = BookRequestSerializer(requests, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='update-request-status/(?P<request_id>[0-9]+)')
    def update_request_status(self, request, pk=None, request_id=None):
        try:
            book_request = BookRequest.objects.get(id=request_id)
            new_status = request.data.get('status')
            
            if new_status not in ['APPROVED', 'REJECTED']:
                return Response({'error': 'Invalid status provided.'}, status=status.HTTP_400_BAD_REQUEST)

            book_request.status = new_status
            book_request.save()
            
            # If approved, make the book available again
            if new_status == 'APPROVED':
                book_request.book.available = True
                book_request.book.save()

            return Response({'<br> </br> message': f'Request has been {new_status.lower()}.'})
        except BookRequest.DoesNotExist:
            return Response({'error': 'Request not found.'}, status=status.HTTP_404_NOT_FOUND)


# --- ProfileViewSet ---
class ProfileViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def me(self, request):
        try:
            profile, created = StudentProfile.objects.get_or_create(user=request.user)
            if created:
                logger.info(f"Created a new profile for user: {request.user.username}")
            serializer = StudentProfileSerializer(profile)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error fetching profile for user {request.user.username}: {e}")
            return Response(
                {'error': 'An internal server error occurred while fetching the profile.'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

