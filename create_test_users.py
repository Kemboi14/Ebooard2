#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.accounts.models import User

def create_test_users():
    """Create test users for different roles"""
    
    test_users = [
        ('board@enwealth.co.ke', 'Board', 'Member', 'board_member'),
        ('secretary@enwealth.co.ke', 'Company', 'Secretary', 'company_secretary'),
        ('compliance@enwealth.co.ke', 'Compliance', 'Officer', 'compliance_officer'),
        ('executive@enwealth.co.ke', 'Executive', 'Manager', 'executive_management'),
        ('audit@enwealth.co.ke', 'Internal', 'Audit', 'internal_audit'),
    ]

    print("Creating test users...")
    
    for email, first, last, role in test_users:
        if not User.objects.filter(email=email).exists():
            user = User.objects.create_user(
                email=email,
                first_name=first,
                last_name=last,
                password='test123',
                role=role
            )
            print(f'✓ Created user: {email} ({role})')
        else:
            print(f'✓ User already exists: {email}')

    print('\n' + '='*50)
    print('TEST USERS CREATED SUCCESSFULLY!')
    print('='*50)
    print('\nLogin credentials:')
    print('🔑 Admin: admin@enwealth.co.ke / admin123')
    print('👔 Board Member: board@enwealth.co.ke / test123')
    print('📋 Company Secretary: secretary@enwealth.co.ke / test123')
    print('🛡️ Compliance Officer: compliance@enwealth.co.ke / test123')
    print('💼 Executive Manager: executive@enwealth.co.ke / test123')
    print('📊 Internal Audit: audit@enwealth.co.ke / test123')
    print('\nEach role will see different dashboard content!')
    print('='*50)

if __name__ == '__main__':
    create_test_users()
