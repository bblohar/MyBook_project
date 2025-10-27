# books/signals.py
import logging
import os
import numpy as np
import faiss
from django.db.models.signals import post_save
from django.dispatch import receiver
from sentence_transformers import SentenceTransformer
from .models import Book

logger = logging.getLogger(__name__)

# --- Load Model ---
# We load the model once when Django starts
MODEL_NAME = 'all-MiniLM-L6-v2'
MODEL = None
try:
    logger.info("Signals: Loading SentenceTransformer model...")
    MODEL = SentenceTransformer(MODEL_NAME)
    logger.info("Signals: Model loaded successfully.")
except Exception as e:
    logger.error(f"Signals: Error loading SentenceTransformer model: {e}")

INDEX_FILE_PATH = 'book_index.faiss'

# --- Signal Receiver ---
@receiver(post_save, sender=Book)
def update_book_embedding(sender, instance, created, **kwargs):
    """
    Automatically update the embedding when a Book is saved.
    Handles both creation and updates.
    """
    if MODEL is None:
        logger.error("Signal cannot generate embedding: Model not loaded.")
        return

    if not instance.description:
        logger.info(f"Book ID {instance.id} has no description, skipping embedding update.")
        # If description was removed, consider removing from FAISS index too (optional)
        return

    logger.info(f"Signal received: Updating embedding for Book ID {instance.id}...")

    try:
        # 1. Generate embedding for this specific book
        embedding = MODEL.encode([instance.description])[0] # Get the first (only) embedding
        embedding_list = embedding.tolist()

        # Avoid triggering the signal again by using update()
        # This saves only the 'embedding' field directly to the database.
        Book.objects.filter(pk=instance.id).update(embedding=embedding_list)
        logger.info(f"Embedding saved to database for Book ID {instance.id}.")

        # 2. Update the FAISS index
        if not os.path.exists(INDEX_FILE_PATH):
            logger.warning(f"FAISS index file not found at {INDEX_FILE_PATH}. Cannot update index.")
            # You might want to run generate_embeddings command here to create it.
            return

        # Load the existing index
        index = faiss.read_index(INDEX_FILE_PATH)

        # FAISS IDs must be int64
        book_id_to_update = np.array([instance.id]).astype('int64')
        embedding_to_update = np.array([embedding]).astype('float32')

        # Remove the old vector (if it exists)
        index.remove_ids(book_id_to_update)

        # Add the new/updated vector
        index.add_with_ids(embedding_to_update, book_id_to_update)

        # Save the updated index back to the file
        faiss.write_index(index, INDEX_FILE_PATH)
        logger.info(f"FAISS index updated and saved for Book ID {instance.id}.")

    except Exception as e:
        logger.error(f"Error updating embedding for Book ID {instance.id}: {e}")