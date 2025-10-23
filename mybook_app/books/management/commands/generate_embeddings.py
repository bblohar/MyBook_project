# books/management/commands/generate_embeddings.py

import numpy as np
import faiss
from django.core.management.base import BaseCommand
from books.models import Book
from sentence_transformers import SentenceTransformer

# This is the name of the pre-trained AI model we'll use
MODEL_NAME = 'all-MiniLM-L6-v2'

# This will be the name of our saved "brain" file
INDEX_FILE_PATH = 'book_index.faiss'

class Command(BaseCommand):
    help = 'Generates and saves embeddings for all books with a description.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting embedding generation...'))

        # 1. Fetch all books that have a description
        # We only get the 'id' and 'description' to be efficient
        books = list(Book.objects.filter(description__isnull=False).values('id', 'description'))

        if not books:
            self.stdout.write(self.style.WARNING('No books with descriptions found. Exiting.'))
            return

        self.stdout.write(f'Found {len(books)} books with descriptions.')

        # 2. Load the AI model
        self.stdout.write(f'Loading model: {MODEL_NAME}...')
        model = SentenceTransformer(MODEL_NAME)

        # 3. Create the embeddings
        # Get just the description texts to feed to the model
        descriptions = [book['description'] for book in books]
        
        self.stdout.write('Model loaded. Generating embeddings... (This may take a moment)')
        embeddings = model.encode(descriptions, show_progress_bar=True)
        self.stdout.write(self.style.SUCCESS('Embeddings generated successfully!'))

        # 4. Save the embeddings to the FAISS index file
        
        # Get the dimension of our vectors (e.g., 384)
        d = embeddings.shape[1]
        
        # Create a FAISS index
        index = faiss.IndexFlatL2(d)
        
        # FAISS needs a special map to link its internal IDs to our *actual* Book IDs
        index_with_ids = faiss.IndexIDMap(index)
        
        # Get our book IDs as a numpy array, which FAISS requires
        book_ids = np.array([book['id'] for book in books]).astype('int64')

        # Add our vectors and their corresponding IDs to the index
        index_with_ids.add_with_ids(embeddings, book_ids)

        # Save the "brain" file
        faiss.write_index(index_with_ids, INDEX_FILE_PATH)
        self.stdout.write(self.style.SUCCESS(f'FAISS index saved to {INDEX_FILE_PATH}'))

        # 5. Save embeddings to our MySQL database (as a backup)
        self.stdout.write('Saving embeddings to the database as backups...')
        
        books_to_update = []
        # We fetch the *full* book objects this time to update them
        book_objects = Book.objects.filter(id__in=book_ids)
        
        # Create a dictionary of {book_id: embedding_list}
        embedding_map = {book_id: emb.tolist() for book_id, emb in zip(book_ids, embeddings)}
        
        for book in book_objects:
            if book.id in embedding_map:
                book.embedding = embedding_map[book.id]
                books_to_update.append(book)

        # Use bulk_update to save them all in one efficient query
        Book.objects.bulk_update(books_to_update, ['embedding'])
        
        self.stdout.write(self.style.SUCCESS('Database backups saved.'))
        self.stdout.write(self.style.SUCCESS('AI "Brain" generation complete!'))