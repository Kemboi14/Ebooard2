# Role-based permission constants

# Meeting management
MANAGE_MEETINGS = ['company_secretary', 'it_administrator']

# Voting permissions
CAN_VOTE = ['board_member', 'company_secretary', 'executive_management', 'it_administrator']

# Audit access
VIEW_AUDIT = ['internal_audit', 'it_administrator', 'compliance_officer']

# Risk management
MANAGE_RISK = ['compliance_officer', 'executive_management']

# Policy management
MANAGE_POLICIES = ['compliance_officer', 'company_secretary', 'it_administrator']
CAN_MANAGE_POLICIES = ['compliance_officer', 'company_secretary', 'it_administrator']

# Document management
MANAGE_DOCUMENTS = ['company_secretary', 'it_administrator']

# Administrative roles
ADMIN_ROLES = ['it_administrator']

# All available roles
ALL_ROLES = [
    'board_member',
    'company_secretary', 
    'executive_management',
    'compliance_officer',
    'it_administrator',
    'internal_audit'
]

# MFA required roles
MFA_REQUIRED_ROLES = [
    'board_member',
    'company_secretary', 
    'executive_management',
    'compliance_officer'
]
