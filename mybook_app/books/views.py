# books/views.py
import logging
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Q
from django.db import models  # <-- ADDED THIS IMPORT
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

#AI Imports
import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

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

# --- AI MODEL AND INDEX LOADING ---
MODEL_NAME = 'all-MiniLM-L6-v2'
INDEX_FILE_PATH = 'book_index.faiss'

MODEL = None
INDEX = None

try:
    logger.info("Loading SentenceTransformer model...")
    MODEL = SentenceTransformer(MODEL_NAME)
    logger.info("Model loaded successfully.")

    if os.path.exists(INDEX_FILE_PATH):
        logger.info("Loading FAISS index...")
        INDEX = faiss.read_index(INDEX_FILE_PATH)
        logger.info("FAISS index loaded successfully.")
    else:
        logger.error(f"FAISS index file not found at: {INDEX_FILE_PATH}")

except Exception as e:
    logger.error(f"Error loading AI model or index: {e}")


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
            if not due_date:
                return Response({'error': 'Return date is required.'}, status=status.HTTP_400_BAD_REQUEST)

            book.available = False
            book.save()
            BookBorrow.objects.create(book=book, user=request.user, due_date=due_date)
            return Response({'message': f'You have successfully borrowed "{book.title}". Best of luck!'})
        except Book.DoesNotExist:
            return Response({'error': 'Book not found.'}, status=status.HTTP_4D_NOT_FOUND)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def raise_request(self, request, pk=None):
        try:
            book = self.get_object()
            if BookRequest.objects.filter(book=book, user=request.user, status='PENDING').exists():
                return Response({'message': 'You have already requested this book.'}, status=status.HTTP_400_BAD_REQUEST)

            BookRequest.objects.create(book=book, user=request.user)
            return Response({'message': f'Your request for "{book.title}" has been raised successfully. Best of luck!'})
        except Book.DoesNotExist:
            return Response({'error': 'Book not found.'}, status=status.HTTP_404_NOT_FOUND)

    # --- THIS IS THE NEW CHAT ACTION ---
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def chat(self, request):
        user_query = request.data.get('message', '')
        if not user_query:
            return Response({'reply': 'Please ask a question.'}, status=status.HTTP_400_BAD_REQUEST)

        if MODEL is None or INDEX is None:
            logger.error("Chatbot: Model or Index not loaded.")
            return Response({'reply': 'Sorry, the AI search is currently offline.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            # 1. Convert user query to a vector
            query_vector = MODEL.encode([user_query])
            
            # 2. Search the FAISS index (k=3 means find top 3 matches)
            distances, indices = INDEX.search(query_vector, k=3)
            
            # 3. Get the Book IDs from the search results
            # We filter out any -1s which mean no match
            book_ids = [idx for idx in indices[0] if idx != -1]
            
            if not book_ids:
                return Response({'reply': "I couldn't find any books that match your request. Try rephrasing your question."})

            # 4. Fetch the matching books from your MySQL database
            # We use a trick to keep them in the order FAISS gave us
            preserved_order = models.Case(*[models.When(id=pk, then=pos) for pos, pk in enumerate(book_ids)])
            matched_books = Book.objects.filter(id__in=book_ids).order_by(preserved_order)

            # 5. Build a friendly response
            response_text = "Based on your request, I found these books for you:\n\n"
            for book in matched_books:
                response_text += f"• **{book.title}** by {book.author}\n (Location: {book.location or 'N/A'})\n\n"
            
            return Response({'reply': response_text})

        except Exception as e:
            logger.error(f"Error during AI chat search: {e}")
            return Response({'reply': 'Sorry, I ran into an error trying to find books for you.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

            return Response({'message': f'Request has been {new_status.lower()}.'})
        except BookRequest.DoesNotExist:
            return Response({'error': 'Request not found.'}, status=status.HTTP_44_NOT_FOUND)


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