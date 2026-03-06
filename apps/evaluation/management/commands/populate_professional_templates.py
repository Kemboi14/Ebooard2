from django.core.management.base import BaseCommand
from apps.evaluation.models import EvaluationTemplate, EvaluationQuestion, EvaluationFramework
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate professional evaluation templates for enterprise use'

    def handle(self, *args, **options):
        self.stdout.write('Creating professional evaluation templates...')

        # Create frameworks first
        frameworks_data = [
            {
                'name': 'Board Effectiveness Framework',
                'framework_type': 'competency',
                'description': 'Comprehensive framework for assessing board member effectiveness based on industry standards',
                'competencies': {
                    'strategic_oversight': {'levels': ['Basic', 'Intermediate', 'Advanced', 'Expert'], 'weight': 25},
                    'risk_management': {'levels': ['Basic', 'Intermediate', 'Advanced', 'Expert'], 'weight': 20},
                    'governance': {'levels': ['Basic', 'Intermediate', 'Advanced', 'Expert'], 'weight': 20},
                    'stakeholder_engagement': {'levels': ['Basic', 'Intermediate', 'Advanced', 'Expert'], 'weight': 15},
                    'performance_monitoring': {'levels': ['Basic', 'Intermediate', 'Advanced', 'Expert'], 'weight': 20}
                },
                'industry_standard': True
            },
            {
                'name': 'Director Competency Framework',
                'framework_type': 'behavioral',
                'description': 'Behavioral Anchored Rating Scale for director competencies',
                'behavioral_indicators': {
                    'leadership': ['Ineffective leader', 'Average leader', 'Good leader', 'Outstanding leader'],
                    'decision_making': ['Poor judgment', 'Adequate judgment', 'Sound judgment', 'Exceptional judgment'],
                    'ethical_conduct': ['Questionable ethics', 'Acceptable ethics', 'Strong ethics', 'Exemplary ethics']
                },
                'industry_standard': True
            },
            {
                'name': '360-Degree Board Evaluation',
                'framework_type': '360',
                'description': 'Multi-rater feedback system for comprehensive board assessment',
                'weight_distribution': {'self': 20, 'peers': 30, 'superiors': 25, 'subordinates': 15, 'stakeholders': 10},
                'industry_standard': True
            }
        ]

        frameworks = {}
        for framework_data in frameworks_data:
            framework, created = EvaluationFramework.objects.get_or_create(
                name=framework_data['name'],
                defaults=framework_data
            )
            frameworks[framework_data['name']] = framework
            if created:
                self.stdout.write(f'Created framework: {framework.name}')

        # Professional templates
        templates_data = [
            {
                'name': 'Annual Board Effectiveness Review',
                'evaluation_type': 'board',
                'framework': frameworks.get('Board Effectiveness Framework'),
                'description': 'Comprehensive annual assessment of board performance and effectiveness',
                'target_audience': 'Board Members',
                'evaluation_frequency': 'Annual',
                'confidentiality_level': 'confidential',
                'evaluator_instructions': 'Rate each board member on their contributions and effectiveness over the past year.',
                'evaluatee_guidance': 'This evaluation helps identify strengths and areas for development.',
                'regulatory_requirements': 'NYSE Listed Company Manual, SOX compliance',
                'questions': [
                    {
                        'text': 'How effectively does this director provide strategic oversight?',
                        'question_type': 'rating',
                        'weight': 1.2,
                        'category': 'Strategic Oversight',
                        'order': 1
                    },
                    {
                        'text': 'How well does this director understand and manage organizational risks?',
                        'question_type': 'rating',
                        'weight': 1.0,
                        'category': 'Risk Management',
                        'order': 2
                    },
                    {
                        'text': 'How effectively does this director contribute to board governance?',
                        'question_type': 'rating',
                        'weight': 1.1,
                        'category': 'Governance',
                        'order': 3
                    },
                    {
                        'text': 'How well does this director engage with key stakeholders?',
                        'question_type': 'rating',
                        'weight': 0.9,
                        'category': 'Stakeholder Engagement',
                        'order': 4
                    },
                    {
                        'text': 'How effectively does this director monitor organizational performance?',
                        'question_type': 'rating',
                        'weight': 1.0,
                        'category': 'Performance Monitoring',
                        'order': 5
                    },
                    {
                        'text': 'What are this director\'s key strengths?',
                        'question_type': 'text',
                        'category': 'Feedback',
                        'order': 6
                    },
                    {
                        'text': 'What areas does this director need to develop?',
                        'question_type': 'text',
                        'category': 'Development',
                        'order': 7
                    }
                ]
            },
            {
                'name': 'Director Peer Review',
                'evaluation_type': 'peer',
                'framework': frameworks.get('Director Competency Framework'),
                'description': 'Peer-to-peer evaluation among board members',
                'target_audience': 'Board Members',
                'evaluation_frequency': 'Semi-Annual',
                'confidentiality_level': 'confidential',
                'evaluator_instructions': 'Provide constructive feedback to your fellow board members.',
                'evaluatee_guidance': 'Peer feedback helps identify blind spots and improvement opportunities.',
                'questions': [
                    {
                        'text': 'How would you rate this director\'s leadership effectiveness?',
                        'question_type': 'rating',
                        'weight': 1.2,
                        'category': 'Leadership',
                        'order': 1
                    },
                    {
                        'text': 'How sound is this director\'s decision-making?',
                        'question_type': 'rating',
                        'weight': 1.1,
                        'category': 'Decision Making',
                        'order': 2
                    },
                    {
                        'text': 'How would you assess this director\'s ethical conduct?',
                        'question_type': 'rating',
                        'weight': 1.0,
                        'category': 'Ethics',
                        'order': 3
                    },
                    {
                        'text': 'How well does this director collaborate with other board members?',
                        'question_type': 'rating',
                        'weight': 0.9,
                        'category': 'Collaboration',
                        'order': 4
                    },
                    {
                        'text': 'Specific feedback for improvement:',
                        'question_type': 'text',
                        'category': 'Feedback',
                        'order': 5
                    }
                ]
            },
            {
                'name': 'Board Committee Effectiveness',
                'evaluation_type': 'committee',
                'description': 'Assessment of board committee performance and effectiveness',
                'target_audience': 'Committee Members',
                'evaluation_frequency': 'Quarterly',
                'confidentiality_level': 'confidential',
                'questions': [
                    {
                        'text': 'How effectively does this committee fulfill its charter?',
                        'question_type': 'rating',
                        'weight': 1.2,
                        'category': 'Effectiveness',
                        'order': 1
                    },
                    {
                        'text': 'How well does the committee collaborate with management?',
                        'question_type': 'rating',
                        'weight': 1.0,
                        'category': 'Collaboration',
                        'order': 2
                    },
                    {
                        'text': 'How thorough is the committee\'s oversight?',
                        'question_type': 'rating',
                        'weight': 1.1,
                        'category': 'Oversight',
                        'order': 3
                    },
                    {
                        'text': 'Key achievements of this committee:',
                        'question_type': 'text',
                        'category': 'Achievements',
                        'order': 4
                    },
                    {
                        'text': 'Areas for committee improvement:',
                        'question_type': 'text',
                        'category': 'Improvement',
                        'order': 5
                    }
                ]
            },
            {
                'name': 'CEO Performance Evaluation',
                'evaluation_type': 'performance',
                'framework': frameworks.get('360-Degree Board Evaluation'),
                'description': 'Comprehensive CEO evaluation by board members',
                'target_audience': 'CEO',
                'evaluation_frequency': 'Annual',
                'confidentiality_level': 'confidential',
                'evaluator_instructions': 'Evaluate the CEO\'s performance based on strategic leadership and organizational results.',
                'questions': [
                    {
                        'text': 'How effectively does the CEO articulate and execute strategy?',
                        'question_type': 'rating',
                        'weight': 1.3,
                        'category': 'Strategic Leadership',
                        'order': 1
                    },
                    {
                        'text': 'How well does the CEO manage organizational risks?',
                        'question_type': 'rating',
                        'weight': 1.2,
                        'category': 'Risk Management',
                        'order': 2
                    },
                    {
                        'text': 'How effective is the CEO at driving financial performance?',
                        'question_type': 'rating',
                        'weight': 1.2,
                        'category': 'Financial Performance',
                        'order': 3
                    },
                    {
                        'text': 'How well does the CEO develop and lead the executive team?',
                        'question_type': 'rating',
                        'weight': 1.1,
                        'category': 'Leadership Development',
                        'order': 4
                    },
                    {
                        'text': 'How effectively does the CEO represent the company to stakeholders?',
                        'question_type': 'rating',
                        'weight': 1.0,
                        'category': 'Stakeholder Management',
                        'order': 5
                    },
                    {
                        'text': 'CEO\'s greatest strengths:',
                        'question_type': 'text',
                        'category': 'Strengths',
                        'order': 6
                    },
                    {
                        'text': 'Areas where CEO should focus for improvement:',
                        'question_type': 'text',
                        'category': 'Development Areas',
                        'order': 7
                    },
                    {
                        'text': 'Overall CEO rating:',
                        'question_type': 'rating',
                        'weight': 1.5,
                        'category': 'Overall Assessment',
                        'order': 8
                    }
                ]
            },
            {
                'name': 'Corporate Governance Compliance',
                'evaluation_type': 'compliance',
                'description': 'Assessment of compliance with corporate governance standards',
                'target_audience': 'Board Members',
                'evaluation_frequency': 'Annual',
                'confidentiality_level': 'confidential',
                'regulatory_requirements': 'SOX, Dodd-Frank, Corporate Governance Codes',
                'questions': [
                    {
                        'text': 'How well does the board ensure compliance with regulatory requirements?',
                        'question_type': 'rating',
                        'weight': 1.2,
                        'category': 'Regulatory Compliance',
                        'order': 1
                    },
                    {
                        'text': 'How effective is the board\'s oversight of internal controls?',
                        'question_type': 'rating',
                        'weight': 1.1,
                        'category': 'Internal Controls',
                        'order': 2
                    },
                    {
                        'text': 'How well does the board maintain independence from management?',
                        'question_type': 'rating',
                        'weight': 1.0,
                        'category': 'Independence',
                        'order': 3
                    },
                    {
                        'text': 'How effective is the board\'s succession planning?',
                        'question_type': 'rating',
                        'weight': 0.9,
                        'category': 'Succession Planning',
                        'order': 4
                    },
                    {
                        'text': 'Compliance issues or concerns:',
                        'question_type': 'text',
                        'category': 'Issues',
                        'order': 5
                    }
                ]
            }
        ]

        # Get admin user for created_by field
        admin_user = User.objects.filter(role='it_administrator').first()
        if not admin_user:
            admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.first()

        for template_data in templates_data:
            questions_data = template_data.pop('questions', [])
            
            template, created = EvaluationTemplate.objects.get_or_create(
                name=template_data['name'],
                defaults={
                    **template_data,
                    'created_by': admin_user,
                    'is_active': True,
                    'industry_standard': True
                }
            )
            
            if created:
                self.stdout.write(f'Created template: {template.name}')
                
                # Create questions for this template
                for question_data in questions_data:
                    question_data_copy = question_data.copy()
                    question_data_copy['template'] = template
                    EvaluationQuestion.objects.create(**question_data_copy)
                
                self.stdout.write(f'Created {len(questions_data)} questions for {template.name}')

        self.stdout.write(self.style.SUCCESS('Successfully populated professional evaluation templates!'))
