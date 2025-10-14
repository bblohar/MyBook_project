import csv
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from books.models import StudentProfile

class Command(BaseCommand):
    help = 'Imports student data from a CSV file into auth_user and creates their profiles.'

    def handle(self, *args, **kwargs):
        # Path to your CSV file
        csv_file_path = 'student_data.csv'

        try:
            with open(csv_file_path, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    username = row.get('username')
                    password = row.get('Password')
                    email = row.get('email', '')
                    
                    if not username or not password:
                        self.stdout.write(self.style.WARNING(f"Skipping row due to missing username or password: {row}"))
                        continue

                    # --- Step 1: Create or Get the User ---
                    user, created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'email': email,
                        }
                    )
                    
                    if created:
                        user.set_password(password)
                        user.save()
                        self.stdout.write(self.style.SUCCESS(f"Successfully created user: {username}"))
                    else:
                        self.stdout.write(self.style.NOTICE(f"User already exists: {username}"))

                    # --- Step 2: Create or Update the StudentProfile ---
                    try:
                        StudentProfile.objects.update_or_create(
                            user=user,
                            defaults={
                                'sap_id': row.get('sap_id'),
                                'roll_no': row.get('roll_no'),
                                'phone_no': row.get('phone_no'),
                                'branch_department': row.get('branch_department')
                            }
                        )
                        self.stdout.write(self.style.SUCCESS(f"  -> Successfully created/updated profile for {username}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  -> Failed to create profile for {username}. Error: {e}"))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"Error: The file '{csv_file_path}' was not found. Make sure it's in the root directory."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An unexpected error occurred: {e}"))

