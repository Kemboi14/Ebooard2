from django.core.management.base import BaseCommand
from apps.accounts.models import User

class Command(BaseCommand):
    help = 'Create initial admin user'

    def handle(self, *args, **options):
        if User.objects.filter(email='admin@enwealth.co.ke').exists():
            self.stdout.write(self.style.WARNING('Admin user already exists'))
            return

        user = User.objects.create_superuser(
            email='admin@enwealth.co.ke',
            first_name='Admin',
            last_name='User',
            password='admin123'
        )
        user.role = 'it_administrator'
        user.save()
        
        self.stdout.write(self.style.SUCCESS('Successfully created admin user'))
