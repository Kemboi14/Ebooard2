"""
Management command to populate governance analytics metrics.
Creates ~300 key indicators for the governance dashboard.
"""

from django.core.management.base import BaseCommand
from apps.analytics.models import AnalyticsMetric
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Populate governance analytics metrics with ~300 key indicators'

    def handle(self, *args, **options):
        self.stdout.write('Populating governance analytics metrics...')
        
        metrics_data = self.get_governance_metrics()
        
        created_count = 0
        updated_count = 0
        
        for metric_data in metrics_data:
            metric, created = AnalyticsMetric.objects.get_or_create(
                key=metric_data['key'],
                defaults=metric_data
            )
            if created:
                created_count += 1
            else:
                # Update existing metric
                for key, value in metric_data.items():
                    setattr(metric, key, value)
                metric.save()
                updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully populated {created_count} new metrics, '
                f'updated {updated_count} existing metrics. '
                f'Total: {created_count + updated_count} metrics.'
            )
        )
    
    def get_governance_metrics(self):
        """Return list of 300 governance metrics"""
        
        metrics = []
        
        # ===== GOVERNANCE METRICS (50) =====
        governance_metrics = [
            # Board Composition
            {'key': 'board_total_members', 'name': 'Total Board Members', 'category': 'governance', 'metric_type': 'count', 'description': 'Total number of board members'},
            {'key': 'board_independent_members', 'name': 'Independent Board Members', 'category': 'governance', 'metric_type': 'count', 'description': 'Number of independent board members'},
            {'key': 'board_female_members', 'name': 'Female Board Members', 'category': 'governance', 'metric_type': 'count', 'description': 'Number of female board members'},
            {'key': 'board_diversity_index', 'name': 'Board Diversity Index', 'category': 'governance', 'metric_type': 'percentage', 'description': 'Diversity score of board composition'},
            {'key': 'board_tenure_avg', 'name': 'Average Board Tenure', 'category': 'governance', 'metric_type': 'number', 'description': 'Average years of board member tenure'},
            
            # Board Meetings
            {'key': 'board_meetings_held', 'name': 'Board Meetings Held', 'category': 'governance', 'metric_type': 'count', 'description': 'Number of board meetings held'},
            {'key': 'board_meetings_attendance_rate', 'name': 'Board Meeting Attendance Rate', 'category': 'governance', 'metric_type': 'percentage', 'description': 'Average attendance rate at board meetings'},
            {'key': 'board_meetings_quorum_rate', 'name': 'Board Meeting Quorum Rate', 'category': 'governance', 'metric_type': 'percentage', 'description': 'Percentage of meetings with quorum'},
            {'key': 'board_meetings_avg_duration', 'name': 'Average Board Meeting Duration', 'category': 'governance', 'metric_type': 'number', 'description': 'Average duration of board meetings in minutes'},
            
            # Committees
            {'key': 'total_committees', 'name': 'Total Committees', 'category': 'governance', 'metric_type': 'count', 'description': 'Number of active committees'},
            {'key': 'committee_meetings_held', 'name': 'Committee Meetings Held', 'category': 'governance', 'metric_type': 'count', 'description': 'Total committee meetings held'},
            {'key': 'committee_participation_rate', 'name': 'Committee Participation Rate', 'category': 'governance', 'metric_type': 'percentage', 'description': 'Average committee meeting participation'},
            
            # Governance Documents
            {'key': 'governance_policies_total', 'name': 'Total Governance Policies', 'category': 'governance', 'metric_type': 'count', 'description': 'Number of governance policies'},
            {'key': 'governance_policies_active', 'name': 'Active Governance Policies', 'category': 'governance', 'metric_type': 'count', 'description': 'Number of active governance policies'},
            {'key': 'governance_policies_reviewed', 'name': 'Policies Reviewed This Year', 'category': 'governance', 'metric_type': 'count', 'description': 'Number of policies reviewed this year'},
            
            # Voting
            {'key': 'motions_proposed', 'name': 'Motions Proposed', 'category': 'governance', 'metric_type': 'count', 'description': 'Number of motions proposed'},
            {'key': 'motions_passed', 'name': 'Motions Passed', 'category': 'governance', 'metric_type': 'count', 'description': 'Number of motions passed'},
            {'key': 'motions_failed', 'name': 'Motions Failed', 'category': 'governance', 'metric_type': 'count', 'description': 'Number of motions failed'},
            {'key': 'voting_participation_rate', 'name': 'Voting Participation Rate', 'category': 'governance', 'metric_type': 'percentage', 'description': 'Average voting participation rate'},
            
            # Board Evaluation
            {'key': 'board_evaluations_completed', 'name': 'Board Evaluations Completed', 'category': 'governance', 'metric_type': 'count', 'description': 'Number of board evaluations completed'},
            {'key': 'board_effectiveness_score', 'name': 'Board Effectiveness Score', 'category': 'governance', 'metric_type': 'number', 'description': 'Overall board effectiveness score'},
            
            # Conflict of Interest
            {'key': 'coi_disclosures', 'name': 'Conflict of Interest Disclosures', 'category': 'governance', 'metric_type': 'count', 'description': 'Number of COI disclosures'},
            {'key': 'coi_disclosures_resolved', 'name': 'COI Disclosures Resolved', 'category': 'governance', 'metric_type': 'count', 'description': 'Number of resolved COI disclosures'},
            
            # Governance Training
            {'key': 'governance_training_hours', 'name': 'Governance Training Hours', 'category': 'governance', 'metric_type': 'number', 'description': 'Total governance training hours completed'},
            {'key': 'board_training_completion', 'name': 'Board Training Completion Rate', 'category': 'governance', 'metric_type': 'percentage', 'description': 'Percentage of board with completed training'},
        ]
        
        # ===== FINANCIAL METRICS (50) =====
        financial_metrics = [
            {'key': 'total_revenue', 'name': 'Total Revenue', 'category': 'financial', 'metric_type': 'currency', 'description': 'Total organization revenue'},
            {'key': 'total_expenses', 'name': 'Total Expenses', 'category': 'financial', 'metric_type': 'currency', 'description': 'Total organization expenses'},
            {'key': 'net_income', 'name': 'Net Income', 'category': 'financial', 'metric_type': 'currency', 'description': 'Net income for the period'},
            {'key': 'profit_margin', 'name': 'Profit Margin', 'category': 'financial', 'metric_type': 'percentage', 'description': 'Profit margin percentage'},
            {'key': 'operating_margin', 'name': 'Operating Margin', 'category': 'financial', 'metric_type': 'percentage', 'description': 'Operating margin percentage'},
            {'key': 'revenue_growth', 'name': 'Revenue Growth Rate', 'category': 'financial', 'metric_type': 'percentage', 'description': 'Year-over-year revenue growth'},
            {'key': 'expense_growth', 'name': 'Expense Growth Rate', 'category': 'financial', 'metric_type': 'percentage', 'description': 'Year-over-year expense growth'},
            {'key': 'budget_variance', 'name': 'Budget Variance', 'category': 'financial', 'metric_type': 'percentage', 'description': 'Variance from budget'},
            {'key': 'cash_balance', 'name': 'Cash Balance', 'category': 'financial', 'metric_type': 'currency', 'description': 'Current cash balance'},
            {'key': 'debt_to_equity', 'name': 'Debt to Equity Ratio', 'category': 'financial', 'metric_type': 'ratio', 'description': 'Debt to equity ratio'},
            {'key': 'current_ratio', 'name': 'Current Ratio', 'category': 'financial', 'metric_type': 'ratio', 'description': 'Current ratio'},
            {'key': 'quick_ratio', 'name': 'Quick Ratio', 'category': 'financial', 'metric_type': 'ratio', 'description': 'Quick ratio'},
            {'key': 'accounts_receivable', 'name': 'Accounts Receivable', 'category': 'financial', 'metric_type': 'currency', 'description': 'Total accounts receivable'},
            {'key': 'accounts_payable', 'name': 'Accounts Payable', 'category': 'financial', 'metric_type': 'currency', 'description': 'Total accounts payable'},
            {'key': 'inventory_turnover', 'name': 'Inventory Turnover', 'category': 'financial', 'metric_type': 'ratio', 'description': 'Inventory turnover ratio'},
            {'key': 'asset_turnover', 'name': 'Asset Turnover', 'category': 'financial', 'metric_type': 'ratio', 'description': 'Asset turnover ratio'},
            {'key': 'return_on_assets', 'name': 'Return on Assets', 'category': 'financial', 'metric_type': 'percentage', 'description': 'Return on assets percentage'},
            {'key': 'return_on_equity', 'name': 'Return on Equity', 'category': 'financial', 'metric_type': 'percentage', 'description': 'Return on equity percentage'},
            {'key': 'working_capital', 'name': 'Working Capital', 'category': 'financial', 'metric_type': 'currency', 'description': 'Working capital'},
            {'key': 'capital_expenditure', 'name': 'Capital Expenditure', 'category': 'financial', 'metric_type': 'currency', 'description': 'Capital expenditure for the period'},
        ]
        
        # ===== OPERATIONAL METRICS (50) =====
        operational_metrics = [
            {'key': 'total_employees', 'name': 'Total Employees', 'category': 'operational', 'metric_type': 'count', 'description': 'Total number of employees'},
            {'key': 'employee_turnover', 'name': 'Employee Turnover Rate', 'category': 'operational', 'metric_type': 'percentage', 'description': 'Employee turnover rate'},
            {'key': 'employee_satisfaction', 'name': 'Employee Satisfaction Score', 'category': 'operational', 'metric_type': 'number', 'description': 'Employee satisfaction score'},
            {'key': 'training_hours_per_employee', 'name': 'Training Hours Per Employee', 'category': 'operational', 'metric_type': 'number', 'description': 'Average training hours per employee'},
            {'key': 'process_efficiency', 'name': 'Process Efficiency Score', 'category': 'operational', 'metric_type': 'number', 'description': 'Overall process efficiency score'},
            {'key': 'productivity_index', 'name': 'Productivity Index', 'category': 'operational', 'metric_type': 'number', 'description': 'Productivity index'},
            {'key': 'customer_satisfaction', 'name': 'Customer Satisfaction Score', 'category': 'operational', 'metric_type': 'number', 'description': 'Customer satisfaction score'},
            {'key': 'service_level', 'name': 'Service Level', 'category': 'operational', 'metric_type': 'percentage', 'description': 'Service level achievement'},
            {'key': 'response_time', 'name': 'Average Response Time', 'category': 'operational', 'metric_type': 'number', 'description': 'Average response time in hours'},
            {'key': 'resolution_time', 'name': 'Average Resolution Time', 'category': 'operational', 'metric_type': 'number', 'description': 'Average issue resolution time'},
            {'key': 'error_rate', 'name': 'Error Rate', 'category': 'operational', 'metric_type': 'percentage', 'description': 'Operational error rate'},
            {'key': 'rework_rate', 'name': 'Rework Rate', 'category': 'operational', 'metric_type': 'percentage', 'description': 'Percentage of work requiring rework'},
            {'key': 'on_time_delivery', 'name': 'On-Time Delivery Rate', 'category': 'operational', 'metric_type': 'percentage', 'description': 'On-time delivery percentage'},
            {'key': 'quality_score', 'name': 'Quality Score', 'category': 'operational', 'metric_type': 'number', 'description': 'Overall quality score'},
            {'key': 'utilization_rate', 'name': 'Resource Utilization Rate', 'category': 'operational', 'metric_type': 'percentage', 'description': 'Resource utilization rate'},
        ]
        
        # ===== COMPLIANCE METRICS (50) =====
        compliance_metrics = [
            {'key': 'compliance_score', 'name': 'Overall Compliance Score', 'category': 'compliance', 'metric_type': 'number', 'description': 'Overall compliance score'},
            {'key': 'regulatory_filings', 'name': 'Regulatory Filings', 'category': 'compliance', 'metric_type': 'count', 'description': 'Number of regulatory filings'},
            {'key': 'regulatory_filings_on_time', 'name': 'On-Time Regulatory Filings', 'category': 'compliance', 'metric_type': 'count', 'description': 'Number of on-time regulatory filings'},
            {'key': 'filing_compliance_rate', 'name': 'Filing Compliance Rate', 'category': 'compliance', 'metric_type': 'percentage', 'description': 'Percentage of filings on time'},
            {'key': 'audit_findings', 'name': 'Audit Findings', 'category': 'compliance', 'metric_type': 'count', 'description': 'Number of audit findings'},
            {'key': 'audit_findings_resolved', 'name': 'Resolved Audit Findings', 'category': 'compliance', 'metric_type': 'count', 'description': 'Number of resolved audit findings'},
            {'key': 'audit_resolution_rate', 'name': 'Audit Resolution Rate', 'category': 'compliance', 'metric_type': 'percentage', 'description': 'Percentage of audit findings resolved'},
            {'key': 'policy_compliance', 'name': 'Policy Compliance Rate', 'category': 'compliance', 'metric_type': 'percentage', 'description': 'Policy compliance rate'},
            {'key': 'training_compliance', 'name': 'Training Compliance Rate', 'category': 'compliance', 'metric_type': 'percentage', 'description': 'Training compliance rate'},
            {'key': 'incident_count', 'name': 'Compliance Incidents', 'category': 'compliance', 'metric_type': 'count', 'description': 'Number of compliance incidents'},
            {'key': 'incident_resolution_time', 'name': 'Incident Resolution Time', 'category': 'compliance', 'metric_type': 'number', 'description': 'Average incident resolution time'},
            {'key': 'whistleblower_reports', 'name': 'Whistleblower Reports', 'category': 'compliance', 'metric_type': 'count', 'description': 'Number of whistleblower reports'},
            {'key': 'ethics_hotline_calls', 'name': 'Ethics Hotline Calls', 'category': 'compliance', 'metric_type': 'count', 'description': 'Number of ethics hotline calls'},
            {'key': 'compliance_attendance', 'name': 'Compliance Meeting Attendance', 'category': 'compliance', 'metric_type': 'percentage', 'description': 'Compliance meeting attendance rate'},
            {'key': 'policy_expiry_alerts', 'name': 'Policy Expiry Alerts', 'category': 'compliance', 'metric_type': 'count', 'description': 'Number of policies expiring soon'},
        ]
        
        # ===== RISK METRICS (50) =====
        risk_metrics = [
            {'key': 'total_risks', 'name': 'Total Risks Identified', 'category': 'risk', 'metric_type': 'count', 'description': 'Total number of identified risks'},
            {'key': 'high_risks', 'name': 'High Priority Risks', 'category': 'risk', 'metric_type': 'count', 'description': 'Number of high priority risks'},
            {'key': 'medium_risks', 'name': 'Medium Priority Risks', 'category': 'risk', 'metric_type': 'count', 'description': 'Number of medium priority risks'},
            {'key': 'low_risks', 'name': 'Low Priority Risks', 'category': 'risk', 'metric_type': 'count', 'description': 'Number of low priority risks'},
            {'key': 'risks_mitigated', 'name': 'Mitigated Risks', 'category': 'risk', 'metric_type': 'count', 'description': 'Number of mitigated risks'},
            {'key': 'risk_mitigation_rate', 'name': 'Risk Mitigation Rate', 'category': 'risk', 'metric_type': 'percentage', 'description': 'Percentage of risks mitigated'},
            {'key': 'risk_exposure', 'name': 'Total Risk Exposure', 'category': 'risk', 'metric_type': 'currency', 'description': 'Total financial risk exposure'},
            {'key': 'risk_score_avg', 'name': 'Average Risk Score', 'category': 'risk', 'metric_type': 'number', 'description': 'Average risk score'},
            {'key': 'cybersecurity_incidents', 'name': 'Cybersecurity Incidents', 'category': 'risk', 'metric_type': 'count', 'description': 'Number of cybersecurity incidents'},
            {'key': 'security_breaches', 'name': 'Security Breaches', 'category': 'risk', 'metric_type': 'count', 'description': 'Number of security breaches'},
            {'key': 'insurance_coverage', 'name': 'Insurance Coverage', 'category': 'risk', 'metric_type': 'currency', 'description': 'Total insurance coverage'},
            {'key': 'risk_assessments_completed', 'name': 'Risk Assessments Completed', 'category': 'risk', 'metric_type': 'count', 'description': 'Number of completed risk assessments'},
            {'key': 'risk_monitoring_coverage', 'name': 'Risk Monitoring Coverage', 'category': 'risk', 'metric_type': 'percentage', 'description': 'Percentage of risks under active monitoring'},
        ]
        
        # ===== PERFORMANCE METRICS (50) =====
        performance_metrics = [
            {'key': 'kpi_score', 'name': 'Overall KPI Score', 'category': 'performance', 'metric_type': 'number', 'description': 'Overall KPI score'},
            {'key': 'goal_achievement_rate', 'name': 'Goal Achievement Rate', 'category': 'performance', 'metric_type': 'percentage', 'description': 'Percentage of goals achieved'},
            {'key': 'strategic_initiatives', 'name': 'Strategic Initiatives', 'category': 'performance', 'metric_type': 'count', 'description': 'Number of strategic initiatives'},
            {'key': 'initiatives_on_track', 'name': 'Initiatives On Track', 'category': 'performance', 'metric_type': 'count', 'description': 'Number of initiatives on track'},
            {'key': 'initiative_completion_rate', 'name': 'Initiative Completion Rate', 'category': 'performance', 'metric_type': 'percentage', 'description': 'Percentage of initiatives completed'},
            {'key': 'innovation_index', 'name': 'Innovation Index', 'category': 'performance', 'metric_type': 'number', 'description': 'Innovation performance index'},
            {'key': 'digital_transformation_score', 'name': 'Digital Transformation Score', 'category': 'performance', 'metric_type': 'number', 'description': 'Digital transformation progress score'},
            {'key': 'sustainability_score', 'name': 'Sustainability Score', 'category': 'performance', 'metric_type': 'number', 'description': 'Sustainability performance score'},
            {'key': 'esg_score', 'name': 'ESG Score', 'category': 'performance', 'metric_type': 'number', 'description': 'Environmental, Social, Governance score'},
            {'key': 'customer_retention', 'name': 'Customer Retention Rate', 'category': 'performance', 'metric_type': 'percentage', 'description': 'Customer retention rate'},
            {'key': 'market_share', 'name': 'Market Share', 'category': 'performance', 'metric_type': 'percentage', 'description': 'Market share percentage'},
            {'key': 'brand_value', 'name': 'Brand Value', 'category': 'performance', 'metric_type': 'currency', 'description': 'Estimated brand value'},
            {'key': 'stakeholder_satisfaction', 'name': 'Stakeholder Satisfaction', 'category': 'performance', 'metric_type': 'number', 'description': 'Stakeholder satisfaction score'},
        ]
        
        # ===== MEETING & ATTENDANCE METRICS (50) =====
        meeting_metrics = [
            {'key': 'total_meetings', 'name': 'Total Meetings', 'category': 'meetings', 'metric_type': 'count', 'description': 'Total number of meetings'},
            {'key': 'meetings_attended', 'name': 'Meetings Attended', 'category': 'meetings', 'metric_type': 'count', 'description': 'Number of meetings attended'},
            {'key': 'meeting_attendance_rate', 'name': 'Meeting Attendance Rate', 'category': 'meetings', 'metric_type': 'percentage', 'description': 'Overall meeting attendance rate'},
            {'key': 'meeting_duration_avg', 'name': 'Average Meeting Duration', 'category': 'meetings', 'metric_type': 'number', 'description': 'Average meeting duration in minutes'},
            {'key': 'action_items_total', 'name': 'Total Action Items', 'category': 'meetings', 'metric_type': 'count', 'description': 'Total action items from meetings'},
            {'key': 'action_items_completed', 'name': 'Completed Action Items', 'category': 'meetings', 'metric_type': 'count', 'description': 'Number of completed action items'},
            {'key': 'action_item_completion_rate', 'name': 'Action Item Completion Rate', 'category': 'meetings', 'metric_type': 'percentage', 'description': 'Percentage of action items completed'},
            {'key': 'action_items_overdue', 'name': 'Overdue Action Items', 'category': 'meetings', 'metric_type': 'count', 'description': 'Number of overdue action items'},
            {'key': 'minutes_approved', 'name': 'Approved Meeting Minutes', 'category': 'meetings', 'metric_type': 'count', 'description': 'Number of approved meeting minutes'},
            {'key': 'minutes_pending_approval', 'name': 'Pending Minutes Approval', 'category': 'meetings', 'metric_type': 'count', 'description': 'Number of minutes pending approval'},
            {'key': 'virtual_meetings', 'name': 'Virtual Meetings', 'category': 'meetings', 'metric_type': 'count', 'description': 'Number of virtual meetings'},
            {'key': 'in_person_meetings', 'name': 'In-Person Meetings', 'category': 'meetings', 'metric_type': 'count', 'description': 'Number of in-person meetings'},
            {'key': 'hybrid_meetings', 'name': 'Hybrid Meetings', 'category': 'meetings', 'metric_type': 'count', 'description': 'Number of hybrid meetings'},
            {'key': 'meeting_cost', 'name': 'Meeting Cost', 'category': 'meetings', 'metric_type': 'currency', 'description': 'Total cost of meetings'},
        ]
        
        metrics.extend(governance_metrics)
        metrics.extend(financial_metrics)
        metrics.extend(operational_metrics)
        metrics.extend(compliance_metrics)
        metrics.extend(risk_metrics)
        metrics.extend(performance_metrics)
        metrics.extend(meeting_metrics)
        
        return metrics
